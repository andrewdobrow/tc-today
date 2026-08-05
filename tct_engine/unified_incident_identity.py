"""Conservative cross-source incident identity for sparse and drifting headlines.

This layer sits between exact/source identity and semantic resolution. It requires
concrete, explainable anchors and never treats absent evidence as agreement.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Iterable, Mapping

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "local", "man", "new", "news", "of", "on", "or",
    "said", "says", "the", "this", "to", "was", "were", "with", "woman",
    "florida", "county", "after", "near", "used", "police", "accused",
})
_GENERIC = frozenset({
    "arrest", "arrested", "charge", "charged", "crash", "family", "incident",
    "road", "vehicle", "vehicles", "fire", "death", "killed", "dead",
    "shooting", "shot", "officials", "investigation", "report", "reported",
    "murder", "suicide", "domestic", "related", "victim", "suspect",
    "identified", "identify", "identifies", "dies", "died", "fatal",
    "collision", "wreck", "driver", "rider", "person", "people",
})


def _norm(value: object) -> str:
    return " ".join(_WORD_RE.findall(str(value or "").casefold()))


def _tokens(value: object) -> set[str]:
    return {
        token for token in _WORD_RE.findall(str(value or "").casefold())
        if len(token) >= 3 and token not in _STOP
    }


def _overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / min(len(left), len(right)) if left and right else 0.0


def _family(text: str) -> str:
    patterns = (
        ("road_rage", r"\broad rage\b|\b(?:pit|police) maneuver\b|\brun(?:ning)? .{0,45} off (?:the )?road\b|\bchased? off (?:the )?road\b"),
        ("wildfire_arson", r"\bwildfire\b|\bbrush fire\b.{0,45}\b(?:arson|set|setting|charged)\b|\b(?:arson|set|setting)\b.{0,45}\b(?:wildfire|brush fire)\b"),
        ("animal_rescue", r"\b(?:cat|cats|dog|dogs|animal|animals|hamster|pets?)\b.{0,45}\b(?:rescue|rescued|saved)\b|\b(?:rescue|rescued|saved)\b.{0,45}\b(?:cat|cats|dog|dogs|animal|animals|hamster|pets?)\b"),
        ("traffic_crash", r"\b(?:crash|collision|wreck|vehicle overturned|hit and run)\b"),
        ("murder_suicide", r"\bmurder[- ]suicide\b|\bdomestic[- ]related\b.{0,45}\b(?:two|2) dead\b"),
        ("shooting", r"\b(?:shooting|shot|gunfire)\b"),
        ("government_finance", r"\b(?:property tax|tax reform|millage|budget|job cuts?)\b"),
        ("dui", r"\b(?:dui|driving under the influence)\b"),
        ("fire", r"\b(?:fire|blaze)\b"),
        ("death", r"\b(?:killed|dead|dies|died|death|murder)\b"),
    )
    for family, pattern in patterns:
        if re.search(pattern, text):
            return family
    return "unknown"


def _concepts(text: str) -> set[str]:
    concepts: set[str] = set()
    tests = (
        ("pit_maneuver", r"\b(?:pit|police) maneuver\b"),
        ("forced_off_road", r"\b(?:run|running|ran|chased|forced|sent|sends|crash(?:ed|es)?)\b.{0,60}\b(?:off (?:the )?road|into (?:a )?(?:barbed wire )?fence)\b|\bvehicle.{0,50}\bfence\b|\bsuv.{0,50}\bfence\b"),
        ("north_carolina_family", r"\bnorth carolina\b.{0,50}\bfamily\b|\bfamily\b.{0,50}\bnorth carolina\b"),
        ("family_victim", r"\bfamily(?:'s)?\b"),
        ("barbed_wire_fence", r"\bbarbed wire fence\b|\binto (?:a )?fence\b|\bsuv.{0,35}\bfence\b"),
        ("i95", r"\bi\s*95\b|\binterstate 95\b"),
        ("kanner_highway", r"\bkanner (?:highway|hwy|road)\b"),
        ("martin_stuart", r"\bmartin county\b|\bstuart\b"),
        ("fourth_arrest", r"\b(?:4th|fourth) arrest\b|\b4 (?:people )?arrested\b"),
    )
    for name, pattern in tests:
        if re.search(pattern, text):
            concepts.add(name)
    return concepts


def _person_names(text: str) -> set[str]:
    # Deliberately narrow: full names adjacent to an age or arrest verb.
    names: set[str] = set()
    raw = str(text or "")
    for match in re.finditer(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:,?\s+(?:age\s+)?\d{1,3}\b|\s+(?:was\s+)?(?:arrested|charged|identified|killed)\b)",
        raw,
    ):
        value = " ".join(match.group(1).casefold().split())
        if value not in {"north carolina", "martin county", "palm beach", "fort myers"}:
            names.add(value)
    return names


def _iso(value: object) -> str:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _days_between(left: str, right: str) -> float | None:
    if not left or not right:
        return None
    try:
        a = datetime.fromisoformat(left.replace("Z", "+00:00"))
        b = datetime.fromisoformat(right.replace("Z", "+00:00"))
    except ValueError:
        return None
    return abs((a - b).total_seconds()) / 86400


@dataclass(frozen=True, slots=True)
class UnifiedIncidentEvidence:
    family: str
    concepts: tuple[str, ...]
    people: tuple[str, ...]
    locations: tuple[str, ...]
    agencies: tuple[str, ...]
    distinctive_tokens: tuple[str, ...]
    title_tokens: tuple[str, ...]
    published_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "concepts": list(self.concepts),
            "people": list(self.people),
            "locations": list(self.locations),
            "agencies": list(self.agencies),
            "distinctive_tokens": list(self.distinctive_tokens),
            "title_tokens": list(self.title_tokens),
            "published_at": self.published_at,
        }


def build_unified_incident_evidence(
    *,
    title: object,
    body: object = "",
    facts: Iterable[object] = (),
    locations: Iterable[object] = (),
    agencies: Iterable[object] = (),
    entities: Iterable[object] = (),
    published_at: object = None,
) -> UnifiedIncidentEvidence:
    title_text = str(title or "")
    text = " ".join(
        [title_text, str(body or ""), *(str(v or "") for v in facts), *(str(v or "") for v in entities)]
    )
    normalized = _norm(text)
    title_tokens = _tokens(title_text)
    normalized_locations = {_norm(v) for v in locations if _norm(v)}
    normalized_agencies = {_norm(v) for v in agencies if _norm(v)}
    location_tokens: set[str] = set()
    agency_tokens: set[str] = set()
    for value in normalized_locations:
        location_tokens |= _tokens(value)
    for value in normalized_agencies:
        agency_tokens |= _tokens(value)
    # Location and agency are scored as structured fields. Excluding their words
    # from the distinctive token set prevents a broad city/county name from
    # masquerading as independent evidence.
    distinctive = _tokens(text) - _GENERIC - location_tokens - agency_tokens
    return UnifiedIncidentEvidence(
        family=_family(normalized),
        concepts=tuple(sorted(_concepts(normalized))),
        people=tuple(sorted(_person_names(text))),
        locations=tuple(sorted(normalized_locations)),
        agencies=tuple(sorted(normalized_agencies)),
        distinctive_tokens=tuple(sorted(distinctive))[:48],
        title_tokens=tuple(sorted(title_tokens))[:36],
        published_at=_iso(published_at),
    )


def evidence_from_mapping(value: Mapping[str, Any]) -> UnifiedIncidentEvidence:
    return UnifiedIncidentEvidence(
        family=str(value.get("family") or "unknown"),
        concepts=tuple(str(v) for v in value.get("concepts", ()) if str(v)),
        people=tuple(str(v) for v in value.get("people", ()) if str(v)),
        locations=tuple(str(v) for v in value.get("locations", ()) if str(v)),
        agencies=tuple(str(v) for v in value.get("agencies", ()) if str(v)),
        distinctive_tokens=tuple(str(v) for v in value.get("distinctive_tokens", ()) if str(v)),
        title_tokens=tuple(str(v) for v in value.get("title_tokens", ()) if str(v)),
        published_at=str(value.get("published_at") or ""),
    )


@dataclass(frozen=True, slots=True)
class UnifiedIncidentMatch:
    story_id: str | None
    confidence: float
    reason: str
    decision_trace: tuple[str, ...]

    @property
    def matched(self) -> bool:
        return bool(self.story_id) and self.confidence >= 0.86


def compare_unified_incident_evidence(
    incoming: UnifiedIncidentEvidence,
    known: UnifiedIncidentEvidence,
) -> tuple[float, tuple[str, ...]]:
    if incoming.family == "unknown" or known.family == "unknown" or incoming.family != known.family:
        return 0.0, ("Compatible event family: false",)

    days = _days_between(incoming.published_at, known.published_at)
    if days is not None and days > 21:
        return 0.0, (f"Publication window days: {days:.1f}", "Within incident window: false")

    concepts_a, concepts_b = set(incoming.concepts), set(known.concepts)
    people_a, people_b = set(incoming.people), set(known.people)
    locations_a, locations_b = set(incoming.locations), set(known.locations)
    agencies_a, agencies_b = set(incoming.agencies), set(known.agencies)
    distinctive_a, distinctive_b = set(incoming.distinctive_tokens), set(known.distinctive_tokens)
    title_a, title_b = set(incoming.title_tokens), set(known.title_tokens)

    shared_concepts = concepts_a & concepts_b
    shared_people = people_a & people_b
    shared_locations = locations_a & locations_b
    shared_agencies = agencies_a & agencies_b
    shared_distinctive = distinctive_a & distinctive_b
    distinctive_overlap = _overlap(distinctive_a, distinctive_b)
    title_overlap = _overlap(title_a, title_b)

    location_conflict = bool(locations_a and locations_b and not shared_locations)
    if location_conflict and not shared_people and incoming.family != "road_rage":
        return 0.0, ("Location conflict: true",)

    confidence = 0.0
    qualified = False
    if shared_people:
        confidence = 0.94 + min(0.04, 0.01 * len(shared_concepts))
        qualified = True
    elif incoming.family == "road_rage":
        core = {"pit_maneuver", "forced_off_road"}
        region = {"martin_stuart", "i95", "kanner_highway", "north_carolina_family", "barbed_wire_fence"}
        core_match = bool(shared_concepts & core) or (
            bool(concepts_a & core) and bool(concepts_b & core)
        )
        region_match = bool((concepts_a & region) & (concepts_b & region))
        # Source headlines can describe the same maneuver as PIT, police maneuver,
        # chased off road, or SUV into a fence. Require the core action plus one
        # distinctive regional/victim anchor, never generic "road rage" alone.
        shared_victim = "family_victim" in shared_concepts
        if core_match and region_match:
            confidence = 0.94 + min(0.04, 0.01 * len(shared_concepts))
            qualified = True
        elif core_match and shared_victim and title_overlap >= 0.25:
            confidence = 0.91
            qualified = True
        elif len(shared_concepts) >= 3 and title_overlap >= 0.28:
            confidence = 0.90
            qualified = True
        elif len(shared_concepts & region) >= 2 and title_overlap >= 0.25:
            confidence = 0.88
            qualified = True
        elif shared_locations and title_overlap >= 0.30:
            confidence = 0.87
            qualified = True
    else:
        # General source-framing drift contract. A shared city or county by itself
        # is never enough: the same event family must also retain substantial
        # distinctive wording from the publisher source. Agency corroboration can
        # lower the wording threshold slightly, while location-only matches require
        # both high token overlap and at least three shared distinctive terms.
        general_family_allowed = incoming.family in {
            "traffic_crash", "shooting", "murder_suicide",
            "animal_rescue", "dui", "wildfire_arson",
        }
        location_agency_signature = (
            general_family_allowed
            and bool(shared_locations)
            and bool(shared_agencies)
            and len(shared_distinctive) >= 2
            and distinctive_overlap >= 0.50
            and title_overlap >= 0.45
        )
        location_fact_signature = (
            general_family_allowed
            and bool(shared_locations)
            and (
                (
                    len(shared_distinctive) >= 3
                    and distinctive_overlap >= 0.60
                    and title_overlap >= 0.55
                )
                or (
                    len(shared_distinctive) >= 2
                    and distinctive_overlap >= 0.66
                    and title_overlap >= 0.65
                )
            )
        )
        if location_agency_signature:
            confidence = 0.91 + min(0.04, 0.01 * len(shared_distinctive))
            qualified = True
        elif location_fact_signature:
            confidence = 0.89 + min(0.04, 0.01 * len(shared_distinctive))
            qualified = True

    trace = (
        f"Compatible event family: {incoming.family == known.family}",
        f"Event family: {incoming.family}",
        f"Shared people: {', '.join(sorted(shared_people)) or 'none'}",
        f"Shared locations: {', '.join(sorted(shared_locations)) or 'none'}",
        f"Shared agencies: {', '.join(sorted(shared_agencies)) or 'none'}",
        f"Shared concepts: {', '.join(sorted(shared_concepts)) or 'none'}",
        f"Shared distinctive tokens: {len(shared_distinctive)}",
        f"Distinctive-token overlap: {distinctive_overlap:.2f}",
        f"Title overlap: {title_overlap:.2f}",
        f"Identity anchors qualified: {qualified}",
        f"Confidence: {confidence:.2f}",
    )
    return confidence if qualified else 0.0, trace


def story_unified_evidence(story: Mapping[str, Any]) -> tuple[UnifiedIncidentEvidence, ...]:
    stored = story.get("unified_incident_evidence", ()) or ()
    evidence = [evidence_from_mapping(row) for row in stored if isinstance(row, Mapping)]
    if evidence:
        return tuple(evidence)
    titles = [story.get("canonical_title", ""), *story.get("titles", ())]
    published = ""
    timeline = list(story.get("timeline", ()) or ())
    if timeline:
        published = str(timeline[0].get("published_at") or "")
    built = [
        build_unified_incident_evidence(
            title=title,
            facts=story.get("facts", ()),
            locations=story.get("locations", ()),
            agencies=story.get("agencies", ()),
            entities=story.get("entities", ()),
            published_at=published,
        )
        for title in titles if str(title or "").strip()
    ]
    return tuple(built)


def find_matching_unified_incident_story(
    incoming: UnifiedIncidentEvidence,
    stories: Iterable[Mapping[str, Any]],
) -> UnifiedIncidentMatch:
    candidates: list[tuple[float, str, tuple[str, ...]]] = []
    for story in stories:
        if story.get("status") == "archived":
            continue
        story_id = str(story.get("story_id") or "").strip()
        if not story_id:
            continue
        best_score = 0.0
        best_trace: tuple[str, ...] = ()
        for known in story_unified_evidence(story):
            score, trace = compare_unified_incident_evidence(incoming, known)
            if score > best_score:
                best_score, best_trace = score, trace
        if best_score >= 0.86:
            candidates.append((best_score, story_id, best_trace))
    candidates.sort(reverse=True)
    if not candidates:
        return UnifiedIncidentMatch(None, 0.0, "No verified unified incident match", ("Unified incident match: false",))
    best_score, best_story, best_trace = candidates[0]
    if len(candidates) > 1 and candidates[1][0] >= best_score - 0.03:
        return UnifiedIncidentMatch(None, 0.0, "Ambiguous unified incident candidates", (*best_trace, "Ambiguous candidate margin: true"))
    return UnifiedIncidentMatch(
        best_story,
        best_score,
        "Verified cross-source incident evidence belongs to an existing story",
        ("Unified incident match: true", *best_trace),
    )


def story_has_verified_unified_identity(story: Mapping[str, Any]) -> bool:
    """Return true when every stored title/evidence row forms one verified incident.

    Registry repair uses this to distinguish a legitimate sparse-key incident with
    many publisher phrasings from an unsupported sparse merge. The evidence graph
    must be connected; one matching pair is not enough to excuse a disconnected
    title cluster.
    """
    evidence = list(story_unified_evidence(story))
    if len(evidence) < 2:
        return False
    parent = list(range(len(evidence)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    for left in range(len(evidence)):
        for right in range(left + 1, len(evidence)):
            score, _ = compare_unified_incident_evidence(evidence[left], evidence[right])
            if score >= 0.86:
                union(left, right)
    return len({find(index) for index in range(len(evidence))}) == 1


def unified_incident_components(stories: Mapping[str, Mapping[str, Any]]) -> list[set[str]]:
    ids = list(stories)
    parent = {story_id: story_id for story_id in ids}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    buckets: dict[str, list[str]] = {}
    for story_id, story in stories.items():
        families = {ev.family for ev in story_unified_evidence(story) if ev.family != "unknown"}
        for family in families:
            buckets.setdefault(family, []).append(story_id)
    for members in buckets.values():
        for i, left in enumerate(members):
            left_evidence = story_unified_evidence(stories[left])
            for right in members[i + 1:]:
                matched = False
                for a in left_evidence:
                    for b in story_unified_evidence(stories[right]):
                        score, _ = compare_unified_incident_evidence(a, b)
                        if score >= 0.86:
                            union(left, right)
                            matched = True
                            break
                    if matched:
                        break
    grouped: dict[str, set[str]] = {}
    for story_id in ids:
        grouped.setdefault(find(story_id), set()).add(story_id)
    return [group for group in grouped.values() if len(group) > 1]
