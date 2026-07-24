"""Deterministic repair of legacy persistent-story registry corruption.

The repair is intentionally conservative. It quarantines story records that
were created by known unsafe generic event keys or by unsupported sparse-key
merges, then folds only exact identity duplicates back together.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import itertools
import re
from typing import Any, Iterable, Mapping, MutableMapping

REPAIR_VERSION = 1

_LEGACY_GENERIC_EVENT_KEYS = frozenset({"unknown-event", "fire", "traffic-crash"})
_HASH_SUFFIX_RE = re.compile(r"-[0-9a-f]{10}$")
_WORD_RE = re.compile(r"[a-z0-9]+")
_STORY_ID_RE = re.compile(r"(\d+)$")
_GENERIC_TITLE_TOKENS = frozenset(
    {
        "the", "and", "for", "with", "after", "from", "that", "this", "into",
        "over", "says", "said", "new", "county", "florida", "man", "woman",
        "arrest", "arrested", "made", "home", "story", "news", "local",
        "report", "reported", "officials", "following", "police", "wptv", "wpbf",
        "wpec", "aol", "msn", "treasure", "coast", "fort", "pierce", "lucie",
        "martin", "indian", "river", "palm", "city", "stuart", "vero", "beach",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_title(value: object) -> str:
    return " ".join(_WORD_RE.findall(str(value or "").casefold()))


def _title_tokens(value: object) -> set[str]:
    return {
        token
        for token in _WORD_RE.findall(str(value or "").casefold())
        if (len(token) >= 3 or token.isdigit()) and token not in _GENERIC_TITLE_TOKENS
    }


def is_sparse_event_key(event_key: object) -> bool:
    value = str(event_key or "").strip().casefold()
    return bool(
        value in _LEGACY_GENERIC_EVENT_KEYS
        or value.startswith("unknown-event-")
        or _HASH_SUFFIX_RE.search(value)
    )


def _pair_overlap(left: str, right: str) -> float:
    a = _title_tokens(left)
    b = _title_tokens(right)
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def _shared_title_anchors(titles: Iterable[str]) -> set[str]:
    token_sets = [_title_tokens(title) for title in titles if str(title or "").strip()]
    if not token_sets:
        return set()
    return set.intersection(*token_sets)


def _sparse_story_is_incoherent(story: Mapping[str, Any]) -> bool:
    events = [str(value) for value in story.get("events", ()) if str(value).strip()]
    titles = [str(value) for value in story.get("titles", ()) if str(value).strip()]
    if len(events) < 2 or len(titles) < 2 or not all(is_sparse_event_key(key) for key in events):
        return False

    anchors = _shared_title_anchors(titles)
    overlaps = [_pair_overlap(a, b) for a, b in itertools.combinations(titles, 2)]
    average_overlap = sum(overlaps) / len(overlaps) if overlaps else 1.0
    return len(anchors) < 2 and average_overlap < 0.40


def story_quarantine_reasons(story: Mapping[str, Any]) -> tuple[str, ...]:
    events = [str(value) for value in story.get("events", ()) if str(value).strip()]
    titles = list(story.get("titles", ()) or ())
    timeline = list(story.get("timeline", ()) or ())
    reasons: list[str] = []

    if any(event in _LEGACY_GENERIC_EVENT_KEYS for event in events):
        reasons.append("legacy_unsuffixed_generic_event_key")

    if len(titles) >= 8 and len(titles) > 4 * max(1, len(timeline)):
        reasons.append("impossible_title_fanout")

    if _sparse_story_is_incoherent(story):
        reasons.append("unsupported_sparse_event_merge")

    return tuple(reasons)


def _story_number(story_id: str) -> int:
    match = _STORY_ID_RE.search(story_id)
    return int(match.group(1)) if match else 10**12


def _canonical_candidate_priority(story: Mapping[str, Any]) -> tuple[int, int, int]:
    candidates = list(story.get("title_candidates", ()) or ())
    return max(
        (
            int(bool(candidate.get("is_custom", False))),
            int(candidate.get("priority", 0) or 0),
            int(candidate.get("source_trust", 0) or 0),
        )
        for candidate in candidates
    ) if candidates else (int(story.get("custom_article_count", 0) or 0) > 0, 0, 0)


def choose_primary_story_id(story_ids: Iterable[str], stories: Mapping[str, Mapping[str, Any]]) -> str:
    ids = sorted(set(story_ids))
    return max(
        ids,
        key=lambda story_id: (
            *_canonical_candidate_priority(stories[story_id]),
            -_story_number(story_id),
        ),
    )


def _unique_dicts(values: Iterable[Mapping[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    result: list[dict[str, Any]] = []
    for value in values:
        item = dict(value)
        key = tuple(str(item.get(field, "")) for field in fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _select_canonical_title(story: MutableMapping[str, Any]) -> str:
    candidates = list(story.get("title_candidates", ()) or ())
    if candidates:
        best = max(
            candidates,
            key=lambda item: (
                int(bool(item.get("is_custom", False))),
                int(item.get("priority", 0) or 0),
                int(item.get("source_trust", 0) or 0),
                len(str(item.get("title", ""))),
            ),
        )
        title = str(best.get("title", "")).strip()
        if title:
            return title
    existing = str(story.get("canonical_title", "")).strip()
    if existing:
        return existing
    titles = list(story.get("titles", ()) or ())
    return str(titles[0]).strip() if titles else ""


def merge_story_records(primary: MutableMapping[str, Any], secondary: Mapping[str, Any]) -> None:
    for field in (
        "events", "titles", "title_tokens", "fact_tokens", "facts", "locations",
        "agencies", "event_types", "entities", "sources",
    ):
        primary[field] = sorted(
            {str(value) for value in primary.get(field, ()) if str(value).strip()}
            | {str(value) for value in secondary.get(field, ()) if str(value).strip()}
        )

    primary["title_candidates"] = _unique_dicts(
        [*primary.get("title_candidates", ()), *secondary.get("title_candidates", ())],
        ("title", "source", "source_class", "source_trust", "is_custom", "priority"),
    )
    primary["timeline"] = _unique_dicts(
        [*primary.get("timeline", ()), *secondary.get("timeline", ())],
        ("event_key", "article_id", "url", "title"),
    )
    primary["resolution_history"] = _unique_dicts(
        [*primary.get("resolution_history", ()), *secondary.get("resolution_history", ())],
        ("event_key", "relationship", "confidence", "reason"),
    )
    primary["relationship_history"] = _unique_dicts(
        [*primary.get("relationship_history", ()), *secondary.get("relationship_history", ())],
        ("event_key", "relationship", "confidence", "reason"),
    )
    primary["lifecycle_history"] = _unique_dicts(
        [*primary.get("lifecycle_history", ()), *secondary.get("lifecycle_history", ())],
        ("from", "to", "last_updated", "reason"),
    )

    locality_candidates = [primary.get("local_relevance") or {}, secondary.get("local_relevance") or {}]
    primary["local_relevance"] = dict(
        max(locality_candidates, key=lambda item: int(item.get("score", 0) or 0))
    )
    primary["custom_article_count"] = sum(
        1 for candidate in primary.get("title_candidates", ()) if bool(candidate.get("is_custom", False))
    )
    primary["canonical_title"] = _select_canonical_title(primary)


@dataclass(frozen=True, slots=True)
class RegistryRepairReport:
    repair_version: int
    changed: bool
    active_stories_before: int
    active_stories_after: int
    quarantined_story_ids: tuple[str, ...]
    quarantine_reasons: Mapping[str, tuple[str, ...]]
    duplicate_groups_merged: int
    duplicate_story_records_removed: int
    merged_story_ids: Mapping[str, tuple[str, ...]]
    remaining_exact_duplicate_title_groups: int
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "repair_version": self.repair_version,
            "changed": self.changed,
            "status": "repaired" if self.changed else "clean",
            "active_stories_before": self.active_stories_before,
            "active_stories_after": self.active_stories_after,
            "quarantined_story_count": len(self.quarantined_story_ids),
            "quarantined_story_ids": list(self.quarantined_story_ids),
            "quarantine_reasons": {
                story_id: list(reasons) for story_id, reasons in self.quarantine_reasons.items()
            },
            "duplicate_groups_merged": self.duplicate_groups_merged,
            "duplicate_story_records_removed": self.duplicate_story_records_removed,
            "merged_story_ids": {
                primary: list(merged) for primary, merged in self.merged_story_ids.items()
            },
            "remaining_exact_duplicate_title_groups": self.remaining_exact_duplicate_title_groups,
            "generated_at": self.generated_at,
        }


def _duplicate_components(stories: Mapping[str, Mapping[str, Any]]) -> list[set[str]]:
    parent = {story_id: story_id for story_id in stories}

    def find(story_id: str) -> str:
        while parent[story_id] != story_id:
            parent[story_id] = parent[parent[story_id]]
            story_id = parent[story_id]
        return story_id

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    title_index: dict[str, list[str]] = {}
    event_index: dict[str, list[str]] = {}
    for story_id, story in stories.items():
        titles = [story.get("canonical_title", ""), *story.get("titles", ())]
        for title in titles:
            normalized = normalize_title(title)
            if len(normalized.split()) >= 4:
                title_index.setdefault(normalized, []).append(story_id)
        for event_key in story.get("events", ()):
            value = str(event_key or "").strip()
            if value:
                event_index.setdefault(value, []).append(story_id)

    for group in (*title_index.values(), *event_index.values()):
        unique = sorted(set(group))
        for story_id in unique[1:]:
            union(unique[0], story_id)

    components: dict[str, set[str]] = {}
    for story_id in stories:
        components.setdefault(find(story_id), set()).add(story_id)
    return [component for component in components.values() if len(component) > 1]


def _count_exact_duplicate_title_groups(stories: Mapping[str, Mapping[str, Any]]) -> int:
    title_index: dict[str, set[str]] = {}
    for story_id, story in stories.items():
        for title in [story.get("canonical_title", ""), *story.get("titles", ())]:
            normalized = normalize_title(title)
            if len(normalized.split()) >= 4:
                title_index.setdefault(normalized, set()).add(story_id)
    return sum(1 for story_ids in title_index.values() if len(story_ids) > 1)


def repair_registry_payload(payload: MutableMapping[str, Any]) -> RegistryRepairReport:
    stories: MutableMapping[str, MutableMapping[str, Any]] = payload.setdefault("stories", {})
    aliases: MutableMapping[str, str] = payload.setdefault("story_aliases", {})
    quarantined: MutableMapping[str, Any] = payload.setdefault("quarantined_stories", {})
    before = len(stories)

    quarantine_reasons: dict[str, tuple[str, ...]] = {}
    for story_id, story in list(stories.items()):
        reasons = story_quarantine_reasons(story)
        if not reasons:
            continue
        quarantine_reasons[story_id] = reasons
        snapshot = dict(story)
        snapshot["quarantined_at"] = _utc_now()
        snapshot["quarantine_reasons"] = list(reasons)
        snapshot["repair_version"] = REPAIR_VERSION
        quarantined[story_id] = snapshot
        del stories[story_id]

    quarantined_ids = set(quarantine_reasons)
    for alias, target in list(aliases.items()):
        if alias in quarantined_ids or target in quarantined_ids:
            del aliases[alias]

    merged_story_ids: dict[str, tuple[str, ...]] = {}
    components = _duplicate_components(stories)
    for component in sorted(components, key=lambda group: min(_story_number(value) for value in group)):
        primary_id = choose_primary_story_id(component, stories)
        secondary_ids = sorted(component - {primary_id}, key=_story_number)
        primary = stories[primary_id]
        for secondary_id in secondary_ids:
            merge_story_records(primary, stories[secondary_id])
            aliases[secondary_id] = primary_id
            del stories[secondary_id]
        merged_story_ids[primary_id] = tuple(secondary_ids)

    # Rebuild the event index from active records only. Quarantined records never
    # retain active mappings, and aliases are resolved to their chosen primary.
    event_to_story: dict[str, str] = {}
    for story_id, story in stories.items():
        for event_key in story.get("events", ()):
            value = str(event_key or "").strip()
            if value:
                event_to_story[value] = story_id
    payload["event_to_story"] = event_to_story

    removed = sum(len(values) for values in merged_story_ids.values())
    remaining_duplicates = _count_exact_duplicate_title_groups(stories)
    report = RegistryRepairReport(
        repair_version=REPAIR_VERSION,
        changed=bool(quarantine_reasons or removed),
        active_stories_before=before,
        active_stories_after=len(stories),
        quarantined_story_ids=tuple(sorted(quarantine_reasons, key=_story_number)),
        quarantine_reasons=quarantine_reasons,
        duplicate_groups_merged=len(merged_story_ids),
        duplicate_story_records_removed=removed,
        merged_story_ids=merged_story_ids,
        remaining_exact_duplicate_title_groups=remaining_duplicates,
        generated_at=_utc_now(),
    )

    repair_state = payload.setdefault("registry_repair", {})
    history = list(repair_state.get("history", ()) or ())
    history.append(report.to_dict())
    repair_state["version"] = REPAIR_VERSION
    repair_state["last_run"] = report.to_dict()
    repair_state["history"] = history[-10:]
    return report
