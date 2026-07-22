import re

from .fact_extraction import ExtractedArticleFacts


def _slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def generate_event_key(
    facts: ExtractedArticleFacts,
) -> str:

    if not facts.event_types:
        return "unknown-event"

    parts = [
        _slug(facts.event_types[0]),
    ]

    if facts.locations:
        parts.append(_slug(facts.locations[0]))

    if "cats rescued" in facts.facts:
        parts.append("cats")

    return "-".join(parts)