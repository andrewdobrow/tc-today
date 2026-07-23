from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StoryResolution:

    merge: bool

    confidence: float

    reason: str


class StoryResolver:

    """
    Determines whether two different event keys
    are actually the same evolving story.
    """

    def should_merge(
        self,
        existing_snapshot,
        incoming_update,
    ) -> StoryResolution:

        existing = set(existing_snapshot.facts)

        incoming = set(incoming_update.facts)

        if not existing or not incoming:

            return StoryResolution(
                merge=False,
                confidence=0.0,
                reason="missing facts",
            )

        overlap = len(existing & incoming)

        union = len(existing | incoming)

        confidence = overlap / union

        return StoryResolution(
            merge=confidence >= 0.60,
            confidence=confidence,
            reason=f"{overlap}/{union} fact overlap",
        )
