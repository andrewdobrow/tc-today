"""OpenAI Responses adapter for TCT's existing Anthropic-shaped editorial client.

Only the API transport changes. The existing Python decision/publishing gates,
assignment/editor prompts, source provenance, and canonical logic stay in place.

Activate explicitly with TCT_LLM_PROVIDER=openai and OPENAI_API_KEY.
If the OpenAI API fails, callers keep their existing fail-closed behavior.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

DEFAULT_OPENAI_MODEL = "gpt-6.1-sol"


def _text_parts(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks = []
        for part in value:
            if isinstance(part, dict):
                if part.get("type") in ("text", "input_text", "output_text"):
                    chunks.append(str(part.get("text") or ""))
                else:
                    raise ValueError("Unsupported non-text model content block")
            elif isinstance(part, str):
                chunks.append(part)
            else:
                raise ValueError("Unsupported model content block")
        return "\n".join(chunks)
    raise ValueError("Unsupported model message content type")


def translate_anthropic_request(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Preserve the exact editorial text/roles but remove Anthropic API options."""
    kwargs = dict(kwargs)
    requested_model = str(kwargs.get("model") or "").strip()
    if not requested_model:
        raise ValueError("Editorial model was not provided")
    messages = kwargs.get("messages") or []
    if not isinstance(messages, list) or not messages:
        raise ValueError("Missing editorial messages")
    if kwargs.get("tools") or kwargs.get("tool_choice"):
        raise ValueError("Tool-using model requests require an explicit adapter contract")
    if kwargs.get("stream"):
        raise ValueError("Streaming model requests require an explicit adapter contract")
    formatted = []
    for item in messages:
        if not isinstance(item, dict):
            raise ValueError("Invalid editorial message")
        role = item.get("role")
        if role not in ("user", "assistant"):
            raise ValueError("Unsupported editorial message role")
        formatted.append({"role": role, "content": _text_parts(item.get("content"))})
    system = kwargs.get("system")
    max_tokens = int(kwargs.get("max_tokens") or 1500)
    if max_tokens <= 0:
        raise ValueError("Invalid model output token limit")
    # Very short Anthropic replies (e.g. SAME or one story index) need more
    # space in reasoning-capable OpenAI models. Keep the answer task unchanged.
    output_limit = max(256, max_tokens)
    args = {
        "model": DEFAULT_OPENAI_MODEL,
        "input": formatted,
        "max_output_tokens": output_limit,
        "reasoning": {"effort": "low" if max_tokens <= 500 else "medium"},
    }
    if system:
        args["instructions"] = _text_parts(system)
    return args


def adapt_openai_response(response: Any) -> Any:
    """Expose the Anthropic response fields used by the TCT engine/tracker."""
    text = str(getattr(response, "output_text", "") or "")
    if not text:
        parts = []
        for item in getattr(response, "output", []) or []:
            for chunk in getattr(item, "content", []) or []:
                if getattr(chunk, "type", "") == "output_text":
                    parts.append(str(getattr(chunk, "text", "") or ""))
        text = "\n".join(parts)
    if not text.strip():
        status = str(getattr(response, "status", "unknown"))
        raise ValueError("OpenAI returned no editorial text (status=" + status + ")")
    status = str(getattr(response, "status", "") or "")
    if status not in ("completed", ""):
        raise ValueError("OpenAI editorial response incomplete (status=" + status + ")")
    usage = getattr(response, "usage", None)
    total_input = int(getattr(usage, "input_tokens", 0) or 0)
    cached_input = int(getattr(
        getattr(usage, "input_tokens_details", None), "cached_tokens", 0) or 0)
    cached_input = min(total_input, max(0, cached_input))
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        model=str(getattr(response, "model", "") or DEFAULT_OPENAI_MODEL),
        stop_reason="end_turn",
        usage=SimpleNamespace(
            input_tokens=total_input - cached_input,
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            cache_creation_input_tokens=0,
            cache_read_input_tokens=cached_input,
        ),
    )


class _OpenAIMessages:
    def __init__(self, api_client: Any):
        self._api_client = api_client

    def create(self, **kwargs: Any) -> Any:
        return adapt_openai_response(
            self._api_client.responses.create(**translate_anthropic_request(kwargs)))


class OpenAIEditorialClient:
    """Anthropic-compatible transport for TCT; model decisions remain in TCT."""

    def __init__(self, api_client: Any):
        self._api_client = api_client
        self.messages = _OpenAIMessages(api_client)

    def with_options(self, **kwargs: Any) -> "OpenAIEditorialClient":
        if not hasattr(self._api_client, "with_options"):
            raise ValueError("OpenAI SDK client does not support request options")
        return OpenAIEditorialClient(self._api_client.with_options(**kwargs))


def make_openai_editorial_client(*, api_key: str) -> OpenAIEditorialClient:
    if not api_key:
        raise ValueError("TCT_LLM_PROVIDER=openai requires OPENAI_API_KEY")
    from openai import OpenAI

    return OpenAIEditorialClient(OpenAI(api_key=api_key, max_retries=0))
