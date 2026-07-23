"""Relationship classification for distinct events that belong to one story."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

_WORD_RE = re.compile(r"[a-z0-9]+")
_NUMBER_RE = re.compile(r"\b\d+\b")
_STOP = {
    "the", "and", "for", "with", "from", "after", "before", "into",
    "county", "news", "update", "says", "said", "earlier", "reported",
}
_FOLLOW_UP_MARKERS = {
    "arrest", "arrested", "charge", "charged", "charges", "reopen", "reopens",
    "reopened", "identified", "dies", "died", "sentenced", "sentence", "trial",
    "hearing", "lawsuit", "investigation", "continues", "recovered", "found",
}
_CASUALTY_WORDS = {"injured", "killed", "dead", "fatalities", "victims", "hurt"}


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _set(values: Iterable[object]) -> set[str]:
    return {_norm(value) for value in values if _norm(value)}


def _tokens(value: object) -> set[str]:
    return {
        token for token in _WORD_RE.findall(_norm(value))
        if len(token) >= 3 and token not in _STOP
    }


def _overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / min(len(left), len(right)) if left and right else 0.0


def _numeric_casualty_signatures(facts: Iterable[str]) -> set[tuple[str, str]]:
    signatures: set[tuple[str, str]] = set()
    for fact in facts:
        text = _norm(fact)
        numbers = _NUMBER_RE.findall(text)
        casualty_terms = _tokens(text) & _CASUALTY_WORDS
        for number in numbers:
            for term in casualty_terms:
                signatures.add((term, number))
    return signatures


class StoryRelationshipType(str, Enum):
    SAME_EVENT = "same_event"
    FOLLOW_UP = "follow_up"
    RELATED = "related"
    NEW_STORY = "new_story"


@dataclass(frozen=True, slots=True)
class StoryRelationship:
    relationship: StoryRelationshipType
    story_id: str | None
    confidence: float
    reason: str
    decision_trace: tuple[str, ...] = ()

    @property
    def attaches_to_story(self) -> bool:
        return self.relationship in {
            StoryRelationshipType.SAME_EVENT,
            StoryRelationshipType.FOLLOW_UP,
        } and bool(self.story_id)


class StoryRelationshipEngine:
    """Conservatively groups distinct events into a persistent story."""

    FOLLOW_UP_THRESHOLD = 0.68

    def classify(
        self,
        *,
        event_key: str,
        title: str,
        facts: Iterable[str],
        locations: Iterable[str] = (),
        agencies: Iterable[str] = (),
        event_types: Iterable[str] = (),
        entities: Iterable[str] = (),
        stories: Iterable[Mapping[str, Any]],
    ) -> StoryRelationship:
        incoming = {
            "facts": _set(facts),
            "locations": _set(locations),
            "agencies": _set(agencies),
            "types": _set(event_types),
            "entities": _set(entities),
        }
        incoming_title_tokens = _tokens(title)
        incoming_event_tokens = _tokens(event_key.replace("-", " "))
        incoming_casualties = _numeric_casualty_signatures(incoming["facts"])

        best: StoryRelationship | None = None

        for story in stories:
            if story.get("status") == "archived":
                continue
            story_id = str(story.get("story_id", "")).strip()
            if not story_id:
                continue

            known = {
                "facts": _set(story.get("facts", ())),
                "locations": _set(story.get("locations", ())),
                "agencies": _set(story.get("agencies", ())),
                "types": _set(story.get("event_types", ())),
                "entities": _set(story.get("entities", ())),
            }

            # Concrete contradictions always win over similarity.
            if incoming["locations"] and known["locations"] and not incoming["locations"] & known["locations"]:
                continue
            if incoming["agencies"] and known["agencies"] and not incoming["agencies"] & known["agencies"]:
                continue
            if incoming["types"] and known["types"] and not incoming["types"] & known["types"]:
                continue

            known_casualties = _numeric_casualty_signatures(known["facts"])
            if incoming_casualties and known_casualties:
                incoming_terms = {term for term, _ in incoming_casualties}
                known_terms = {term for term, _ in known_casualties}
                shared_terms = incoming_terms & known_terms
                if any(
                    {number for term, number in incoming_casualties if term == casualty_term}
                    != {number for term, number in known_casualties if term == casualty_term}
                    for casualty_term in shared_terms
                ):
                    continue

            scores = {key: _overlap(incoming[key], known[key]) for key in incoming}
            known_title_tokens = _tokens(story.get("canonical_title", "")) | set(story.get("title_tokens", ()))
            title_score = _overlap(incoming_title_tokens, known_title_tokens)
            known_event_tokens: set[str] = set()
            for known_event in story.get("events", ()):
                known_event_tokens |= _tokens(str(known_event).replace("-", " "))
            event_score = _overlap(incoming_event_tokens, known_event_tokens)

            location_match = bool(incoming["locations"] & known["locations"])
            agency_match = bool(incoming["agencies"] & known["agencies"])
            type_match = bool(incoming["types"] & known["types"])
            entity_match = bool(incoming["entities"] & known["entities"])
            fact_score = scores["facts"]
            lifecycle_signal = bool(incoming_title_tokens & _FOLLOW_UP_MARKERS)

            # Strong fact continuity plus concrete identity anchors is enough to
            # establish that a later event belongs to the same developing story.
            strong_public_safety_follow_up = (
                type_match
                and location_match
                and fact_score >= 0.66
                and (lifecycle_signal or agency_match or entity_match)
            )
            strong_agency_follow_up = (
                type_match
                and location_match
                and agency_match
                and fact_score >= 0.50
            )
            strong_entity_follow_up = (
                type_match
                and (location_match or agency_match)
                and entity_match
                and fact_score >= 0.40
            )
            lifecycle_follow_up = (
                lifecycle_signal
                and type_match
                and (location_match or agency_match or entity_match)
                and fact_score >= 0.50
            )
            unstructured_lifecycle_follow_up = (
                lifecycle_signal
                and fact_score >= 0.66
                and (title_score >= 0.35 or event_score >= 0.35)
            )

            eligible = any((
                strong_public_safety_follow_up,
                strong_agency_follow_up,
                strong_entity_follow_up,
                lifecycle_follow_up,
                unstructured_lifecycle_follow_up,
            ))
            if not eligible:
                continue

            anchor_score = (
                0.18 * float(location_match)
                + 0.18 * float(agency_match)
                + 0.14 * float(type_match)
                + 0.18 * float(entity_match)
            )
            if unstructured_lifecycle_follow_up:
                confidence = min(
                    1.0,
                    0.52 + 0.30 * fact_score + 0.10 * title_score + 0.08 * event_score,
                )
            else:
                confidence = min(
                    1.0,
                    0.42 * fact_score
                    + anchor_score
                    + 0.05 * title_score
                    + 0.03 * event_score
                    + 0.08 * float(lifecycle_signal),
                )
            if confidence < self.FOLLOW_UP_THRESHOLD:
                continue

            trace = (
                f"Relationship: {StoryRelationshipType.FOLLOW_UP.value}",
                f"Facts overlap: {fact_score:.2f}",
                f"Location match: {location_match}",
                f"Agency match: {agency_match}",
                f"Event type match: {type_match}",
                f"Entity match: {entity_match}",
                f"Lifecycle signal: {lifecycle_signal}",
                f"Confidence: {confidence:.2f}",
                f"Threshold: {self.FOLLOW_UP_THRESHOLD:.2f}",
            )
            candidate = StoryRelationship(
                StoryRelationshipType.FOLLOW_UP,
                story_id,
                confidence,
                "Attached distinct event as a follow-up to an existing developing story",
                trace,
            )
            if best is None or candidate.confidence > best.confidence:
                best = candidate

        if best is not None:
            return best
        return StoryRelationship(
            StoryRelationshipType.NEW_STORY,
            None,
            0.0,
            "Created new story: no supported cross-event relationship was found",
            ("Relationship: new_story",),
        )
