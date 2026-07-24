import importlib
import os
import sys
import types

import pytest


def _load_generate_module():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser

    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Messages:
            def create(self, *args, **kwargs):
                raise RuntimeError("AI calls are disabled in JSON parser tests")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = _Messages()

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic

    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


def test_parse_index_array_accepts_fenced_json():
    generate = _load_generate_module()
    assert generate._parse_json_index_array("```json\n[2, 4]\n```", max_index=4) == [2, 4]


def test_parse_index_array_extracts_array_from_prose():
    generate = _load_generate_module()
    assert generate._parse_json_index_array("Duplicates: [3, 1].", max_index=3) == [3, 1]


def test_parse_index_array_filters_duplicates_and_invalid_indexes():
    generate = _load_generate_module()
    raw = '[2, "2", 0, -1, 8, true, "bad", 3]'
    assert generate._parse_json_index_array(raw, max_index=4) == [2, 3]


def test_parse_index_array_accepts_empty_json_array():
    generate = _load_generate_module()
    assert generate._parse_json_index_array("[]", max_index=9) == []


def test_parse_index_array_rejects_empty_response():
    generate = _load_generate_module()
    with pytest.raises(ValueError, match="empty response"):
        generate._parse_json_index_array("", max_index=3)


class _Response:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(text=text)]


class _SequenceMessages:
    def __init__(self, texts):
        self._texts = iter(texts)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(next(self._texts))


class _SequenceClient:
    def __init__(self, texts):
        self.messages = _SequenceMessages(texts)


def test_request_index_array_retries_after_empty_response():
    generate = _load_generate_module()
    fake = _SequenceClient(["", "```json\n[2]\n```"])

    indexes, attempts = generate._request_json_index_array(
        "Return duplicate indexes",
        model="offline-model",
        max_tokens=20,
        max_index=3,
        request_client=fake,
    )

    assert indexes == [2]
    assert attempts == 2
    assert len(fake.messages.calls) == 2
    assert "previous response was invalid" in fake.messages.calls[1]["messages"][0]["content"]


def test_request_index_array_raises_after_two_invalid_responses():
    generate = _load_generate_module()
    fake = _SequenceClient(["", "not json"])

    with pytest.raises(ValueError, match="attempt 1.*attempt 2"):
        generate._request_json_index_array(
            "Return duplicate indexes",
            model="offline-model",
            max_tokens=20,
            max_index=3,
            request_client=fake,
        )



def test_hero_semantic_dedup_uses_retry_result(monkeypatch):
    generate = _load_generate_module()
    fake = _SequenceClient(["", "[1]"])
    monkeypatch.setattr(generate, "client", fake)

    top = {
        "category_key": "crime",
        "category_label": "Crime & Safety",
        "hero": {"headline": "Alpha lead story"},
        "cards": [],
    }
    other = {
        "category_key": "martin",
        "category_label": "Martin County",
        "hero": {"headline": "Different wording entirely"},
        "cards": [{"headline": "Replacement county story"}],
    }

    generate.promote_duplicate_heroes(top, [top, other])

    assert other["hero"]["headline"] == "Replacement county story"
    assert len(fake.messages.calls) == 2


def test_hero_semantic_dedup_preserves_deterministic_result_after_invalid_responses(monkeypatch):
    generate = _load_generate_module()
    fake = _SequenceClient(["", "still not json"])
    monkeypatch.setattr(generate, "client", fake)

    top = {
        "category_key": "crime",
        "category_label": "Crime & Safety",
        "hero": {"headline": "Alpha lead story"},
        "cards": [],
    }
    other = {
        "category_key": "martin",
        "category_label": "Martin County",
        "hero": {"headline": "Independent county story"},
        "cards": [{"headline": "Replacement county story"}],
    }

    generate.promote_duplicate_heroes(top, [top, other])

    assert other["hero"]["headline"] == "Independent county story"
    assert len(fake.messages.calls) == 2
