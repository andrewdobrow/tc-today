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

from .incident_identity import (
    build_story_incident_signature,
    compare_incident_signatures,
    named_person_death_subjects,
    timeline_incident_anchor,
)
from .timeline_coherence import (
    analyze_story_timeline_coherence,
    infer_timeline_event_family,
    registry_timeline_coherence_violations,
    timeline_entries_have_continuity,
    timeline_entry_source_identity,
    timeline_title_tokens,
)
from .source_identity import (
    source_identity_requires_title_continuity,
    source_identity_title_compatible,
    story_identity_titles,
    story_source_identity_urls,
)

REPAIR_VERSION = 8

_LEGACY_GENERIC_EVENT_KEYS = frozenset({"unknown-event", "fire", "traffic-crash"})
_HASH_SUFFIX_RE = re.compile(r"-[0-9a-f]{10}$")

_BROAD_EVENT_PREFIXES = ("traffic-crash-", "fire-")
_BROAD_NAMED_DEATH_LOCATION_TOKENS = frozenset({
    "avenue", "beach", "boulevard", "bridge", "circle", "county",
    "drive", "highway", "interstate", "lane", "parkway", "road",
    "street", "trail", "turnpike", "way", "fort", "pierce", "stuart",
    "vero", "sebastian", "lucie", "martin", "river", "florida",
    "north", "south", "east", "west", "northeast", "northwest",
    "southeast", "southwest", "state", "us",
})
_DIRECTION_TOKENS = frozenset({
    "north", "south", "east", "west", "northeast", "northwest",
    "southeast", "southwest",
})


def is_broad_event_class_key(event_key: object) -> bool:
    """Return True when a key describes an event class, not one incident.

    City/county crash and fire keys were historically treated as canonical
    identity.  That allowed every crash in one jurisdiction to inherit one
    persistent story.  These keys may still be retained as descriptive metadata,
    but they must never own an ``event_to_story`` mapping or authorize a merge.
    """
    value = str(event_key or "").strip().casefold()
    if not value:
        return False
    if value.startswith(_BROAD_EVENT_PREFIXES):
        # v1.12.0.8 appends a ten-character source/article hash to crash and
        # fire keys. Those keys identify one incident; only the unsuffixed
        # jurisdiction-level class remains broad.
        return _HASH_SUFFIX_RE.search(value) is None
    if value.startswith("named-person-death:"):
        subject = value.split(":", 1)[1]
        ordered_tokens = tuple(token for token in subject.split("-") if token)
        tokens = set(ordered_tokens)
        # A location-only subject (or a truncated street beginning with a
        # direction) is not a named person. Do not reject a real surname merely
        # because it is also a county name, e.g. ``marie-martin``.
        if tokens and tokens <= _BROAD_NAMED_DEATH_LOCATION_TOKENS:
            return True
        if ordered_tokens and ordered_tokens[0] in _DIRECTION_TOKENS:
            return True
    return False
_WORD_RE = re.compile(r"[a-z0-9]+")

_PUBLISHER_SUFFIX_RE = re.compile(
    r"^(?P<head>.+?)\s+(?:-|–|—|\|)\s+(?P<tail>[^|–—]{2,80})\s*$"
)
_PUBLISHER_DOMAIN_RE = re.compile(r"^[a-z0-9.-]+\.(?:com|org|net|news|tv)$", re.IGNORECASE)
_PUBLISHER_ACRONYM_RE = re.compile(r"^[A-Z0-9]{2,8}$")
_PUBLISHER_ENDINGS = frozenset(
    {
        "news", "network", "post", "press", "record", "sentinel", "times",
        "tribune", "journal", "herald", "observer", "courier", "living",
    }
)
_KNOWN_PUBLISHER_SUFFIXES = frozenset(
    {
        "aol", "aol.com", "cw34.com", "fox23.com", "hometown news treasure coast",
        "ksnb", "kktv", "latestly", "msn", "mynbc15.com", "nfhs network",
        "southern living", "the times of india", "treasure coast news", "wcti",
        "wflx", "wpbf", "wpec", "wptv", "wrdw", "wxii", "yahoo",
    }
)
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


def strip_publisher_suffix(value: object) -> str:
    """Remove a trailing publisher attribution without changing display copy.

    Google News commonly emits the same headline as ``Headline - WPTV`` and
    ``Headline - WFLX``. The suffix is identity noise, but ordinary headline
    subtitles such as ``Budget workshop - what residents should know`` must
    remain intact.
    """

    title = str(value or "").strip()
    match = _PUBLISHER_SUFFIX_RE.match(title)
    if not match:
        return title

    head = match.group("head").strip()
    tail = match.group("tail").strip().strip(".")
    folded = tail.casefold()
    words = [word for word in _WORD_RE.findall(folded) if word]
    publisher_like = bool(
        folded in _KNOWN_PUBLISHER_SUFFIXES
        or _PUBLISHER_DOMAIN_RE.fullmatch(tail)
        or _PUBLISHER_ACRONYM_RE.fullmatch(tail)
        or (words and len(words) <= 6 and words[-1] in _PUBLISHER_ENDINGS)
    )
    return head if publisher_like and len(normalize_title(head).split()) >= 4 else title


def normalize_identity_title(value: object) -> str:
    """Normalize a title for deterministic cross-feed identity matching."""

    return normalize_title(strip_publisher_suffix(value))


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
        or is_broad_event_class_key(value)
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


def _broad_event_story_is_incoherent(story: Mapping[str, Any]) -> bool:
    events = [str(value) for value in story.get("events", ()) if str(value).strip()]
    titles = [str(value) for value in story.get("titles", ()) if str(value).strip()]
    if not any(is_broad_event_class_key(key) for key in events) or len(titles) < 4:
        return False

    # Treat syndicated/reworded titles as a graph. A legitimate incident should
    # remain connected through at least one specific title anchor. Multiple
    # disconnected clusters under one city-level crash/fire key indicate that the
    # key merged separate incidents.
    parent = list(range(len(titles)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    for left, right in itertools.combinations(range(len(titles)), 2):
        if _pair_overlap(titles[left], titles[right]) >= 0.30:
            union(left, right)
    components = {find(index) for index in range(len(titles))}
    return len(components) > 1


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

    if _broad_event_story_is_incoherent(story):
        reasons.append("broad_event_class_multi_incident")

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
    publisher_title_duplicate_groups_resolved: int
    remaining_publisher_title_duplicate_groups: int
    source_identity_groups_resolved: int
    source_story_records_removed: int
    remaining_source_identity_groups: int
    incident_identity_groups_resolved: int
    incident_story_records_removed: int
    remaining_incident_identity_groups: int
    selective_incident_anchor_groups_repaired: int
    selective_timeline_entries_moved: int
    contaminated_story_records_preserved: int
    timeline_coherence_story_records_repaired: int
    timeline_coherence_entries_detached: int
    timeline_coherence_new_story_ids: tuple[str, ...]
    remaining_timeline_coherence_violations: int
    timeline_coherence_violation_story_ids: tuple[str, ...]
    incident_anchor_to_story_count: int
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
            "publisher_title_duplicate_groups_resolved": self.publisher_title_duplicate_groups_resolved,
            "remaining_publisher_title_duplicate_groups": self.remaining_publisher_title_duplicate_groups,
            "source_identity_groups_resolved": self.source_identity_groups_resolved,
            "source_story_records_removed": self.source_story_records_removed,
            "remaining_source_identity_groups": self.remaining_source_identity_groups,
            "incident_identity_groups_resolved": self.incident_identity_groups_resolved,
            "incident_story_records_removed": self.incident_story_records_removed,
            "remaining_incident_identity_groups": self.remaining_incident_identity_groups,
            "selective_incident_anchor_groups_repaired": self.selective_incident_anchor_groups_repaired,
            "selective_timeline_entries_moved": self.selective_timeline_entries_moved,
            "contaminated_story_records_preserved": self.contaminated_story_records_preserved,
            "timeline_coherence_story_records_repaired": self.timeline_coherence_story_records_repaired,
            "timeline_coherence_entries_detached": self.timeline_coherence_entries_detached,
            "timeline_coherence_new_story_ids": list(self.timeline_coherence_new_story_ids),
            "remaining_timeline_coherence_violations": self.remaining_timeline_coherence_violations,
            "timeline_coherence_violation_story_ids": list(self.timeline_coherence_violation_story_ids),
            "incident_anchor_to_story_count": self.incident_anchor_to_story_count,
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
            normalized = normalize_identity_title(title)
            if len(normalized.split()) >= 4:
                title_index.setdefault(normalized, []).append(story_id)
        for event_key in story.get("events", ()):
            value = str(event_key or "").strip()
            if value and not is_broad_event_class_key(value):
                event_index.setdefault(value, []).append(story_id)

    for group in (*title_index.values(), *event_index.values()):
        unique = sorted(set(group))
        for story_id in unique[1:]:
            union(unique[0], story_id)

    components: dict[str, set[str]] = {}
    for story_id in stories:
        components.setdefault(find(story_id), set()).add(story_id)
    return [component for component in components.values() if len(component) > 1]


def _incident_components(stories: Mapping[str, Mapping[str, Any]]) -> list[set[str]]:
    """Return conservative high-confidence incident identity components."""

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

    story_ids = sorted(stories, key=_story_number)
    signatures = {
        story_id: build_story_incident_signature(stories[story_id])
        for story_id in story_ids
    }
    # Named-person death anchors are repaired at timeline-entry granularity.
    # Whole-record merging would drag unrelated entries from already contaminated
    # stories into the canonical incident.
    supported_ids = [
        story_id
        for story_id in story_ids
        if signatures[story_id].supported
        and signatures[story_id].family != "named_person_death"
    ]
    for index, left_id in enumerate(supported_ids):
        for right_id in supported_ids[index + 1 :]:
            if compare_incident_signatures(signatures[left_id], signatures[right_id]).matched:
                union(left_id, right_id)

    components: dict[str, set[str]] = {}
    for story_id in story_ids:
        components.setdefault(find(story_id), set()).add(story_id)
    return [component for component in components.values() if len(component) > 1]



def _selective_named_person_death_repair(
    stories: MutableMapping[str, MutableMapping[str, Any]],
    aliases: MutableMapping[str, str],
) -> tuple[int, int, int, dict[str, str], dict[str, list[str]]]:
    """Consolidate anchored timeline entries without merging contamination.

    Legacy generic ``fire-<location>`` keys allowed unrelated fire, shots-fired,
    animal-rescue and firefighter-death entries to coexist in one story record.
    This repair moves only timeline entries carrying the exact named-person death
    anchor. Unrelated entries stay in their original story.
    """

    evidence: dict[str, dict[str, list[dict[str, Any]]]] = {}
    subjects_by_story: dict[str, tuple[str, ...]] = {}
    for story_id, story in stories.items():
        subjects = named_person_death_subjects(story)
        subjects_by_story[story_id] = subjects
        for entry in story.get("timeline", ()) or ():
            if not isinstance(entry, Mapping):
                continue
            anchor = timeline_incident_anchor(entry, inherited_subjects=subjects)
            if anchor:
                evidence.setdefault(anchor, {}).setdefault(story_id, []).append(dict(entry))

    groups_repaired = 0
    entries_moved = 0
    contaminated_preserved = 0
    anchor_to_story: dict[str, str] = {}
    moved_by_primary: dict[str, list[str]] = {}

    for anchor, by_story in sorted(evidence.items()):
        if len(by_story) < 2:
            only = next(iter(by_story), "")
            if only:
                anchor_to_story[anchor] = only
                stories[only].setdefault("incident_anchors", [])
                if anchor not in stories[only]["incident_anchors"]:
                    stories[only]["incident_anchors"].append(anchor)
            continue

        def _primary_key(story_id: str) -> tuple[float, int, int, int, int, int]:
            story = stories[story_id]
            matching = len(by_story[story_id])
            total = len(list(story.get("timeline", ()) or ()))
            purity = matching / total if total else 0.0
            custom, priority, trust = _canonical_candidate_priority(story)
            return (purity, matching, int(custom), priority, trust, -_story_number(story_id))

        primary_id = max(by_story, key=_primary_key)
        primary = stories[primary_id]
        primary.setdefault("incident_anchors", [])
        if anchor not in primary["incident_anchors"]:
            primary["incident_anchors"].append(anchor)
        primary["events"] = sorted(
            {str(value) for value in primary.get("events", ()) if str(value).strip()}
            | {anchor}
        )
        anchor_to_story[anchor] = primary_id
        moved_by_primary.setdefault(primary_id, [])

        for secondary_id in sorted(set(by_story) - {primary_id}, key=_story_number):
            if secondary_id not in stories:
                continue
            secondary = stories[secondary_id]
            secondary_subjects = subjects_by_story.get(secondary_id, ())
            moving_entries = by_story[secondary_id]
            moving_event_keys = {
                str(entry.get("event_key") or "").strip()
                for entry in moving_entries
                if str(entry.get("event_key") or "").strip()
            }
            moving_article_ids = {
                str(entry.get("article_id") or "").strip()
                for entry in moving_entries
                if str(entry.get("article_id") or "").strip()
            }

            primary["timeline"] = _unique_dicts(
                [*primary.get("timeline", ()), *moving_entries],
                ("event_key", "article_id", "url", "title"),
            )
            primary["events"] = sorted(
                {str(value) for value in primary.get("events", ()) if str(value).strip()}
                | moving_event_keys
            )

            def _title_anchor(value: object) -> str:
                return timeline_incident_anchor(
                    {"title": str(value or "")},
                    inherited_subjects=secondary_subjects,
                )

            moving_titles = [
                str(value)
                for value in secondary.get("titles", ())
                if _title_anchor(value) == anchor
            ]
            primary["titles"] = sorted(
                {str(value) for value in primary.get("titles", ()) if str(value).strip()}
                | set(moving_titles)
                | {str(entry.get("title") or "").strip() for entry in moving_entries if str(entry.get("title") or "").strip()}
            )

            moving_candidates = [
                dict(candidate)
                for candidate in secondary.get("title_candidates", ()) or ()
                if isinstance(candidate, Mapping)
                and _title_anchor(candidate.get("title")) == anchor
            ]
            primary["title_candidates"] = _unique_dicts(
                [*primary.get("title_candidates", ()), *moving_candidates],
                ("title", "source", "source_class", "source_trust", "is_custom", "priority"),
            )
            primary["sources"] = sorted(
                {str(value) for value in primary.get("sources", ()) if str(value).strip()}
                | {
                    str(entry.get("source") or entry.get("url") or "").strip()
                    for entry in moving_entries
                    if str(entry.get("source") or entry.get("url") or "").strip()
                }
            )

            remaining_timeline = [
                dict(entry)
                for entry in secondary.get("timeline", ()) or ()
                if not (
                    str(entry.get("article_id") or "").strip() in moving_article_ids
                    or str(entry.get("event_key") or "").strip() in moving_event_keys
                )
            ]
            secondary["timeline"] = remaining_timeline
            secondary["events"] = [
                value for value in secondary.get("events", ())
                if str(value or "").strip() not in moving_event_keys
            ]
            secondary["titles"] = [
                value for value in secondary.get("titles", ())
                if _title_anchor(value) != anchor
            ]
            secondary["title_candidates"] = [
                candidate
                for candidate in secondary.get("title_candidates", ()) or ()
                if not (
                    isinstance(candidate, Mapping)
                    and _title_anchor(candidate.get("title")) == anchor
                )
            ]
            secondary["sources"] = sorted(
                {
                    str(entry.get("source") or entry.get("url") or "").strip()
                    for entry in remaining_timeline
                    if str(entry.get("source") or entry.get("url") or "").strip()
                }
            )

            entries_moved += len(moving_entries)
            moved_by_primary[primary_id].append(secondary_id)
            if remaining_timeline:
                contaminated_preserved += 1
                secondary["identity_contamination_repaired"] = True
                secondary["detached_incident_anchor"] = anchor
                secondary["canonical_title"] = _select_canonical_title(secondary)
                # Remove the named subject when no remaining title refers to it.
                remaining_text = " ".join(
                    [
                        *[str(entry.get("title") or "") for entry in remaining_timeline],
                        *[str(value) for value in secondary.get("titles", ())],
                    ]
                ).casefold()
                secondary["entities"] = [
                    value
                    for value in secondary.get("entities", ())
                    if str(value or "").casefold() in remaining_text
                    or str(value or "").casefold() not in {
                        str(subject).casefold() for subject in secondary_subjects
                    }
                ]
            else:
                aliases[secondary_id] = primary_id
                del stories[secondary_id]

        primary["canonical_title"] = _select_canonical_title(primary)
        primary["custom_article_count"] = sum(
            1 for candidate in primary.get("title_candidates", ())
            if bool(candidate.get("is_custom", False))
        )
        groups_repaired += 1

    # Re-evaluate anchors after moves so clean one-story groups are indexed too.
    for story_id, story in stories.items():
        for anchor in story.get("incident_anchors", ()) or ():
            if str(anchor or "").strip():
                anchor_to_story[str(anchor)] = story_id
        subjects = named_person_death_subjects(story)
        for entry in story.get("timeline", ()) or ():
            if not isinstance(entry, Mapping):
                continue
            anchor = timeline_incident_anchor(entry, inherited_subjects=subjects)
            if anchor:
                anchor_to_story.setdefault(anchor, story_id)

    return groups_repaired, entries_moved, contaminated_preserved, anchor_to_story, moved_by_primary



def _component_candidate_matches(
    candidate: Mapping[str, Any], component: Iterable[Mapping[str, Any]]
) -> bool:
    candidate_entry = {
        "title": str(candidate.get("title") or ""),
        "source": str(candidate.get("source") or ""),
        "url": str(candidate.get("source") or ""),
    }
    return any(
        timeline_entries_have_continuity(candidate_entry, entry)
        for entry in component
    )


def _component_title_matches(
    title: object, component: Iterable[Mapping[str, Any]]
) -> bool:
    candidate_entry = {"title": str(title or "")}
    return any(
        timeline_entries_have_continuity(candidate_entry, entry)
        for entry in component
    )


def _event_family_label(family: str) -> str:
    return {
        "animal_rescue": "animal rescue",
        "dui": "dui",
        "execution": "execution",
        "fire": "fire",
        "government_finance": "government finance",
        "hazing": "hazing",
        "shooting": "shooting",
        "traffic_crash": "traffic crash",
        "death": "death",
    }.get(str(family or ""), "")


def _allocate_story_id(payload: MutableMapping[str, Any]) -> str:
    stories = payload.setdefault("stories", {})
    quarantined = payload.setdefault("quarantined_stories", {})
    next_number = int(payload.get("next_story_id", 1) or 1)
    while True:
        story_id = f"story_{next_number:06d}"
        next_number += 1
        if story_id not in stories and story_id not in quarantined:
            payload["next_story_id"] = next_number
            return story_id


def _component_record(
    original: Mapping[str, Any],
    component: Iterable[Mapping[str, Any]],
    *,
    story_id: str,
    preserve_local_relevance: bool,
    original_story_id: str,
) -> dict[str, Any]:
    entries = [dict(entry) for entry in component]
    event_keys = {
        str(entry.get("event_key") or "").strip()
        for entry in entries
        if str(entry.get("event_key") or "").strip()
    }
    entry_sources = {
        value
        for entry in entries
        for value in (
            str(entry.get("source") or "").strip(),
            str(entry.get("url") or "").strip(),
        )
        if value
    }
    titles = {
        str(entry.get("title") or "").strip()
        for entry in entries
        if str(entry.get("title") or "").strip()
    }
    titles.update(
        str(value).strip()
        for value in (original.get("titles", ()) or ())
        if str(value).strip() and _component_title_matches(value, entries)
    )
    candidates = [
        dict(candidate)
        for candidate in (original.get("title_candidates", ()) or ())
        if isinstance(candidate, Mapping)
        and _component_candidate_matches(candidate, entries)
    ]
    for entry in entries:
        title = str(entry.get("title") or "").strip()
        source = str(entry.get("source") or entry.get("url") or "").strip()
        if not title:
            continue
        if not any(
            normalize_identity_title(candidate.get("title"))
            == normalize_identity_title(title)
            and str(candidate.get("source") or "").strip() == source
            for candidate in candidates
        ):
            candidates.append(
                {
                    "title": title,
                    "source": source,
                    "source_class": "unknown",
                    "source_trust": 50,
                    "is_custom": False,
                    "priority": 50,
                }
            )

    sources = set(entry_sources)
    sources.update(
        str(candidate.get("source") or "").strip()
        for candidate in candidates
        if str(candidate.get("source") or "").strip()
    )
    incident_anchors = sorted(
        {
            str(anchor).strip()
            for anchor in (original.get("incident_anchors", ()) or ())
            if str(anchor).strip() in event_keys
        }
    )
    families = {
        infer_timeline_event_family(entry)
        for entry in entries
        if infer_timeline_event_family(entry) != "unknown"
    }
    event_types = sorted(
        label for label in (_event_family_label(family) for family in families) if label
    )
    resolution_history = [
        dict(row)
        for row in (original.get("resolution_history", ()) or ())
        if isinstance(row, Mapping)
        and str(row.get("event_key") or "").strip() in event_keys
    ]
    relationship_history = [
        dict(row)
        for row in (original.get("relationship_history", ()) or ())
        if isinstance(row, Mapping)
        and str(row.get("event_key") or "").strip() in event_keys
    ]
    title_tokens = sorted(
        {
            token
            for title in titles
            for token in timeline_title_tokens(title)
        }
    )

    record: dict[str, Any] = {
        "story_id": story_id,
        "events": sorted(event_keys),
        "status": "active",
        "lifecycle": {},
        "lifecycle_history": [],
        "titles": sorted(titles),
        "title_tokens": title_tokens,
        "fact_tokens": [],
        "facts": [],
        "locations": [],
        "agencies": [],
        "event_types": event_types,
        "entities": [],
        "local_relevance": (
            dict(original.get("local_relevance") or {})
            if preserve_local_relevance
            else {"scope": "unknown", "score": 35, "counties": [], "places": []}
        ),
        "resolution_history": resolution_history,
        "relationship_history": relationship_history,
        "editorial_proximity": (
            dict(original.get("editorial_proximity") or {})
            if preserve_local_relevance
            else {"score": 35, "scope": "unknown", "reason": "Not yet classified"}
        ),
        "editorial_priority": 0,
        "editorial_score": 0,
        "score_breakdown": {},
        "timeline": entries,
        "custom_article_count": sum(
            1 for candidate in candidates if bool(candidate.get("is_custom", False))
        ),
        "sources": sorted(sources),
        "title_candidates": _unique_dicts(
            candidates,
            ("title", "source", "source_class", "source_trust", "is_custom", "priority"),
        ),
        "canonical_title": "",
        "importance": {
            "score": 0,
            "level": "low",
            "reasons": [],
        },
        "identity_contamination_repaired": True,
        "timeline_coherence_repair": {
            "repair_version": REPAIR_VERSION,
            "original_story_id": original_story_id,
            "component_entry_count": len(entries),
            "reason": "incompatible_event_families_without_identity_continuity",
        },
    }
    if incident_anchors:
        record["incident_anchors"] = incident_anchors
    record["canonical_title"] = _select_canonical_title(record)
    return record


def _repair_timeline_coherence(
    payload: MutableMapping[str, Any],
) -> tuple[int, int, list[str], dict[str, list[str]]]:
    """Split only high-confidence incompatible timeline components.

    The largest coherent component retains the original story ID.  Each detached
    component receives a fresh ID; no alias is created because these records are
    explicitly different stories.
    """

    stories: MutableMapping[str, MutableMapping[str, Any]] = payload.setdefault(
        "stories", {}
    )
    repaired_story_count = 0
    detached_entry_count = 0
    new_story_ids: list[str] = []
    split_story_ids: dict[str, list[str]] = {}

    for story_id in sorted(list(stories), key=_story_number):
        story = stories.get(story_id)
        if not isinstance(story, MutableMapping):
            continue
        analysis = analyze_story_timeline_coherence(story, story_id=story_id)
        if analysis.coherent or len(analysis.components) < 2:
            continue

        components = [list(component) for component in analysis.components]

        def component_priority(component: list[dict[str, Any]]) -> tuple[int, int, int, str]:
            candidate_count = sum(
                1
                for candidate in (story.get("title_candidates", ()) or ())
                if isinstance(candidate, Mapping)
                and _component_candidate_matches(candidate, component)
            )
            source_count = len(
                {
                    timeline_entry_source_identity(entry)
                    for entry in component
                    if timeline_entry_source_identity(entry)
                }
            )
            earliest = min(
                (str(entry.get("published_at") or "") for entry in component),
                default="",
            )
            return (len(component), candidate_count, source_count, earliest)

        primary_component = max(components, key=component_priority)
        original_snapshot = dict(story)
        primary_record = _component_record(
            original_snapshot,
            primary_component,
            story_id=story_id,
            preserve_local_relevance=True,
            original_story_id=story_id,
        )
        stories[story_id] = primary_record
        split_story_ids[story_id] = []

        for component in components:
            if component is primary_component:
                continue
            new_story_id = _allocate_story_id(payload)
            stories[new_story_id] = _component_record(
                original_snapshot,
                component,
                story_id=new_story_id,
                preserve_local_relevance=False,
                original_story_id=story_id,
            )
            new_story_ids.append(new_story_id)
            split_story_ids[story_id].append(new_story_id)
            detached_entry_count += len(component)

        repaired_story_count += 1

    return repaired_story_count, detached_entry_count, new_story_ids, split_story_ids

def _source_identity_components(stories: Mapping[str, Mapping[str, Any]]) -> list[set[str]]:
    """Return components sharing an exact safe article identity URL."""

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

    source_index: dict[str, list[str]] = {}
    for story_id, story in stories.items():
        for source_url in story_source_identity_urls(story):
            source_index.setdefault(source_url, []).append(story_id)

    for source_url, group in source_index.items():
        unique = sorted(set(group))
        for left, right in itertools.combinations(unique, 2):
            left_titles = story_identity_titles(stories[left])
            right_titles = story_identity_titles(stories[right])
            if source_identity_requires_title_continuity(
                source_url, existing_titles=(*left_titles, *right_titles)
            ):
                compatible = any(
                    source_identity_title_compatible(title, right_titles)
                    for title in left_titles
                )
                if not compatible:
                    continue
            union(left, right)

    components: dict[str, set[str]] = {}
    for story_id in stories:
        components.setdefault(find(story_id), set()).add(story_id)
    return [component for component in components.values() if len(component) > 1]


def _count_incident_identity_groups(stories: Mapping[str, Mapping[str, Any]]) -> int:
    return len(_incident_components(stories))


def _count_source_identity_groups(stories: Mapping[str, Mapping[str, Any]]) -> int:
    return len(_source_identity_components(stories))


def _count_exact_duplicate_title_groups(stories: Mapping[str, Mapping[str, Any]]) -> int:
    title_index: dict[str, set[str]] = {}
    for story_id, story in stories.items():
        for title in [story.get("canonical_title", ""), *story.get("titles", ())]:
            normalized = normalize_title(title)
            if len(normalized.split()) >= 4:
                title_index.setdefault(normalized, set()).add(story_id)
    return sum(1 for story_ids in title_index.values() if len(story_ids) > 1)


def _count_publisher_title_duplicate_groups(stories: Mapping[str, Mapping[str, Any]]) -> int:
    title_index: dict[str, set[str]] = {}
    for story_id, story in stories.items():
        for title in [story.get("canonical_title", ""), *story.get("titles", ())]:
            normalized = normalize_identity_title(title)
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

    publisher_duplicate_groups_before = _count_publisher_title_duplicate_groups(stories)
    merged_story_ids: dict[str, list[str]] = {}

    exact_components = _duplicate_components(stories)
    for component in sorted(exact_components, key=lambda group: min(_story_number(value) for value in group)):
        primary_id = choose_primary_story_id(component, stories)
        secondary_ids = sorted(component - {primary_id}, key=_story_number)
        primary = stories[primary_id]
        for secondary_id in secondary_ids:
            merge_story_records(primary, stories[secondary_id])
            aliases[secondary_id] = primary_id
            del stories[secondary_id]
        merged_story_ids.setdefault(primary_id, []).extend(secondary_ids)

    # Exact article URLs are stronger identity evidence than evolving headline
    # text. Feed/search URLs are filtered by source_identity.py and cannot join
    # unrelated stories.
    source_groups_before = _count_source_identity_groups(stories)
    source_components = _source_identity_components(stories)
    source_removed = 0
    for component in sorted(source_components, key=lambda group: min(_story_number(value) for value in group)):
        primary_id = choose_primary_story_id(component, stories)
        secondary_ids = sorted(component - {primary_id}, key=_story_number)
        primary = stories[primary_id]
        for secondary_id in secondary_ids:
            merge_story_records(primary, stories[secondary_id])
            aliases[secondary_id] = primary_id
            del stories[secondary_id]
            source_removed += 1
        merged_story_ids.setdefault(primary_id, []).extend(secondary_ids)

    # Named-person death incidents are repaired at timeline-entry granularity.
    # This prevents a contaminated legacy story from dragging unrelated fire or
    # animal-rescue entries into the canonical death story.
    (
        selective_groups,
        selective_entries_moved,
        contaminated_preserved,
        incident_anchor_to_story,
        selective_moved_by_primary,
    ) = _selective_named_person_death_repair(stories, aliases)
    for primary_id, secondary_ids in selective_moved_by_primary.items():
        merged_story_ids.setdefault(primary_id, []).extend(secondary_ids)

    # Split only high-confidence timeline contamination.  Unlike a merge, these
    # components are intentionally different stories, so no aliases are created.
    (
        timeline_stories_repaired,
        timeline_entries_detached,
        timeline_new_story_ids,
        timeline_split_story_ids,
    ) = _repair_timeline_coherence(payload)

    # Exact and publisher-attribution duplicates are resolved first.  The
    # remaining whole-record incident layer is used only for families whose
    # records are safe to merge as a unit (currently mass animal hoarding).
    incident_groups_before = _count_incident_identity_groups(stories)
    incident_components = _incident_components(stories)
    incident_removed = 0
    for component in sorted(incident_components, key=lambda group: min(_story_number(value) for value in group)):
        primary_id = choose_primary_story_id(component, stories)
        secondary_ids = sorted(component - {primary_id}, key=_story_number)
        primary = stories[primary_id]
        for secondary_id in secondary_ids:
            merge_story_records(primary, stories[secondary_id])
            aliases[secondary_id] = primary_id
            del stories[secondary_id]
            incident_removed += 1
        merged_story_ids.setdefault(primary_id, []).extend(secondary_ids)

    # Rebuild the event index from active records only. Quarantined records never
    # retain active mappings, and aliases are resolved to their chosen primary.
    event_to_story: dict[str, str] = {}
    for story_id, story in stories.items():
        for event_key in story.get("events", ( )):
            value = str(event_key or "").strip()
            if value and not is_broad_event_class_key(value):
                event_to_story[value] = story_id
    payload["event_to_story"] = event_to_story
    # Structured incident anchors are a first-class registry index.  New feed
    # coverage can resolve directly to the canonical story before generic event
    # keys or semantic similarity are considered.
    incident_anchor_to_story = {
        anchor: aliases.get(story_id, story_id)
        for anchor, story_id in incident_anchor_to_story.items()
        if aliases.get(story_id, story_id) in stories
    }
    payload["incident_anchor_to_story"] = incident_anchor_to_story

    removed = sum(len(values) for values in merged_story_ids.values())
    remaining_duplicates = _count_exact_duplicate_title_groups(stories)
    remaining_publisher_duplicates = _count_publisher_title_duplicate_groups(stories)
    remaining_source_groups = _count_source_identity_groups(stories)
    remaining_incident_groups = _count_incident_identity_groups(stories)
    remaining_timeline_violations = registry_timeline_coherence_violations(stories)
    report = RegistryRepairReport(
        repair_version=REPAIR_VERSION,
        changed=bool(
            quarantine_reasons
            or removed
            or selective_entries_moved
            or timeline_stories_repaired
        ),
        active_stories_before=before,
        active_stories_after=len(stories),
        quarantined_story_ids=tuple(sorted(quarantine_reasons, key=_story_number)),
        quarantine_reasons=quarantine_reasons,
        duplicate_groups_merged=(
            len(exact_components) + len(source_components) + len(incident_components)
        ),
        duplicate_story_records_removed=removed,
        merged_story_ids={
            primary: tuple(dict.fromkeys(merged))
            for primary, merged in merged_story_ids.items()
        },
        remaining_exact_duplicate_title_groups=remaining_duplicates,
        publisher_title_duplicate_groups_resolved=max(
            0, publisher_duplicate_groups_before - remaining_publisher_duplicates
        ),
        remaining_publisher_title_duplicate_groups=remaining_publisher_duplicates,
        source_identity_groups_resolved=max(
            0, source_groups_before - remaining_source_groups
        ),
        source_story_records_removed=source_removed,
        remaining_source_identity_groups=remaining_source_groups,
        incident_identity_groups_resolved=max(
            0, incident_groups_before - remaining_incident_groups
        ),
        incident_story_records_removed=incident_removed,
        remaining_incident_identity_groups=remaining_incident_groups,
        selective_incident_anchor_groups_repaired=selective_groups,
        selective_timeline_entries_moved=selective_entries_moved,
        contaminated_story_records_preserved=contaminated_preserved,
        timeline_coherence_story_records_repaired=timeline_stories_repaired,
        timeline_coherence_entries_detached=timeline_entries_detached,
        timeline_coherence_new_story_ids=tuple(timeline_new_story_ids),
        remaining_timeline_coherence_violations=len(remaining_timeline_violations),
        timeline_coherence_violation_story_ids=tuple(
            str(row.get("story_id") or "") for row in remaining_timeline_violations
        ),
        incident_anchor_to_story_count=len(incident_anchor_to_story),
        generated_at=_utc_now(),
    )

    repair_state = payload.setdefault("registry_repair", {})
    history = list(repair_state.get("history", ()) or ())
    history.append(report.to_dict())
    repair_state["version"] = REPAIR_VERSION
    repair_state["last_run"] = report.to_dict()
    repair_state["history"] = history[-10:]
    return report

