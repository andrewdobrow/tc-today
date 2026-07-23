"""Conservative, deterministic cross-event story resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

_WORD_RE = re.compile(r"[a-z0-9]+")
_QUANTIFIED_FACT_RE = re.compile(r"^(\d+)\s+(.+)$")
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "that", "the",
    "this", "to", "was", "were", "with", "after", "before", "new",
}
_GENERIC_NEWS_TOKENS = {
    "arrest", "arrested", "charges", "closed", "closes", "crash",
    "deputies", "fire", "injured", "meeting", "person", "people",
    "reported", "rescue", "rescued", "road", "woman", "county",
}


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _normalized_set(values: Iterable[str]) -> set[str]:
    return {_normalize(str(value)) for value in values if _normalize(str(value))}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _WORD_RE.findall((value or "").lower())
        if len(token) >= 3 and token not in _STOP_WORDS
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _overlap_ratio(left: set[str], right: set[str]) -> float:
    """Measure how much of the smaller evidence set is shared."""
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def _fact_signature(value: str) -> tuple[str, str] | None:
    """Return a normalized numeric fact signature for conflict detection."""
    match = _QUANTIFIED_FACT_RE.match(_normalize(value))
    if not match:
        return None

    number, subject = match.groups()
    subject = re.sub(r"\bpeople\b", "person", subject)
    subject = re.sub(r"\bcats\b", "cat", subject)
    subject = re.sub(r"\bdogs\b", "dog", subject)
    return number, subject


def _has_quantified_conflict(left: set[str], right: set[str]) -> bool:
    left_signatures = {
        signature[1]: signature[0]
        for value in left
        if (signature := _fact_signature(value)) is not None
    }
    right_signatures = {
        signature[1]: signature[0]
        for value in right
        if (signature := _fact_signature(value)) is not None
    }

    return any(
        subject in right_signatures
        and number != right_signatures[subject]
        for subject, number in left_signatures.items()
    )


def _distinctive_title_tokens(
    title_tokens: set[str],
    locations: set[str],
) -> set[str]:
    location_tokens: set[str] = set()
    for location in locations:
        location_tokens.update(_tokens(location))

    return title_tokens - _GENERIC_NEWS_TOKENS - location_tokens


@dataclass(frozen=True, slots=True)
class StoryResolution:
    story_id: str | None
    merge: bool
    confidence: float
    reason: str


class StoryResolver:
    """Select an existing persistent story for a new event, conservatively."""

    MERGE_THRESHOLD = 0.60

    def resolve(
        self,
        *,
        event_key: str,
        title: str,
        facts: Iterable[str],
        locations: Iterable[str] = (),
        agencies: Iterable[str] = (),
        event_types: Iterable[str] = (),
        stories: Iterable[Mapping[str, Any]],
    ) -> StoryResolution:
        incoming_facts = _normalized_set(facts)
        incoming_locations = _normalized_set(locations)
        incoming_agencies = _normalized_set(agencies)
        incoming_event_types = _normalized_set(event_types)

        incoming_event_tokens = _tokens(event_key.replace("-", " "))
        incoming_title_tokens = _tokens(title)
        incoming_distinctive_tokens = _distinctive_title_tokens(
            incoming_title_tokens,
            incoming_locations,
        )

        best_story_id: str | None = None
        best_score = 0.0
        best_reason = "no sufficiently similar active story"

        for story in stories:
            if story.get("status", "developing") == "archived":
                continue

            story_id = str(story.get("story_id", "")).strip()
            if not story_id:
                continue

            known_facts = _normalized_set(story.get("facts", ()))
            known_locations = _normalized_set(story.get("locations", ()))
            known_agencies = _normalized_set(story.get("agencies", ()))
            known_event_types = _normalized_set(story.get("event_types", ()))

            # Conflicting structured identity is a hard stop. This prevents
            # same-topic stories in different counties or from different
            # agencies from being merged merely because their generic facts
            # and event types match.
            if (
                incoming_locations
                and known_locations
                and not (incoming_locations & known_locations)
            ):
                continue
            if (
                incoming_agencies
                and known_agencies
                and not (incoming_agencies & known_agencies)
            ):
                continue
            if _has_quantified_conflict(incoming_facts, known_facts):
                continue

            fact_score = _overlap_ratio(incoming_facts, known_facts)
            location_score = _overlap_ratio(incoming_locations, known_locations)
            agency_score = _overlap_ratio(incoming_agencies, known_agencies)
            event_type_score = _overlap_ratio(
                incoming_event_types,
                known_event_types,
            )

            event_tokens: set[str] = set()
            for known_event in story.get("events", ()):
                event_tokens.update(_tokens(str(known_event).replace("-", " ")))

            title_tokens = set(story.get("title_tokens", ()))
            event_key_score = _jaccard(incoming_event_tokens, event_tokens)
            title_score = _jaccard(incoming_title_tokens, title_tokens)
            known_distinctive_tokens = _distinctive_title_tokens(
                title_tokens,
                known_locations,
            )
            distinctive_overlap = bool(
                incoming_distinctive_tokens & known_distinctive_tokens
            )

            # Structured evidence drives the decision. Event-key and title
            # similarity are supporting signals only.
            weighted_signals = []
            if incoming_facts and known_facts:
                weighted_signals.append((0.45, fact_score))
            if incoming_locations and known_locations:
                weighted_signals.append((0.15, location_score))
            if incoming_agencies and known_agencies:
                weighted_signals.append((0.20, agency_score))
            if incoming_event_types and known_event_types:
                weighted_signals.append((0.20, event_type_score))

            available_weight = sum(weight for weight, _ in weighted_signals)
            structured_score = (
                sum(weight * value for weight, value in weighted_signals)
                / available_weight
                if available_weight
                else 0.0
            )
            support_score = (0.60 * event_key_score) + (0.40 * title_score)
            score = (0.90 * structured_score) + (0.10 * support_score)

            shared_facts = len(incoming_facts & known_facts)
            shared_locations = len(incoming_locations & known_locations)
            shared_agencies = len(incoming_agencies & known_agencies)
            shared_event_types = len(
                incoming_event_types & known_event_types
            )

            # False splits are safer than false merges. Require meaningful
            # factual overlap plus an identity anchor. A distinctive title
            # token can supply that anchor; otherwise event-key similarity
            # must be strong enough to indicate the same underlying incident.
            identity_anchor = distinctive_overlap or event_key_score >= 0.50
            eligible = identity_anchor and (
                shared_facts >= 2
                or (
                    shared_facts >= 1
                    and (
                        shared_locations >= 1
                        or shared_agencies >= 1
                        or shared_event_types >= 1
                    )
                    and (event_key_score >= 0.35 or title_score >= 0.25)
                )
            )

            if eligible and score > best_score:
                best_story_id = story_id
                best_score = score
                best_reason = (
                    f"facts={fact_score:.3f}, "
                    f"locations={location_score:.3f}, "
                    f"agencies={agency_score:.3f}, "
                    f"event_types={event_type_score:.3f}, "
                    f"event_key={event_key_score:.3f}, "
                    f"title={title_score:.3f}, "
                    f"distinctive_anchor={distinctive_overlap}"
                )

        should_merge = (
            best_story_id is not None
            and best_score >= self.MERGE_THRESHOLD
        )

        return StoryResolution(
            story_id=best_story_id if should_merge else None,
            merge=should_merge,
            confidence=best_score,
            reason=best_reason,
        )
