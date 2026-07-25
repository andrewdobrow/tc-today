"""Observe-only homepage ranking recommendations for controlled production rollout."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

RANKING_RECOMMENDATION_VERSION = "1.1"
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


def _iter_stories(registry: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    stories = registry.get("stories") or {}
    if isinstance(stories, Mapping):
        return [story for story in stories.values() if isinstance(story, Mapping)]
    if isinstance(stories, Sequence) and not isinstance(stories, (str, bytes)):
        return [story for story in stories if isinstance(story, Mapping)]
    return []


def _story_indexes(
    registry: Mapping[str, Any],
) -> tuple[
    dict[str, Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
]:
    by_id: dict[str, Mapping[str, Any]] = {}
    by_url: dict[str, Mapping[str, Any]] = {}
    by_title: dict[str, Mapping[str, Any]] = {}
    by_slug: dict[str, Mapping[str, Any]] = {}

    for story in _iter_stories(registry):
        story_id = str(story.get("story_id") or "").strip()
        if story_id:
            by_id[story_id] = story

        titles = [story.get("canonical_title", ""), story.get("title", "")]
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
            try:
                path = urlsplit(str(url or "")).path
                if path.endswith(".html"):
                    slug = path.rsplit("/", 1)[-1][:-5]
                    if slug:
                        by_slug.setdefault(slug, story)
            except ValueError:
                pass

        slugs = [story.get("canonical_slug", ""), story.get("slug", "")]
        slugs.extend(story.get("article_slugs") or [])
        for slug in slugs:
            slug = str(slug or "").strip()
            if slug:
                by_slug.setdefault(slug, story)

    return by_id, by_url, by_title, by_slug


def _archive_indexes(
    archive: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
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


def _explicit_story_id(item: Mapping[str, Any] | None) -> str:
    if not item:
        return ""
    for key in ("editorial_story_id", "story_id", "_story_id", "persistent_story_id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _resolve_story(
    card: Mapping[str, Any],
    *,
    by_id: Mapping[str, Mapping[str, Any]],
    by_url: Mapping[str, Mapping[str, Any]],
    by_title: Mapping[str, Mapping[str, Any]],
    by_slug: Mapping[str, Mapping[str, Any]],
    archive_by_slug: Mapping[str, Mapping[str, Any]],
    archive_by_title: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Any] | None, str, Mapping[str, Any] | None]:
    archive_entry = None
    slug = str(card.get("_archived_slug") or card.get("slug") or "").strip()
    if slug:
        archive_entry = archive_by_slug.get(slug)
    if archive_entry is None:
        archive_entry = archive_by_title.get(_norm_title(str(card.get("headline") or "")))

    for candidate in (card, archive_entry):
        story_id = _explicit_story_id(candidate)
        if story_id and story_id in by_id:
            return by_id[story_id], "persistent_story_id", archive_entry

    if slug and slug in by_slug:
        return by_slug[slug], "canonical_slug", archive_entry

    candidate_urls = [card.get("link", ""), card.get("source_url", ""), card.get("original_url", "")]
    if archive_entry:
        candidate_urls.extend([
            archive_entry.get("source_url", ""),
            archive_entry.get("link", ""),
            archive_entry.get("original_url", ""),
        ])
    for url in candidate_urls:
        story = by_url.get(_norm_url(str(url or "")))
        if story is not None:
            return story, "source_url", archive_entry

    candidate_titles = [card.get("headline", "")]
    if archive_entry:
        candidate_titles.append(archive_entry.get("headline", ""))
    for title in candidate_titles:
        story = by_title.get(_norm_title(str(title or "")))
        if story is not None:
            return story, "title", archive_entry
    return None, "unmatched", archive_entry


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


def _identity_key(
    card: Mapping[str, Any],
    story: Mapping[str, Any] | None,
    archive_entry: Mapping[str, Any] | None,
) -> tuple[str, str]:
    """Return a safe canonical identity for recommendation-only deduplication."""
    custom = bool(card.get("is_custom") or card.get("authoritative_custom"))
    slug = str(card.get("_archived_slug") or card.get("slug") or (archive_entry or {}).get("slug") or "").strip()
    if custom:
        # Custom articles are never collapsed into generated coverage merely because
        # the registry thinks they describe the same event.
        return (f"custom:{slug or _norm_title(str(card.get('headline') or ''))}", "custom_article")

    story_id = str((story or {}).get("story_id") or "").strip()
    if story_id:
        return (f"story:{story_id}", "persistent_story_id")

    for candidate in (card, archive_entry or {}):
        for key in ("source_url", "original_url", "link"):
            normalized = _norm_url(str(candidate.get(key) or ""))
            if normalized:
                return (f"source:{normalized}", "source_url")
    if slug:
        return (f"slug:{slug}", "canonical_slug")
    return (f"title:{_norm_title(str(card.get('headline') or ''))}", "normalized_title")


def build_homepage_ranking_recommendations(
    cards: Sequence[Mapping[str, Any]],
    hero: Mapping[str, Any] | None,
    *,
    registry: Mapping[str, Any],
    archive: Sequence[Mapping[str, Any]] = (),
    max_recommendations: int = 10,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return a deduplicated recommendation report without mutating cards or hero."""
    original_snapshot = deepcopy(list(cards))
    by_id, by_url, by_title, by_slug = _story_indexes(registry)
    archive_by_slug, archive_by_title = _archive_indexes(archive)

    unique_rows: list[dict[str, Any]] = []
    identity_to_row: dict[str, dict[str, Any]] = {}
    duplicate_placements: list[dict[str, Any]] = []

    for placement_position, card in enumerate(cards, start=1):
        story, match_basis, archive_entry = _resolve_story(
            card,
            by_id=by_id,
            by_url=by_url,
            by_title=by_title,
            by_slug=by_slug,
            archive_by_slug=archive_by_slug,
            archive_by_title=archive_by_title,
        )
        identity_key, identity_basis = _identity_key(card, story, archive_entry)
        if identity_key in identity_to_row:
            existing = identity_to_row[identity_key]
            existing["placement_count"] += 1
            existing["placement_categories"].append(str(card.get("cat_key") or card.get("category_key") or ""))
            duplicate_placements.append({
                "headline": str(card.get("headline") or ""),
                "placement_position": placement_position,
                "canonical_position": existing["current_position"],
                "identity": identity_key,
                "identity_basis": identity_basis,
            })
            continue

        score, breakdown = _score_card(card, story)
        current_position = len(unique_rows) + 1
        custom = bool(card.get("is_custom") or card.get("authoritative_custom"))
        pin_position = card.get("pin_position")
        position_locked = custom or bool(pin_position)
        row = {
            "current_position": current_position,
            "recommended_position": current_position,
            "first_placement_position": placement_position,
            "headline": str(card.get("headline") or ""),
            "category_key": str(card.get("cat_key") or card.get("category_key") or ""),
            "slug": str(card.get("_archived_slug") or card.get("slug") or (archive_entry or {}).get("slug") or ""),
            "story_id": str((story or {}).get("story_id") or ""),
            "score": score,
            "score_breakdown": breakdown,
            "match_basis": match_basis,
            "identity": identity_key,
            "identity_basis": identity_basis,
            "placement_count": 1,
            "placement_categories": [str(card.get("cat_key") or card.get("category_key") or "")],
            "pinned": bool(pin_position),
            "pin_position": pin_position,
            "custom": custom,
            "position_locked": position_locked,
            "position_lock_reason": "custom_article" if custom else ("pin_position" if pin_position else ""),
        }
        unique_rows.append(row)
        identity_to_row[identity_key] = row

    # Lock custom articles and explicitly pinned cards at their current unique-card
    # position. Recommendations must never use registry uncertainty to move manual work.
    locked_positions = {int(row["current_position"]): row for row in unique_rows if row["position_locked"]}
    movable = [row for row in unique_rows if not row["position_locked"]]
    movable.sort(key=lambda row: (-int(row["score"]), row["current_position"], row["headline"].lower()))

    recommended: list[dict[str, Any]] = []
    movable_iter = iter(movable)
    for position in range(1, len(unique_rows) + 1):
        row = locked_positions.get(position)
        if row is None:
            row = next(movable_iter, None)
        if row is None:
            continue
        row["recommended_position"] = position
        recommended.append(row)

    moves = [
        {
            "action": "recommend_reorder_card",
            "headline": row["headline"],
            "story_id": row["story_id"],
            "identity": row["identity"],
            "from_position": row["current_position"],
            "to_position": row["recommended_position"],
            "score": row["score"],
            "reason": row["score_breakdown"],
            "enforced": False,
        }
        for row in recommended
        if row["current_position"] != row["recommended_position"] and not row["position_locked"]
    ]
    moves.sort(key=lambda move: (abs(move["from_position"] - move["to_position"]), move["score"]), reverse=True)

    assert list(cards) == original_snapshot, "ranking recommendation builder mutated live cards"

    now = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    matched = sum(1 for row in unique_rows if row["story_id"])
    fallback = len(unique_rows) - matched
    return {
        "schema_version": 2,
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
            "custom_articles_position_locked": True,
            "custom_pin_positions_preserved": True,
            "deduplicate_cross_category_placements": True,
            "max_reported_recommendations": max_recommendations,
        },
        "summary": {
            "input_placements": len(cards),
            "unique_cards_observed": len(unique_rows),
            "cards_observed": len(unique_rows),
            "duplicate_placements_excluded": len(duplicate_placements),
            "registry_matches": matched,
            "fallback_scores": fallback,
            "registry_match_rate": round((matched / len(unique_rows)), 4) if unique_rows else 1.0,
            "recommended_moves": len(moves),
            "unchanged_positions": len(unique_rows) - len(moves),
            "reported_moves": min(len(moves), max_recommendations),
            "enforcement_readiness": "eligible_for_review" if (len(unique_rows) > 0 and matched / len(unique_rows) >= 0.8) else "not_ready",
            "enforcement_readiness_reason": (
                "At least 80% of unique cards matched persistent story IDs"
                if (len(unique_rows) > 0 and matched / len(unique_rows) >= 0.8)
                else "Fewer than 80% of unique cards matched persistent story IDs"
            ),
        },
        "current_order": [row["headline"] for row in sorted(unique_rows, key=lambda row: row["current_position"])],
        "recommended_order": [row["headline"] for row in sorted(recommended, key=lambda row: row["recommended_position"])],
        "recommendations": moves[:max_recommendations],
        "items": sorted(recommended, key=lambda row: row["recommended_position"]),
        "excluded_duplicate_placements": duplicate_placements,
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
