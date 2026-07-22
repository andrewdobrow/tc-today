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


def extract_article_facts(
    article: RawArticle,
) -> ExtractedArticleFacts:

    text = f"{article.title} {article.body}"

    facts = []
    locations = []
    agencies = []
    event_types = []

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

    if "fire" in lower:
        event_types.append("fire")
        facts.append("fire reported")

    if "no injuries" in lower:
        facts.append("no injuries reported")

    if "missing" in lower:
        event_types.append("missing person")
        facts.append("missing person")

    return ExtractedArticleFacts(
        article_id=article.article_id,
        source=article.source,
        is_custom=article.is_custom,
        facts=_unique(facts),
        locations=_unique(locations),
        agencies=_unique(agencies),
        event_types=_unique(event_types),
    )