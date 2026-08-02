#!/usr/bin/env python3
"""Sanitize persistent generation-cache entries before tests or publication.

The GitHub Actions cache can restore an older ``data/generation-cache.json``
after checkout. That restored file must be treated as untrusted generated state:
new editorial integrity rules have to be applied before pytest or the publisher
can reuse any cached category output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CACHE_INTEGRITY_VERSION = "v1.13.0.3-source-focus-cache-integrity"
DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "generation-cache.json"

# One-time migrations for cache rows known to have crossed source focus before the
# universal guard existed. General future protection comes from the versioned
# category key and live cached-output validation in ``scripts/generate.py``.
_KNOWN_INVALID_SOURCE_FOCUS_RULES = (
    {
        "source_path_fragment": "/florida-sharks-caught-on-video-off-shore",
        "forbidden_headline_terms": (
            "ordinance",
            "commissioners",
            "state order",
            "state directive",
        ),
    },
)

# These words carry little event identity. Removing them makes the comparison
# about the publisher story's central action, actors, and location.
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "by", "for",
    "from", "has", "have", "in", "into", "is", "it", "its", "of", "on", "or",
    "that", "the", "their", "this", "to", "was", "were", "will", "with",
}


@dataclass(frozen=True)
class CacheSanitizationResult:
    removed_category_keys: tuple[str, ...]
    removed_headlines: tuple[str, ...]
    changed: bool


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _first_paragraph(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    return re.split(r"\n\s*\n|<\/p>|<br\s*\/?>", str(value or ""), maxsplit=1, flags=re.I)[0].strip()


def _opening_focus(value: Any, *, max_sentences: int = 2, max_words: int = 80) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
        if part.strip()
    ]
    focused = " ".join(sentences[:max_sentences]) if sentences else text
    return " ".join(focused.split()[:max_words])


def _tokens(value: Any) -> set[str]:
    words = re.findall(r"[a-z0-9]+", str(value or "").lower())
    return {
        word[:-1] if len(word) > 4 and word.endswith("s") else word
        for word in words
        if len(word) > 1 and word not in _STOP_WORDS
    }


def cached_item_source_focus_drift(item: Any) -> bool:
    """Return True only for high-confidence cached source-focus abandonment.

    This mirrors the production source-focus guard but stays stdlib-only so it
    can run immediately after Actions restores the cache and before package
    imports or pytest collection.
    """
    if not isinstance(item, dict):
        return False
    if item.get("is_custom") or item.get("authoritative_custom"):
        return False

    generated_headline = str(item.get("headline") or item.get("title") or "").strip()
    generated_lead = _opening_focus(_first_paragraph(item.get("body") or item.get("teaser") or ""))
    source_title = str(
        item.get("source_title")
        or item.get("source_headline")
        or ""
    ).strip()
    source_text = str(
        item.get("article_text")
        or item.get("source_text")
        or item.get("source_summary")
        or ""
    ).strip()
    source_lead = _opening_focus(source_text)

    generated_title_tokens = _tokens(generated_headline)
    source_title_tokens = _tokens(source_title)
    generated_lead_tokens = _tokens(generated_lead)
    source_lead_tokens = _tokens(source_lead)

    required = bool(
        generated_headline
        and generated_lead
        and len(source_title_tokens) >= 5
        and len(source_lead_tokens) >= 8
        and len(re.findall(r"\b\w+\b", source_text)) >= 35
    )
    if not required:
        return False

    title_denominator = min(len(generated_title_tokens), len(source_title_tokens))
    title_shared = generated_title_tokens & source_title_tokens
    title_score = len(title_shared) / title_denominator if title_denominator else 0.0

    lead_denominator = min(len(generated_lead_tokens), len(source_lead_tokens))
    lead_shared = generated_lead_tokens & source_lead_tokens
    lead_score = len(lead_shared) / lead_denominator if lead_denominator else 0.0

    return bool(title_score < 0.38 and len(title_shared) <= 3 and lead_score < 0.30)


def _matches_known_invalid_source_focus(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    source_url = str(item.get("source_url") or item.get("link") or "").lower()
    headline = str(item.get("headline") or item.get("title") or "").lower()
    for rule in _KNOWN_INVALID_SOURCE_FOCUS_RULES:
        if rule["source_path_fragment"] not in source_url:
            continue
        if any(term in headline for term in rule["forbidden_headline_terms"]):
            return True
    return False


def sanitize_cache_payload(payload: Any) -> tuple[dict[str, Any], CacheSanitizationResult]:
    """Remove unsafe category outputs and stamp the active integrity version."""
    if not isinstance(payload, dict):
        payload = {}
    categories = payload.get("categories")
    if not isinstance(categories, dict):
        categories = {}
        payload["categories"] = categories

    removed_keys: list[str] = []
    removed_headlines: list[str] = []

    for cache_key, entry in list(categories.items()):
        data = (((entry or {}).get("value") or {}).get("data") or {}) if isinstance(entry, dict) else {}
        items = []
        hero = data.get("hero") if isinstance(data, dict) else None
        if isinstance(hero, dict):
            items.append(hero)
        cards = data.get("cards") if isinstance(data, dict) else None
        if isinstance(cards, list):
            items.extend(card for card in cards if isinstance(card, dict))

        drifted = [item for item in items if _matches_known_invalid_source_focus(item)]
        if not drifted:
            continue

        categories.pop(cache_key, None)
        removed_keys.append(str(cache_key))
        removed_headlines.extend(
            str(item.get("headline") or item.get("title") or "").strip()
            for item in drifted
        )

    previous_version = str(payload.get("cache_integrity_version") or "")
    payload["cache_integrity_version"] = CACHE_INTEGRITY_VERSION
    changed = bool(removed_keys or previous_version != CACHE_INTEGRITY_VERSION)
    if changed:
        payload["updated_at"] = _utc_now_iso()

    return payload, CacheSanitizationResult(
        removed_category_keys=tuple(removed_keys),
        removed_headlines=tuple(removed_headlines),
        changed=changed,
    )


def sanitize_cache_file(path: Path = DEFAULT_CACHE_PATH) -> CacheSanitizationResult:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {"schema_version": 1, "categories": {}}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Generation cache is invalid JSON: {path}: {exc}") from exc

    sanitized, result = sanitize_cache_payload(payload)
    if result.changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(sanitized, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_CACHE_PATH)
    args = parser.parse_args()

    result = sanitize_cache_file(args.path)
    if result.removed_category_keys:
        print(
            "Generation cache integrity: removed "
            f"{len(result.removed_category_keys)} unsafe category entr"
            f"{'y' if len(result.removed_category_keys) == 1 else 'ies'}."
        )
        for headline in result.removed_headlines:
            print(f"  - {headline}")
    elif result.changed:
        print("Generation cache integrity: stamped current integrity version; no unsafe entries found.")
    else:
        print("Generation cache integrity: already clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
