"""Deterministic article fact extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RawArticle:
    article_id: str
    title: str
    body: str
    source: str
    url: str
    published_at: datetime
    county: str | None
    is_custom: bool = False


@dataclass(frozen=True, slots=True)
class ExtractedArticleFacts:
    article_id: str
    source: str
    is_custom: bool
    facts: tuple[str, ...]
    locations: tuple[str, ...]
    agencies: tuple[str, ...]
    event_types: tuple[str, ...]
    entities: tuple[str, ...] = ()


_LOCATION_PATTERNS = (
    "Stuart",
    "Jensen Beach",
    "Port St. Lucie",
    "Fort Pierce",
    "Palm City",
    "Hobe Sound",
    "Sebastian",
    "Vero Beach",
)

_AGENCIES = (
    (
        re.compile(r"martin county sheriff", re.I),
        "Martin County Sheriff's Office",
    ),
    (
        re.compile(r"st\.?\s*lucie county sheriff", re.I),
        "St. Lucie County Sheriff's Office",
    ),
    (
        re.compile(r"indian river county sheriff", re.I),
        "Indian River County Sheriff's Office",
    ),
    (
        re.compile(r"port st\.?\s*lucie police", re.I),
        "Port St. Lucie Police Department",
    ),
    (
        re.compile(r"fort pierce police", re.I),
        "Fort Pierce Police Department",
    ),
    (
        re.compile(r"st\.?\s*lucie county fire district", re.I),
        "St. Lucie County Fire District",
    ),
)

_NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


def _number_to_digit(value: str) -> str:
    normalized = value.lower()
    return _NUMBER_WORDS.get(normalized, value)

_NUMBER_PATTERNS = [
    (
        re.compile(r"\b(\d+)(?:st|nd|rd|th)\s+arrest\b", re.I),
        lambda m: f"arrest count: {m.group(1)}",
    ),
    (
        re.compile(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+arrest\b", re.I),
        lambda m: f"arrest count: { {'first':'1','second':'2','third':'3','fourth':'4','fifth':'5','sixth':'6','seventh':'7','eighth':'8','ninth':'9','tenth':'10'}[m.group(1).lower()] }",
    ),
    (
        re.compile(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:people?\s+)?arrested\b", re.I),
        lambda m: f"arrest count: {_number_to_digit(m.group(1))}",
    ),
    (
        re.compile(r"(\d+)\s+cats?", re.I),
        lambda m: f"{m.group(1)} cats",
    ),
    (
        re.compile(
            r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
            r"\s+people?\s+(?:was|were)\s+injured",
            re.I,
        ),
        lambda m: (
            f"{_number_to_digit(m.group(1))} people injured"
        ),
),
    (
        re.compile(r"one person died", re.I),
        lambda m: "1 person died",
    ),
    (
        re.compile(r"(\d+)-year-old", re.I),
        lambda m: f"{m.group(1)}-year-old",
    ),
]


def _unique(values):
    seen = set()
    ordered = []

    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)

    return tuple(ordered)


def _is_active_missing_person_incident(text: str) -> bool:
    """Return True only when ``missing`` describes the article's active incident.

    The word appears routinely in policy and public-safety stories as a permitted
    use case (for example, ALPR access for a missing or endangered child).  A raw
    substring check turns those stories into city-level missing-person events and
    can merge unrelated coverage.  Require incident language that says somebody is
    actually missing, being searched for, was last seen, or has been found/located.
    """
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if not re.search(r"\bmissing\b", lower):
        return False

    active_patterns = (
        # Search language must actually govern a missing subject. This deliberately
        # excludes generic capability wording such as "locating missing people".
        r"\b(?:search(?:ing|es|ed)?|look(?:ing)?|seek(?:ing|s|ed)?)\b[^.!?]{0,100}\bmissing\b",
        r"\b(?:trying|asking the public|asked the public|help(?:ing)?)\b[^.!?]{0,60}\b(?:find|locate)\b[^.!?]{0,60}\bmissing\b",
        # Direct subject phrasing, but not policy buckets such as
        # "missing-person cases/investigations".
        r"\bmissing[- ](?:person|man|woman|boy|girl|teen(?:ager)?|child|adult|senior|resident|visitor|student|juvenile)\b(?!\s+(?:case|cases|investigation|investigations|policy|policies))",
        r"\b(?:man|woman|boy|girl|teen(?:ager)?|child|adult|senior|resident|visitor|student|juvenile|person)\b[^.!?]{0,45}\b(?:is|was|remains|reported)\s+missing\b",
        r"\b(?:reported|remains|still)\s+missing\b",
        r"\blast\s+seen\b",
        r"\bwhereabouts\b[^.!?]{0,80}\b(?:unknown|remain unknown|are unknown)\b",
        r"\b(?:amber|silver)\s+alert\b",
        r"\bmissing\b[^.!?]{0,140}\b(?:found|located)\s+safe\b",
        r"\b(?:found|located)\s+safe\b[^.!?]{0,140}\bmissing\b",
    )
    return any(re.search(pattern, lower, re.I) for pattern in active_patterns)


def extract_article_facts(
    article: RawArticle,
) -> ExtractedArticleFacts:

    text = f"{article.title} {article.body}"

    facts = []
    locations = []
    agencies = []
    event_types = []
    entities = []

    lower = text.lower()

    for location in _LOCATION_PATTERNS:
        if location.lower() in lower:
            locations.append(location)

    for pattern, agency in _AGENCIES:
        if pattern.search(text):
            agencies.append(agency)

    for pattern, formatter in _NUMBER_PATTERNS:
        for match in pattern.finditer(text):
            facts.append(formatter(match))

    if "rescued" in lower and "cat" in lower:
        facts.append("cats rescued")
        event_types.append("animal rescue")

    if "animal cruelty" in lower:
        facts.append("animal cruelty")

    if "arrest" in lower:
        facts.append("arrest made")

    if "crash" in lower:
        event_types.append("traffic crash")

    if "closed" in lower:
        facts.append("road closed")

    # Match an actual fire event, not substrings such as "firearm" or
    # "firefighter". The old substring check poisoned drug/crime stories that
    # mentioned seized firearms with a false fire event identity.
    if re.search(r"\b(?:fire|blaze|burning|burned|arson)\b", lower):
        event_types.append("fire")
        facts.append("fire reported")

    if "no injuries" in lower:
        facts.append("no injuries reported")

    if _is_active_missing_person_incident(text):
        event_types.append("missing person")
        facts.append("missing person")


    # Named organizations, roads, projects, teams and quoted proper names are
    # durable identity anchors for Resolver v2.
    entity_patterns = (
        r"\b(?:Martin County|St\.? Lucie County|Indian River County) (?:Sheriff(?:\'s)? Office|Commission|School Board|Fire District)\b",
        r"\b(?:Port St\.? Lucie|Stuart|Fort Pierce|Vero Beach|Sebastian) City Council\b",
        r"\bSt\.? Lucie Mets\b",
        r"\bPalm Beach Cardinals\b",
        r"\b(?:State Road|S\.?R\.?|U\.?S\.?)\s*\d+[A-Za-z-]*\b",
        r"\b[A-Z][A-Za-z0-9&.'-]+(?:\s+[A-Z][A-Za-z0-9&.'-]+){1,4}\b",
    )
    for pattern in entity_patterns:
        for match in re.finditer(pattern, text):
            value = match.group(0).strip()
            if len(value) >= 5:
                entities.append(value)

    return ExtractedArticleFacts(
        article_id=article.article_id,
        source=article.source,
        is_custom=article.is_custom,
        facts=_unique(facts),
        locations=_unique(locations),
        agencies=_unique(agencies),
        event_types=_unique(event_types),
        entities=_unique(entities),
    )