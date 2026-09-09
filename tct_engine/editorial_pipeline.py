"""Editorial processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .canonical_story import CanonicalStoryManager, StoryCandidate
from .editorial_decision import EditorialDecisionInput, decide_editorial_action
from .story_evolution import (
    IncomingStoryUpdate,
    StorySnapshot,
    evaluate_story_update,
)
from .story_registry import StoryRegistry
from .story_timeline import TimelineEntry


@dataclass(frozen=True, slots=True)
class PipelineArticle:
    article_id: str
    event_key: str
    title: str
    source: str
    url: str
    is_custom: bool
    facts: tuple[str, ...]
    locations: tuple[str, ...] = ()
    agencies: tuple[str, ...] = ()
    event_types: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    county: str = ""
    status: str = "developing"
    is_major: bool = False
    is_correction: bool = False
    published_at: datetime | None = None
    source_class: str = "unknown"
    source_trust: int = 50
    unified_incident_evidence: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class EditorialPipelineResult:
    action: object
    event_key: str
    canonical_article_id: str
    new_facts: tuple[str, ...]
    is_major: bool
    story_id: str = ""
    relationship: str = "new_story"
    relationship_confidence: float = 0.0
    relationship_reason: str = ""
    decision_trace: tuple[str, ...] = ()
    follow_up_candidate_story_id: str = ""
    follow_up_candidate_confidence: float = 0.0
    follow_up_candidate_milestones: tuple[str, ...] = ()
    follow_up_candidate_reason_codes: tuple[str, ...] = ()
    follow_up_candidate_trace: tuple[str, ...] = ()
    follow_up_candidate_mode: str = "observe_only"


class EditorialPipeline:
    """
    Preserve event-level editorial decisions while assigning each event to a
    persistent, potentially multi-event story.
    """

    def __init__(
        self,
        *,
        registry_path: str | Path = "story-registry.json",
    ) -> None:
        self._stories = CanonicalStoryManager()
        self._registry = StoryRegistry(registry_path)
        self._snapshots: dict[str, StorySnapshot] = {}

    def defer_registry_saves(self, *, commit: bool = True):
        """Return a context manager that batches persistent registry writes."""
        return self._registry.defer_saves(commit=commit)

    def quarantine_registry_contamination(self):
        """Revoke active authority for stories contaminated during this batch."""
        return self._registry.quarantine_active_contamination()

    def export_replay_state(self) -> dict[str, object]:
        """Serialize only the derived event state needed to resume exactly.

        The persistent ``StoryRegistry`` remains the authority for cross-event story
        identity.  This snapshot covers the two in-memory structures that historically
        required replaying the entire editorial journal on every process start:
        canonical candidates per event and the latest event snapshot used by update
        classification.  It is a cache of derived state, never an authority boundary.
        """
        candidates: list[dict[str, object]] = []
        for event_key in sorted(self._stories._candidates):
            event_candidates = self._stories._candidates[event_key]
            for article_id in sorted(event_candidates):
                candidate = event_candidates[article_id]
                candidates.append({
                    "article_id": candidate.article_id,
                    "event_key": candidate.event_key,
                    "title": candidate.title,
                    "source": candidate.source,
                    "url": candidate.url,
                    "is_custom": candidate.is_custom,
                    "published_at": candidate.published_at.isoformat(),
                })

        snapshots = [
            {
                "event_key": snapshot.event_key,
                "facts": list(snapshot.facts),
                "status": snapshot.status,
            }
            for _, snapshot in sorted(self._snapshots.items())
        ]
        return {
            "version": 1,
            "candidates": candidates,
            "snapshots": snapshots,
        }

    def restore_replay_state(self, payload: object) -> dict[str, int]:
        """Restore a validated derived-state snapshot atomically.

        Any malformed snapshot raises ``ValueError`` before mutating the live pipeline.
        The caller can then fall back to the historical replay path, preserving the
        exact pre-optimization behavior rather than accepting partial state.
        """
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("unsupported editorial pipeline replay-state version")
        candidate_rows = payload.get("candidates")
        snapshot_rows = payload.get("snapshots")
        if not isinstance(candidate_rows, list) or not isinstance(snapshot_rows, list):
            raise ValueError("invalid editorial pipeline replay-state shape")

        restored_stories = CanonicalStoryManager()
        restored_snapshots: dict[str, StorySnapshot] = {}

        for index, row in enumerate(candidate_rows):
            if not isinstance(row, dict):
                raise ValueError(f"invalid replay candidate at index {index}")
            try:
                article_id = str(row["article_id"]).strip()
                event_key = str(row["event_key"]).strip()
                title = str(row["title"]).strip()
                source = str(row["source"]).strip()
                url = str(row.get("url") or "")
                is_custom = bool(row.get("is_custom", False))
                published_raw = str(row["published_at"]).strip()
                published_at = datetime.fromisoformat(published_raw)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid replay candidate at index {index}") from exc
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            restored_stories.add(
                StoryCandidate(
                    article_id=article_id,
                    event_key=event_key,
                    title=title,
                    source=source,
                    url=url,
                    is_custom=is_custom,
                    published_at=published_at,
                )
            )

        for index, row in enumerate(snapshot_rows):
            if not isinstance(row, dict):
                raise ValueError(f"invalid replay snapshot at index {index}")
            event_key = str(row.get("event_key") or "").strip()
            facts = row.get("facts")
            status = str(row.get("status") or "developing")
            if not event_key or not isinstance(facts, list) or not all(
                isinstance(fact, str) for fact in facts
            ):
                raise ValueError(f"invalid replay snapshot at index {index}")
            if event_key in restored_snapshots:
                raise ValueError(f"duplicate replay snapshot for {event_key}")
            restored_snapshots[event_key] = StorySnapshot(
                event_key=event_key,
                facts=tuple(facts),
                status=status,
            )

        candidate_event_keys = set(restored_stories._candidates)
        snapshot_event_keys = set(restored_snapshots)
        if candidate_event_keys != snapshot_event_keys:
            raise ValueError("replay candidates and snapshots cover different events")

        self._stories = restored_stories
        self._snapshots = restored_snapshots
        return {
            "candidate_count": len(candidate_rows),
            "event_count": len(snapshot_rows),
        }

    def _record_timeline_entry(
        self,
        *,
        story_id: str,
        article: PipelineArticle,
        action: object,
        canonical_article_id: str,
    ) -> None:
        action_value = getattr(action, "value", str(action))
        self._registry.add_timeline_entry(
            story_id,
            TimelineEntry(
                event_key=article.event_key,
                article_id=article.article_id,
                published_at=(
                    article.published_at or datetime.now(timezone.utc)
                ),
                title=article.title,
                source=article.source,
                url=article.url,
                editorial_action=str(action_value),
                canonical_article_id=canonical_article_id,
            ),
        )

    def process(self, article: PipelineArticle) -> EditorialPipelineResult:
        # Story resolution is intentionally separate from event-level duplicate
        # and update decisions. Different events may share one story, but their
        # canonical candidates and snapshots remain event-scoped.
        story_id = self._registry.resolve_article(
            event_key=article.event_key,
            title=article.title,
            facts=article.facts,
            locations=article.locations,
            agencies=article.agencies,
            event_types=article.event_types,
            entities=article.entities,
            published_at=article.published_at,
            county=article.county,
            source=article.source,
            is_custom=article.is_custom,
            source_class=article.source_class,
            source_trust=article.source_trust,
            unified_incident_evidence=article.unified_incident_evidence,
        )
        relationship_decision = dict(self._registry.last_decision or {})

        # A verified unified-incident match can arrive under a different sparse or
        # publisher-derived event key. Route event-level canonical decisions through
        # the already established event so the same incident cannot publish a second
        # article merely because its generated key drifted. The incoming event key is
        # still retained in the persistent registry and timeline as an alias/evidence
        # trail.
        decision_event_key = article.event_key
        if (
            relationship_decision.get("identity_contract") == "unified_incident_v1"
            and relationship_decision.get("relationship") == "same_event"
        ):
            matched_story = self._registry.get_story(story_id) or {}
            for known_event_key in matched_story.get("events", ()):
                known_event_key = str(known_event_key or "").strip()
                if (
                    known_event_key
                    and known_event_key != article.event_key
                    and self._stories.get(known_event_key) is not None
                    and known_event_key in self._snapshots
                ):
                    decision_event_key = known_event_key
                    break

        existing_snapshot = self._snapshots.get(decision_event_key)
        existing_canonical = self._stories.get(decision_event_key)

        candidate = StoryCandidate(
            article_id=article.article_id,
            event_key=decision_event_key,
            title=article.title,
            source=article.source,
            url=article.url,
            is_custom=article.is_custom,
            published_at=article.published_at or datetime.now(timezone.utc),
        )

        canonical = self._stories.add(candidate)

        if existing_snapshot is None:
            self._snapshots[decision_event_key] = StorySnapshot(
                event_key=decision_event_key,
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

            self._record_timeline_entry(
                story_id=story_id,
                article=article,
                action=decision.action,
                canonical_article_id=canonical.canonical.article_id,
            )

            return EditorialPipelineResult(
                action=decision.action,
                event_key=decision_event_key,
                canonical_article_id=canonical.canonical.article_id,
                new_facts=article.facts,
                is_major=article.is_major,
                story_id=story_id,
                relationship=str(relationship_decision.get("relationship", "new_story")),
                relationship_confidence=float(relationship_decision.get("confidence", 0.0) or 0.0),
                relationship_reason=str(relationship_decision.get("reason", "")),
                decision_trace=tuple(relationship_decision.get("decision_trace", ()) or ()),
                follow_up_candidate_story_id=str(relationship_decision.get("follow_up_candidate_story_id", "")),
                follow_up_candidate_confidence=float(relationship_decision.get("follow_up_candidate_confidence", 0.0) or 0.0),
                follow_up_candidate_milestones=tuple(relationship_decision.get("follow_up_candidate_milestones", ()) or ()),
                follow_up_candidate_reason_codes=tuple(relationship_decision.get("follow_up_candidate_reason_codes", ()) or ()),
                follow_up_candidate_trace=tuple(relationship_decision.get("follow_up_candidate_trace", ()) or ()),
                follow_up_candidate_mode=str(relationship_decision.get("follow_up_candidate_mode", "observe_only")),
            )

        update = evaluate_story_update(
            existing_snapshot,
            IncomingStoryUpdate(
                event_key=decision_event_key,
                facts=article.facts,
                status=article.status,
                is_major=article.is_major,
                is_correction=article.is_correction,
            ),
        )

        self._snapshots[decision_event_key] = StorySnapshot(
            event_key=decision_event_key,
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

        self._record_timeline_entry(
            story_id=story_id,
            article=article,
            action=decision.action,
            canonical_article_id=canonical.canonical.article_id,
        )

        return EditorialPipelineResult(
            action=decision.action,
            event_key=decision_event_key,
            canonical_article_id=canonical.canonical.article_id,
            new_facts=update.new_facts,
            is_major=article.is_major,
            story_id=story_id,
            relationship=str(relationship_decision.get("relationship", "new_story")),
            relationship_confidence=float(relationship_decision.get("confidence", 0.0) or 0.0),
            relationship_reason=str(relationship_decision.get("reason", "")),
            decision_trace=tuple(relationship_decision.get("decision_trace", ()) or ()),
            follow_up_candidate_story_id=str(relationship_decision.get("follow_up_candidate_story_id", "")),
            follow_up_candidate_confidence=float(relationship_decision.get("follow_up_candidate_confidence", 0.0) or 0.0),
            follow_up_candidate_milestones=tuple(relationship_decision.get("follow_up_candidate_milestones", ()) or ()),
            follow_up_candidate_reason_codes=tuple(relationship_decision.get("follow_up_candidate_reason_codes", ()) or ()),
            follow_up_candidate_trace=tuple(relationship_decision.get("follow_up_candidate_trace", ()) or ()),
            follow_up_candidate_mode=str(relationship_decision.get("follow_up_candidate_mode", "observe_only")),
        )

    def get_event(self, event_key: str):
        return self._stories.get(event_key)

    def get_story(self, story_id: str):
        return self._registry.get_story(story_id)

    def get_story_for_event(self, event_key: str):
        return self._registry.get_story_for_event(event_key)

    def get_story_timeline(self, story_id: str):
        return self._registry.get_timeline(story_id)

    def get_story_importance(self, story_id: str):
        return self._registry.get_importance(story_id)

    def get_top_stories(self, limit: int = 10):
        return self._registry.get_top_stories(limit=limit)

    def get_breaking_stories(self):
        return self._registry.get_breaking_stories()

    def get_registry_health(self):
        return self._registry.get_registry_health()
