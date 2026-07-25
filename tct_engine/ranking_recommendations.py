"""Observe-only homepage ranking recommendations for controlled production rollout."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

RANKING_RECOMMENDATION_VERSION = "1.0"
RANKING_MODE = "recommend"


def _norm_title(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return " ".join(value.split())


def _norm_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw.lower().rstrip("/")
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"oc", "gclid", "fbclid"}
    ]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def _story_indexes(registry: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    by_url: dict[str, Mapping[str, Any]] = {}
    by_title: dict[str, Mapping[str, Any]] = {}
    stories = registry.get("stories") or {}
    iterable: Iterable[Mapping[str, Any]]
    if isinstance(stories, Mapping):
        iterable = [story for story in stories.values() if isinstance(story, Mapping)]
    elif isinstance(stories, Sequence):
        iterable = [story for story in stories if isinstance(story, Mapping)]
    else:
        iterable = []

    for story in iterable:
        titles = [story.get("canonical_title", "")]
        titles.extend(candidate.get("title", "") for candidate in story.get("title_candidates", []) if isinstance(candidate, Mapping))
        titles.extend(entry.get("title", "") for entry in story.get("timeline", []) if isinstance(entry, Mapping))
        for title in titles:
            normalized = _norm_title(str(title or ""))
            if normalized:
                by_title.setdefault(normalized, story)

        urls = list(story.get("sources") or [])
        urls.extend(entry.get("url", "") for entry in story.get("timeline", []) if isinstance(entry, Mapping))
        for url in urls:
            normalized = _norm_url(str(url or ""))
            if normalized:
                by_url.setdefault(normalized, story)
    return by_url, by_title


def _archive_indexes(archive: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    by_slug: dict[str, Mapping[str, Any]] = {}
    by_title: dict[str, Mapping[str, Any]] = {}
    for entry in archive:
        slug = str(entry.get("slug") or "").strip()
        if slug:
            by_slug[slug] = entry
        title = _norm_title(str(entry.get("headline") or ""))
        if title:
            by_title.setdefault(title, entry)
    return by_slug, by_title


def _resolve_story(
    card: Mapping[str, Any],
    *,
    by_url: Mapping[str, Mapping[str, Any]],
    by_title: Mapping[str, Mapping[str, Any]],
    archive_by_slug: Mapping[str, Mapping[str, Any]],
    archive_by_title: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Any] | None, str]:
    archive_entry = None
    slug = str(card.get("_archived_slug") or "").strip()
    if slug:
        archive_entry = archive_by_slug.get(slug)
    if archive_entry is None:
        archive_entry = archive_by_title.get(_norm_title(str(card.get("headline") or "")))

    candidate_urls = [card.get("link", ""), card.get("source_url", "")]
    if archive_entry:
        candidate_urls.extend([
            archive_entry.get("source_url", ""),
            archive_entry.get("link", ""),
            archive_entry.get("original_url", ""),
        ])
    for url in candidate_urls:
        story = by_url.get(_norm_url(str(url or "")))
        if story is not None:
            return story, "source_url"

    candidate_titles = [card.get("headline", "")]
    if archive_entry:
        candidate_titles.append(archive_entry.get("headline", ""))
    for title in candidate_titles:
        story = by_title.get(_norm_title(str(title or "")))
        if story is not None:
            return story, "title"
    return None, "unmatched"


def _score_card(card: Mapping[str, Any], story: Mapping[str, Any] | None) -> tuple[int, dict[str, Any]]:
    if story is not None:
        score = int(story.get("editorial_score", story.get("editorial_priority", 0)) or 0)
        breakdown = deepcopy(story.get("score_breakdown") or {})
        breakdown.setdefault("score", score)
        breakdown["basis"] = "persistent_story_registry"
        return score, breakdown

    urgency = max(0, min(10, int(card.get("urgency_score", 0) or 0)))
    score = urgency * 8
    if card.get("is_custom") or card.get("authoritative_custom"):
        score = min(100, score + 10)
    return score, {
        "score": score,
        "basis": "live_urgency_fallback",
        "urgency_score": urgency,
    }


def build_homepage_ranking_recommendations(
    cards: Sequence[Mapping[str, Any]],
    hero: Mapping[str, Any] | None,
    *,
    registry: Mapping[str, Any],
    archive: Sequence[Mapping[str, Any]] = (),
    max_recommendations: int = 10,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return a recommendation report without mutating cards or hero."""
    original_snapshot = deepcopy(list(cards))
    by_url, by_title = _story_indexes(registry)
    archive_by_slug, archive_by_title = _archive_indexes(archive)

    rows: list[dict[str, Any]] = []
    for current_position, card in enumerate(cards, start=1):
        story, match_basis = _resolve_story(
            card,
            by_url=by_url,
            by_title=by_title,
            archive_by_slug=archive_by_slug,
            archive_by_title=archive_by_title,
        )
        score, breakdown = _score_card(card, story)
        rows.append({
            "current_position": current_position,
            "recommended_position": current_position,
            "headline": str(card.get("headline") or ""),
            "category_key": str(card.get("cat_key") or card.get("category_key") or ""),
            "slug": str(card.get("_archived_slug") or ""),
            "story_id": str((story or {}).get("story_id") or ""),
            "score": score,
            "score_breakdown": breakdown,
            "match_basis": match_basis,
            "pinned": bool(card.get("pin_position")),
            "pin_position": card.get("pin_position"),
            "custom": bool(card.get("is_custom") or card.get("authoritative_custom")),
        })

    pinned_positions = {
        int(row["pin_position"]): row
        for row in rows
        if row.get("pin_position") and str(row.get("pin_position")).isdigit()
    }
    unpinned = [row for row in rows if not row.get("pinned")]
    unpinned.sort(key=lambda row: (-int(row["score"]), row["current_position"], row["headline"].lower()))

    recommended: list[dict[str, Any]] = []
    unpinned_iter = iter(unpinned)
    for position in range(1, len(rows) + 1):
        if position in pinned_positions:
            row = pinned_positions[position]
        else:
            row = next(unpinned_iter, None)
            if row is None:
                remaining = [candidate for candidate in rows if candidate not in recommended]
                row = remaining[0] if remaining else None
        if row is None:
            continue
        row["recommended_position"] = position
        recommended.append(row)

    moves = [
        {
            "action": "recommend_reorder_card",
            "headline": row["headline"],
            "story_id": row["story_id"],
            "from_position": row["current_position"],
            "to_position": row["recommended_position"],
            "score": row["score"],
            "reason": row["score_breakdown"],
            "enforced": False,
        }
        for row in recommended
        if row["current_position"] != row["recommended_position"] and not row["pinned"]
    ]
    moves.sort(key=lambda move: (abs(move["from_position"] - move["to_position"]), move["score"]), reverse=True)

    assert list(cards) == original_snapshot, "ranking recommendation builder mutated live cards"

    now = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "schema_version": 1,
        "version": RANKING_RECOMMENDATION_VERSION,
        "mode": RANKING_MODE,
        "generated_at": now,
        "publication_behavior_changed": False,
        "hero": {
            "headline": str((hero or {}).get("headline") or ""),
            "observe_only": True,
            "changed": False,
        },
        "controls": {
            "hero_changes_enabled": False,
            "card_reordering_enabled": False,
            "custom_pin_positions_preserved": True,
            "max_reported_recommendations": max_recommendations,
        },
        "summary": {
            "cards_observed": len(rows),
            "registry_matches": sum(1 for row in rows if row["story_id"]),
            "fallback_scores": sum(1 for row in rows if not row["story_id"]),
            "recommended_moves": len(moves),
            "reported_moves": min(len(moves), max_recommendations),
        },
        "current_order": [row["headline"] for row in sorted(rows, key=lambda row: row["current_position"])],
        "recommended_order": [row["headline"] for row in sorted(recommended, key=lambda row: row["recommended_position"])],
        "recommendations": moves[:max_recommendations],
        "items": sorted(recommended, key=lambda row: row["recommended_position"]),
    }


def write_homepage_ranking_recommendations(
    cards: Sequence[Mapping[str, Any]],
    hero: Mapping[str, Any] | None,
    *,
    registry_path: Path,
    archive: Sequence[Mapping[str, Any]],
    output_path: Path,
    max_recommendations: int = 10,
) -> dict[str, Any]:
    registry = _load_json(Path(registry_path), {})
    report = build_homepage_ranking_recommendations(
        cards,
        hero,
        registry=registry,
        archive=archive,
        max_recommendations=max_recommendations,
    )
    _atomic_write_json(Path(output_path), report)
    return report
