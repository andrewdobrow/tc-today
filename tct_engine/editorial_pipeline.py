from .story_registry import StoryRegistry

"""Editorial processing pipeline."""


from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .canonical_story import (
    CanonicalStoryManager,
    StoryCandidate,
)
from .editorial_decision import (
    EditorialDecisionInput,
    decide_editorial_action,
)
from .story_evolution import (
    IncomingStoryUpdate,
    StorySnapshot,
    evaluate_story_update,
)


@dataclass(frozen=True, slots=True)
class PipelineArticle:
    article_id: str
    event_key: str
    title: str
    source: str
    url: str
    is_custom: bool
    facts: tuple[str, ...]
    status: str = "developing"
    is_major: bool = False
    is_correction: bool = False
    published_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class EditorialPipelineResult:
    action: object
    event_key: str
    canonical_article_id: str
    new_facts: tuple[str, ...]
    is_major: bool


class EditorialPipeline:

    def __init__(self) -> None:
        self._stories = CanonicalStoryManager()
        self._registry = StoryRegistry()
        self._snapshots: dict[str, StorySnapshot] = {}

    def process(
        self,
        article: PipelineArticle,
    ) -> EditorialPipelineResult:

        story_id = self._registry.resolve_story(article.event_key)

        existing_snapshot = self._snapshots.get(story_id)
        existing_canonical = self._stories.get(article.event_key)
        
        story_id = self._registry.resolve_story(article.event_key)

        candidate = StoryCandidate(
            article_id=article.article_id,
            event_key=article.event_key,
            title=article.title,
            source=article.source,
            url=article.url,
            is_custom=article.is_custom,
            published_at=article.published_at
            or datetime.now(timezone.utc),
        )

        canonical = self._stories.add(candidate)

        if existing_snapshot is None:

            self._snapshots[article.event_key] = StorySnapshot(
                event_key=article.event_key,
                facts=article.facts,
                status=article.status,
            )

            decision = decide_editorial_action(
                EditorialDecisionInput(
                    has_existing_story=False,
                    existing_is_custom=False,
                    incoming_is_custom=article.is_custom,
                    update_classification=None,
                )
            )

            return EditorialPipelineResult(
                action=decision.action,
                event_key=article.event_key,
                canonical_article_id=canonical.canonical.article_id,
                new_facts=article.facts,
                is_major=article.is_major,
            )

        update = evaluate_story_update(
            existing_snapshot,
            IncomingStoryUpdate(
                event_key=article.event_key,
                facts=article.facts,
                status=article.status,
                is_major=article.is_major,
                is_correction=article.is_correction,
            ),
        )

        self._snapshots[article.event_key] = StorySnapshot(
            event_key=article.event_key,
            facts=article.facts,
            status=article.status,
        )

        decision = decide_editorial_action(
            EditorialDecisionInput(
                has_existing_story=True,
                existing_is_custom=(
                    existing_canonical.canonical.is_custom
                    if existing_canonical is not None
                    else False
                ),
                incoming_is_custom=article.is_custom,
                update_classification=update.classification,
            )
        )

        return EditorialPipelineResult(
            action=decision.action,
            event_key=article.event_key,
            canonical_article_id=canonical.canonical.article_id,
            new_facts=update.new_facts,
            is_major=article.is_major,
        )

    def get_event(self, event_key: str):
        return self._stories.get(event_key)
