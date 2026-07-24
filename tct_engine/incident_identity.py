"""Deterministic high-confidence incident identity signatures.

This module closes the gap between exact headline identity and broad semantic
similarity.  It intentionally supports only incident families with enough
independent anchors to merge safely.  The first supported family is a mass
animal-hoarding/rescue incident, added from a production regression where the
same Martin County case fragmented into many persistent stories.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Iterable, Mapping

INCIDENT_IDENTITY_VERSION = "1.0"

_WORD_RE = re.compile(r"[a-z0-9]+")
_ANIMAL_QUANTITY_RE = re.compile(r"\b(\d{1,3})\s+(?:cats?|dogs?|animals?|pets?)\b", re.IGNORECASE)
_ANIMAL_RE = re.compile(r"\b(?:cats?|dogs?|animals?|pets?)\b", re.IGNORECASE)
_PLURAL_ANIMAL_RE = re.compile(r"\b(?:cats|dogs|animals|pets)\b", re.IGNORECASE)
_HOARDING_RE = re.compile(r"hoard", re.IGNORECASE)
_ANIMAL_ACTION_RE = re.compile(
    r"rescu|removed|reunit|shelter|humane society|filth|feces|faeces|cages",
    re.IGNORECASE,
)
_POSTAL_ROLE_RE = re.compile(r"\b(?:mail carrier|postal worker)\b", re.IGNORECASE)

_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "after", "from", "that", "this", "into",
        "over", "says", "said", "new", "county", "florida", "man", "woman",
        "home", "story", "news", "local", "report", "reported", "officials",
        "following", "police", "what", "how", "why", "their", "they", "was",
        "were", "has", "have", "had", "near", "more", "than", "some",
    }
)
_PUBLISHER_NOISE = frozenset(
    {
        "wptv", "wflx", "wpbf", "wpec", "wrdw", "ksnb", "kktv", "latestly",
        "cw34", "wftv", "abc7", "wwsb", "aol", "msn", "yahoo", "com",
        "orlando", "sentinel", "unionleader", "independent", "times", "india",
        "treasure", "coast", "hometown", "network", "journal", "herald",
    }
)
_SYNONYMS = {
    "rescued": "rescue",
    "rescuing": "rescue",
    "removed": "rescue",
    "removing": "rescue",
    "remove": "rescue",
    "found": "rescue",
    "animals": "animal",
    "pets": "animal",
    "cats": "cat",
    "dogs": "dog",
    "hoarded": "hoard",
    "hoarding": "hoard",
    "owners": "owner",
    "reunited": "reunite",
    "reuniting": "reunite",
    "recovering": "recover",
    "arrested": "arrest",
    "charged": "arrest",
    "charges": "arrest",
    "houses": "house",
    "carrier": "postalworker",
    "postal": "postalworker",
    "worker": "postalworker",
}

# The engine is intentionally Treasure Coast specific.  Nearby city names are
# normalized to their county so Stuart, Palm City and Hobe Sound do not appear
# to be conflicting locations for the same Martin County incident.
_AREA_TERMS: Mapping[str, tuple[str, ...]] = {
    "martin-county": (
        "martin county", "stuart", "hobe sound", "palm city", "port salerno",
        "jensen beach", "foxwoods",
    ),
    "st-lucie-county": (
        "st lucie county", "st. lucie county", "port st lucie", "port st. lucie",
        "fort pierce",
    ),
    "indian-river-county": (
        "indian river county", "vero beach", "sebastian", "fellsmere",
    ),
    "palm-beach-county": (
        "palm beach county", "west palm beach", "lake worth", "boca raton",
        "jupiter",
    ),
}

_DISTINCTIVE_MARKERS = frozenset(
    {"postal_worker", "owner_reunion", "animal_cruelty", "filthy_home", "sheriff"}
)


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _semantic_tokens(text: str) -> frozenset[str]:
    values: set[str] = set()
    for raw in _WORD_RE.findall(text.casefold()):
        token = _SYNONYMS.get(raw, raw)
        if len(token) < 3 or token in _STOPWORDS or token in _PUBLISHER_NOISE:
            continue
        values.add(token)
    if _POSTAL_ROLE_RE.search(text):
        values.add("postalworker")
    return frozenset(values)


def _animal_quantities(text: str) -> tuple[int, ...]:
    return tuple(sorted({int(match.group(1)) for match in _ANIMAL_QUANTITY_RE.finditer(text)}))


def _area_groups(text: str) -> frozenset[str]:
    folded = text.casefold()
    return frozenset(
        area
        for area, terms in _AREA_TERMS.items()
        if any(term in folded for term in terms)
    )


def _markers(text: str, quantities: Iterable[int]) -> frozenset[str]:
    folded = text.casefold()
    result: set[str] = set()
    if _HOARDING_RE.search(folded):
        result.add("hoarding")
    if _POSTAL_ROLE_RE.search(folded):
        result.add("postal_worker")
    if "animal cruelty" in folded:
        result.add("animal_cruelty")
    if re.search(r"reunit", folded) and re.search(r"owner|pet|cat|dog", folded):
        result.add("owner_reunion")
    if re.search(r"filth|feces|faeces|cages|no ac", folded):
        result.add("filthy_home")
    if "sheriff" in folded:
        result.add("sheriff")
    if re.search(r"arrest|charged", folded):
        result.add("arrest")
    if any(value >= 50 for value in quantities) or "nearly 100" in folded or "dozens" in folded:
        result.add("large_rescue")
    return frozenset(result)


def _incident_family(title_text: str, quantities: Iterable[int]) -> str:
    """Return a supported family only when the title has incident-level anchors."""

    animal = bool(_ANIMAL_RE.search(title_text))
    plural_animal = bool(_PLURAL_ANIMAL_RE.search(title_text))
    explicit_hoarding = bool(_HOARDING_RE.search(title_text))
    action = bool(_ANIMAL_ACTION_RE.search(title_text))
    strong_mass_anchor = bool(
        _POSTAL_ROLE_RE.search(title_text) or any(value >= 50 for value in quantities)
    )
    if animal and (explicit_hoarding or (plural_animal and action and strong_mass_anchor)):
        return "mass_animal_hoarding"
    return ""


@dataclass(frozen=True, slots=True)
class IncidentSignature:
    family: str
    tokens: frozenset[str]
    quantities: tuple[int, ...]
    area_groups: frozenset[str]
    markers: frozenset[str]
    published_at: tuple[datetime, ...]

    @property
    def supported(self) -> bool:
        return bool(self.family)


@dataclass(frozen=True, slots=True)
class IncidentIdentityMatch:
    matched: bool
    confidence: float
    reason: str
    decision_trace: tuple[str, ...]
    story_id: str | None = None


def build_incident_signature(
    *,
    titles: Iterable[object],
    facts: Iterable[object] = (),
    locations: Iterable[object] = (),
    agencies: Iterable[object] = (),
    event_types: Iterable[object] = (),
    entities: Iterable[object] = (),
    published_at: Iterable[object] = (),
) -> IncidentSignature:
    title_values = [str(value or "").strip() for value in titles if str(value or "").strip()]
    title_text = " | ".join(title_values)
    full_text = " | ".join(
        [
            title_text,
            *[str(value or "") for value in facts],
            *[str(value or "") for value in locations],
            *[str(value or "") for value in agencies],
            *[str(value or "") for value in event_types],
            *[str(value or "") for value in entities],
        ]
    )
    quantities = _animal_quantities(full_text)
    timestamps = tuple(
        parsed
        for parsed in (_parse_datetime(value) for value in published_at)
        if parsed is not None
    )
    return IncidentSignature(
        family=_incident_family(title_text, quantities),
        tokens=_semantic_tokens(full_text),
        quantities=quantities,
        area_groups=_area_groups(full_text),
        markers=_markers(full_text, quantities),
        published_at=timestamps,
    )


def build_story_incident_signature(story: Mapping[str, Any]) -> IncidentSignature:
    timeline = list(story.get("timeline", ()) or ())
    return build_incident_signature(
        titles=[story.get("canonical_title", ""), *story.get("titles", ())],
        facts=story.get("facts", ()),
        locations=story.get("locations", ()),
        agencies=story.get("agencies", ()),
        event_types=story.get("event_types", ()),
        entities=story.get("entities", ()),
        published_at=[entry.get("published_at") for entry in timeline],
    )


def _quantity_compatible(left: Iterable[int], right: Iterable[int]) -> bool:
    return any(
        abs(a - b) <= max(30, int(0.30 * max(a, b)))
        for a in left
        for b in right
    )


def compare_incident_signatures(
    left: IncidentSignature,
    right: IncidentSignature,
    *,
    max_age_days: float = 7.0,
) -> IncidentIdentityMatch:
    if not left.supported or left.family != right.family:
        return IncidentIdentityMatch(False, 0.0, "No supported shared incident family", ())

    if left.area_groups and right.area_groups and not (left.area_groups & right.area_groups):
        return IncidentIdentityMatch(
            False,
            0.0,
            "Conflicting local areas prevent incident consolidation",
            (
                f"Incident family: {left.family}",
                f"Left areas: {', '.join(sorted(left.area_groups))}",
                f"Right areas: {', '.join(sorted(right.area_groups))}",
                "Location conflict: true",
            ),
        )

    age_gap_days: float | None = None
    if left.published_at and right.published_at:
        age_gap_days = min(
            abs((a - b).total_seconds()) / 86400.0
            for a in left.published_at
            for b in right.published_at
        )
        if age_gap_days > max_age_days:
            return IncidentIdentityMatch(
                False,
                0.0,
                "Incident coverage falls outside the safe consolidation window",
                (
                    f"Incident family: {left.family}",
                    f"Minimum publication gap days: {age_gap_days:.2f}",
                    f"Maximum allowed gap days: {max_age_days:.2f}",
                ),
            )

    shared_tokens = left.tokens & right.tokens
    overlap = (
        len(shared_tokens) / min(len(left.tokens), len(right.tokens))
        if left.tokens and right.tokens
        else 0.0
    )
    quantity_match = _quantity_compatible(left.quantities, right.quantities)
    shared_markers = left.markers & right.markers
    distinctive_match = bool(shared_markers & _DISTINCTIVE_MARKERS)
    concept_match = overlap >= 0.25 and len(shared_tokens) >= 2
    area_match = bool(left.area_groups & right.area_groups)
    strong_evidence_count = sum((quantity_match, distinctive_match, concept_match))

    if area_match:
        matched = bool(
            strong_evidence_count >= 1
            or ("hoarding" in shared_markers and len(shared_tokens) >= 2)
        )
    elif left.area_groups or right.area_groups:
        matched = bool(
            strong_evidence_count >= 2
            or (quantity_match and "hoarding" in shared_markers)
        )
    else:
        matched = bool(strong_evidence_count >= 2 and (quantity_match or distinctive_match))

    confidence = 0.40
    confidence += 0.18 if area_match else 0.0
    confidence += 0.18 if quantity_match else 0.0
    confidence += 0.15 if distinctive_match else 0.0
    confidence += 0.14 if concept_match else 0.0
    confidence += 0.05 if age_gap_days is not None and age_gap_days <= max_age_days else 0.0
    confidence = min(0.99, confidence) if matched else 0.0

    trace = (
        f"Incident family: {left.family}",
        f"Area match: {area_match}",
        f"Quantity compatible: {quantity_match}",
        f"Distinctive marker match: {distinctive_match}",
        f"Concept overlap: {overlap:.2f}",
        f"Shared concept tokens: {', '.join(sorted(shared_tokens)[:12]) or 'none'}",
        f"Shared markers: {', '.join(sorted(shared_markers)) or 'none'}",
        f"Publication gap days: {age_gap_days:.2f}" if age_gap_days is not None else "Publication gap days: unknown",
        f"Confidence: {confidence:.2f}",
    )
    return IncidentIdentityMatch(
        matched,
        confidence,
        "High-confidence deterministic incident signature matched"
        if matched
        else "Incident evidence did not meet the conservative consolidation threshold",
        trace,
    )


def compare_story_incidents(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> IncidentIdentityMatch:
    return compare_incident_signatures(
        build_story_incident_signature(left),
        build_story_incident_signature(right),
    )


def find_matching_incident_story(
    *,
    title: str,
    facts: Iterable[str] = (),
    locations: Iterable[str] = (),
    agencies: Iterable[str] = (),
    event_types: Iterable[str] = (),
    entities: Iterable[str] = (),
    published_at: object = None,
    stories: Iterable[Mapping[str, Any]],
) -> IncidentIdentityMatch:
    incoming = build_incident_signature(
        titles=(title,),
        facts=facts,
        locations=locations,
        agencies=agencies,
        event_types=event_types,
        entities=entities,
        published_at=(published_at,),
    )
    if not incoming.supported:
        return IncidentIdentityMatch(False, 0.0, "Incoming article has no supported incident signature", ())

    matches: list[IncidentIdentityMatch] = []
    for story in stories:
        match = compare_incident_signatures(incoming, build_story_incident_signature(story))
        if match.matched:
            matches.append(
                IncidentIdentityMatch(
                    True,
                    match.confidence,
                    match.reason,
                    match.decision_trace,
                    str(story.get("story_id") or "") or None,
                )
            )
    if not matches:
        return IncidentIdentityMatch(False, 0.0, "No existing story met the incident identity threshold", ())
    return max(matches, key=lambda item: (item.confidence, str(item.story_id or "")))
