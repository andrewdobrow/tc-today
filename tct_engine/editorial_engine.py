"""Production entry point for the TCT editorial engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .editorial_decision import EditorialAction
from .editorial_eligibility import EditorialEligibilityEngine, EligibilityStatus
from .editorial_pipeline import (
    EditorialPipeline,
    PipelineArticle,
)
from .event_key import generate_event_key
from .fact_extraction import extract_article_facts
from .rss_adapter import RSSArticleAdapter


_STATE_VERSION = 1


class EditorialStateError(ValueError):
    """Raised when saved editorial state cannot be loaded."""


@dataclass(frozen=True)
class EditorialEngineResult:
    action: EditorialAction
    article_id: str
    canonical_article_id: str
    event_key: str
    extracted_facts: tuple[str, ...]
    new_facts: tuple[str, ...]
    is_custom: bool
    story_id: str = ""
    eligibility_status: str = "publishable"
    eligibility_reasons: tuple[str, ...] = ()
    source_class: str = "unknown"
    source_trust: int = 50
    eligible: bool = True
    relationship: str = "new_story"
    relationship_confidence: float = 0.0
    relationship_reason: str = ""
    decision_trace: tuple[str, ...] = ()
    canonical_is_custom: bool = False
    canonical_title: str = ""
    canonical_source: str = ""
    canonical_url: str = ""


class EditorialEngine:
    """
    High-level production interface.

    Feed Entry
        ↓
    RSS Adapter
        ↓
    Fact Extraction
        ↓
    Event Key Generation
        ↓
    Editorial Pipeline
    """

    def __init__(
        self,
        *,
        custom_sources: set[str] | None = None,
        default_published_at: datetime | None = None,
        registry_path: str | Path = "story-registry.json",
    ) -> None:
        self._custom_sources = (
            set(custom_sources)
            if custom_sources is not None
            else {"Treasure Coast Today"}
        )

        self._default_published_at = default_published_at

        self._eligibility = EditorialEligibilityEngine()

        self._adapter = RSSArticleAdapter(
            custom_sources=self._custom_sources,
            default_published_at=default_published_at,
        )

        self.registry_path = Path(registry_path)

        self._pipeline = EditorialPipeline(
            registry_path=self.registry_path,
        )

        # A replayable journal provides persistence without exposing
        # private state from the lower-level pipeline components.
        self._history: list[dict[str, Any]] = []

    def process(
        self,
        entry: Mapping[str, Any],
        *,
        source: str,
        county: str | None = None,
        is_custom: bool | None = None,
    ) -> EditorialEngineResult:
        return self._process(
            entry,
            source=source,
            county=county,
            is_custom=is_custom,
            record_history=True,
        )

    def _process(
        self,
        entry: Mapping[str, Any],
        *,
        source: str,
        county: str | None,
        is_custom: bool | None,
        record_history: bool,
    ) -> EditorialEngineResult:
        eligibility = self._eligibility.evaluate(entry, source=source)

        # Non-news never reaches fact extraction, event resolution, timelines,
        # importance scoring, or the persistent story registry.
        if not eligibility.eligible:
            import hashlib
            title = str(entry.get("title") or "").strip()
            url = str(entry.get("link") or "").strip()
            article_id = str(entry.get("id") or entry.get("guid") or "").strip()
            if not article_id:
                article_id = "rejected_" + hashlib.sha256(
                    f"{source}|{title}|{url}".encode("utf-8")
                ).hexdigest()[:20]
            if record_history:
                self._history.append(
                    {
                        "entry": self._make_json_safe(dict(entry)),
                        "source": source,
                        "county": county,
                        "is_custom": is_custom,
                    }
                )
            return EditorialEngineResult(
                action=EditorialAction.IGNORE,
                article_id=article_id,
                canonical_article_id="",
                event_key="",
                extracted_facts=(),
                new_facts=(),
                is_custom=bool(is_custom),
                story_id="",
                eligibility_status=eligibility.status.value,
                eligibility_reasons=eligibility.reasons,
                source_class=eligibility.source_profile.source_class,
                source_trust=eligibility.source_profile.trust,
                eligible=False,
            )

        raw = self._adapter.convert(
            entry,
            source=source,
            county=county,
            is_custom=is_custom,
        )

        extracted = extract_article_facts(raw)
        event_key = generate_event_key(extracted)

        pipeline_result = self._pipeline.process(
            PipelineArticle(
                article_id=raw.article_id,
                title=raw.title,
                url=raw.url,
                event_key=event_key,
                facts=tuple(extracted.facts),
                locations=tuple(extracted.locations),
                agencies=tuple(extracted.agencies),
                event_types=tuple(extracted.event_types),
                entities=tuple(extracted.entities),
                county=raw.county or "",
                source=raw.source,
                is_custom=raw.is_custom,
                published_at=raw.published_at,
                source_class=eligibility.source_profile.source_class,
                source_trust=eligibility.source_profile.trust,
            )
        )

        canonical = self._pipeline.get_event(event_key)

        if canonical is None:
            raise RuntimeError(
                f"Editorial event was not created: {event_key}"
            )

        if record_history:
            self._history.append(
                {
                    "entry": self._make_json_safe(dict(entry)),
                    "source": source,
                    "county": county,
                    "is_custom": is_custom,
                }
            )

        return EditorialEngineResult(
            action=pipeline_result.action,
            article_id=raw.article_id,
            canonical_article_id=canonical.canonical.article_id,
            event_key=event_key,
            extracted_facts=tuple(sorted(extracted.facts)),
            new_facts=tuple(sorted(pipeline_result.new_facts)),
            is_custom=raw.is_custom,
            story_id=pipeline_result.story_id,
            eligibility_status=eligibility.status.value,
            eligibility_reasons=eligibility.reasons,
            source_class=eligibility.source_profile.source_class,
            source_trust=eligibility.source_profile.trust,
            eligible=True,
            relationship=pipeline_result.relationship,
            relationship_confidence=pipeline_result.relationship_confidence,
            relationship_reason=pipeline_result.relationship_reason,
            decision_trace=pipeline_result.decision_trace,
            canonical_is_custom=bool(canonical.canonical.is_custom),
            canonical_title=canonical.canonical.title,
            canonical_source=canonical.canonical.source,
            canonical_url=canonical.canonical.url,
        )

    def get_event(self, event_key: str):
        return self._pipeline.get_event(event_key)

    def get_story_timeline(self, story_id: str):
        return self._pipeline.get_story_timeline(story_id)

    def get_story_importance(self, story_id: str):
        return self._pipeline.get_story_importance(story_id)

    def get_top_stories(self, limit: int = 10):
        return self._pipeline.get_top_stories(limit=limit)

    def get_breaking_stories(self):
        return self._pipeline.get_breaking_stories()

    def get_registry_health(self):
        return self._pipeline.get_registry_health()

    def save(self, path: str | Path) -> None:
        """Save replayable editorial state to a JSON file."""

        state_path = Path(path)

        state_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "version": _STATE_VERSION,
            "articles": self._history,
        }

        temporary_path = state_path.with_suffix(
            state_path.suffix + ".tmp"
        )

        temporary_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # Atomic replacement helps prevent a partially written state file.
        temporary_path.replace(state_path)

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        custom_sources: set[str] | None = None,
        default_published_at: datetime | None = None,
        registry_path: str | Path = "story-registry.json",
    ) -> EditorialEngine:
        """Load saved state and rebuild the editorial pipeline."""

        state_path = Path(path)

        engine = cls(
            custom_sources=custom_sources,
            default_published_at=default_published_at,
            registry_path=registry_path,
        )

        if not state_path.exists():
            return engine

        try:
            payload = json.loads(
                state_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise EditorialStateError(
                "Editorial state file is not valid JSON."
            ) from exc
        except OSError as exc:
            raise EditorialStateError(
                f"Could not read editorial state: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise EditorialStateError(
                "Editorial state must contain a JSON object."
            )

        version = payload.get("version")

        if version != _STATE_VERSION:
            raise EditorialStateError(
                "Unsupported editorial state version: "
                f"{version!r}."
            )

        articles = payload.get("articles")

        if not isinstance(articles, list):
            raise EditorialStateError(
                "Editorial state articles must be a list."
            )

        registry_already_exists = Path(registry_path).exists()
        with engine._pipeline.defer_registry_saves(
            commit=not registry_already_exists
        ):
            for index, item in enumerate(articles):
                if not isinstance(item, dict):
                    raise EditorialStateError(
                        "Invalid article record at index "
                        f"{index}."
                    )

                entry = item.get("entry")
                source = item.get("source")

                if not isinstance(entry, dict):
                    raise EditorialStateError(
                        "Invalid article entry at index "
                        f"{index}."
                    )

                if not isinstance(source, str) or not source.strip():
                    raise EditorialStateError(
                        "Invalid article source at index "
                        f"{index}."
                    )

                county = item.get("county")
                is_custom = item.get("is_custom")

                engine._process(
                    entry,
                    source=source,
                    county=county,
                    is_custom=is_custom,
                    record_history=False,
                )

        # Preserve the original records exactly once. Replaying them above
        # rebuilds pipeline state but does not append them to history.
        engine._history = articles

        return engine

    @classmethod
    def _make_json_safe(cls, value: Any) -> Any:
        if value is None or isinstance(
            value,
            (str, int, float, bool),
        ):
            return value

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, Mapping):
            return {
                str(key): cls._make_json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple)):
            return [
                cls._make_json_safe(item)
                for item in value
            ]

        return str(value)