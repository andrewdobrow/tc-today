"""Conservative cross-event story resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Any

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "that", "the",
    "this", "to", "was", "were", "with", "after", "before", "new",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _WORD_RE.findall((value or "").lower())
        if len(token) >= 3 and token not in _STOP_WORDS
    }


def _fact_tokens(facts: Iterable[str]) -> set[str]:
    result: set[str] = set()
    for fact in facts:
        result.update(_tokens(fact))
    return result


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


@dataclass(frozen=True, slots=True)
class StoryResolution:
    story_id: str | None
    merge: bool
    confidence: float
    reason: str


class StoryResolver:
    """Select an existing persistent story for a new event, conservatively."""

    def resolve(
        self,
        *,
        event_key: str,
        title: str,
        facts: Iterable[str],
        stories: Iterable[Mapping[str, Any]],
    ) -> StoryResolution:
        incoming_event = _tokens(event_key.replace("-", " "))
        incoming_title = _tokens(title)
        incoming_facts = _fact_tokens(facts)

        best_story_id: str | None = None
        best_score = 0.0
        best_reason = "no sufficiently similar active story"

        for story in stories:
            if story.get("status", "developing") == "archived":
                continue

            story_id = str(story.get("story_id", "")).strip()
            if not story_id:
                continue

            event_tokens: set[str] = set()
            for known_event in story.get("events", ()):
                event_tokens.update(_tokens(str(known_event).replace("-", " ")))

            title_tokens = set(story.get("title_tokens", ()))
            fact_tokens = set(story.get("fact_tokens", ()))

            event_score = _jaccard(incoming_event, event_tokens)
            title_score = _jaccard(incoming_title, title_tokens)
            fact_score = _jaccard(incoming_facts, fact_tokens)

            # Facts carry the most weight. Event/title terms provide support.
            score = (0.55 * fact_score) + (0.25 * event_score) + (0.20 * title_score)

            shared_facts = len(incoming_facts & fact_tokens)
            shared_event_terms = len(incoming_event & event_tokens)

            # Guard against generic local-news overlap. Require either multiple
            # shared fact terms or a strong event-key relationship.
            eligible = (
                shared_facts >= 2
                or (shared_facts >= 1 and shared_event_terms >= 2)
                or event_score >= 0.72
            )

            if eligible and score > best_score:
                best_story_id = story_id
                best_score = score
                best_reason = (
                    f"fact={fact_score:.3f}, event={event_score:.3f}, "
                    f"title={title_score:.3f}"
                )

        # Deliberately conservative: false splits are safer than false merges.
        should_merge = best_story_id is not None and best_score >= 0.42

        return StoryResolution(
            story_id=best_story_id if should_merge else None,
            merge=should_merge,
            confidence=best_score,
            reason=best_reason,
        )
