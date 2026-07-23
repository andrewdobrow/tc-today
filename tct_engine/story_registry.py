"""Persistent story identity and cross-event grouping."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from .story_importance import StoryImportance, StoryImportanceEngine, ImportanceLevel
from .story_resolver import StoryResolver
from .story_timeline import StoryTimeline, TimelineEntry
from .editorial_policy import EditorialPolicy

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _WORD_RE.findall((value or "").lower())
        if len(token) >= 3
    }


class StoryRegistry:
    SCHEMA_VERSION = 4

    def __init__(self, filename: str | Path = "story-registry.json") -> None:
        self.path = Path(filename)
        self._resolver = StoryResolver()
        self._importance = StoryImportanceEngine()
        self._policy = EditorialPolicy()
        self.data = self._load()

    def _empty(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA_VERSION,
            "next_story_id": 1,
            "stories": {},
            "event_to_story": {},
            "story_aliases": {},
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Story registry must contain a JSON object")

        payload.setdefault("schema", 1)
        payload.setdefault("next_story_id", 1)
        payload.setdefault("stories", {})
        payload.setdefault("event_to_story", {})
        payload.setdefault("story_aliases", {})

        # Backward-compatible migration from the original minimal registry.
        for story_id, story in payload["stories"].items():
            story.setdefault("story_id", story_id)
            story.setdefault("events", [])
            story.setdefault("status", "developing")
            story.setdefault("titles", [])
            story.setdefault("title_tokens", [])
            story.setdefault("fact_tokens", [])
            story.setdefault("facts", [])
            story.setdefault("locations", [])
            story.setdefault("agencies", [])
            story.setdefault("event_types", [])
            story.setdefault("resolution_history", [])
            story.setdefault("custom_article_count", 0)
            story.setdefault("sources", [])
            story.setdefault("title_candidates", [])
            story.setdefault("canonical_title", story.get("titles", [""])[0] if story.get("titles") else "")
            story["timeline"] = StoryTimeline.from_list(
                story.get("timeline", [])
            ).to_list()
            story["importance"] = self._importance.score(story).to_dict()

        payload["schema"] = self.SCHEMA_VERSION
        return payload

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def _canonical_story_id(self, story_id: str) -> str:
        aliases = self.data["story_aliases"]
        seen: set[str] = set()
        current = story_id

        while current in aliases and current not in seen:
            seen.add(current)
            current = aliases[current]

        return current

    def _new_story(self, event_key: str) -> str:
        story_id = f"story_{self.data['next_story_id']:06d}"
        self.data["next_story_id"] += 1
        self.data["stories"][story_id] = {
            "story_id": story_id,
            "events": [event_key],
            "status": "developing",
            "titles": [],
            "title_tokens": [],
            "fact_tokens": [],
            "facts": [],
            "locations": [],
            "agencies": [],
            "event_types": [],
            "resolution_history": [],
            "timeline": [],
            "custom_article_count": 0,
            "sources": [],
            "title_candidates": [],
            "canonical_title": "",
            "importance": StoryImportance(score=0, level=ImportanceLevel.LOW).to_dict(),
        }
        self.data["event_to_story"][event_key] = story_id
        return story_id

    def resolve_story(self, event_key: str) -> str:
        mapped = self.data["event_to_story"].get(event_key)
        if mapped:
            return self._canonical_story_id(mapped)

        story_id = self._new_story(event_key)
        self.save()
        return story_id

    def resolve_article(
        self,
        *,
        event_key: str,
        title: str,
        facts: Iterable[str],
        locations: Iterable[str] = (),
        agencies: Iterable[str] = (),
        event_types: Iterable[str] = (),
        source: str = "",
        is_custom: bool = False,
        source_class: str = "unknown",
        source_trust: int = 50,
    ) -> str:
        mapped = self.data["event_to_story"].get(event_key)
        if mapped:
            story_id = self._canonical_story_id(mapped)
            self._enrich_story(
                story_id,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                source=source,
                is_custom=is_custom,
                source_class=source_class,
                source_trust=source_trust,
            )
            self._recalculate_importance(story_id)
            self.save()
            return story_id

        resolution = self._resolver.resolve(
            event_key=event_key,
            title=title,
            facts=facts,
            locations=locations,
            agencies=agencies,
            event_types=event_types,
            stories=self.iter_stories(),
        )

        if resolution.merge and resolution.story_id:
            story_id = self._canonical_story_id(resolution.story_id)
            self.attach_event(story_id, event_key, save=False)
        else:
            story_id = self._new_story(event_key)

        self._enrich_story(
            story_id,
            title=title,
            facts=facts,
            locations=locations,
            agencies=agencies,
            event_types=event_types,
            source=source,
            is_custom=is_custom,
            source_class=source_class,
            source_trust=source_trust,
        )
        self._recalculate_importance(story_id)
        story = self.data["stories"][story_id]
        story["resolution_history"].append(
            {
                "event_key": event_key,
                "confidence": round(resolution.confidence, 6),
                "reason": resolution.reason,
                "matched_existing": bool(resolution.merge),
            }
        )
        self.save()
        return story_id

    def _enrich_story(
        self,
        story_id: str,
        *,
        title: str,
        facts: Iterable[str],
        locations: Iterable[str] = (),
        agencies: Iterable[str] = (),
        event_types: Iterable[str] = (),
        source: str = "",
        is_custom: bool = False,
        source_class: str = "unknown",
        source_trust: int = 50,
    ) -> None:
        story = self.data["stories"][self._canonical_story_id(story_id)]

        if title and title not in story["titles"]:
            story["titles"].append(title)

        if title:
            candidates = story.setdefault("title_candidates", [])
            candidate = {
                "title": title,
                "source": source,
                "source_class": source_class,
                "source_trust": int(source_trust),
                "is_custom": bool(is_custom),
                "priority": 100 if is_custom else self._policy.source_profile("").canonical_priority,
            }
            candidate["priority"] = 100 if is_custom else int(
                self._policy.data.get("canonical_priority", {}).get(source_class, 50)
            )
            if candidate not in candidates:
                candidates.append(candidate)
            best = max(
                candidates,
                key=lambda item: (
                    int(item.get("priority", 0)),
                    int(item.get("source_trust", 0)),
                    len(str(item.get("title", ""))),
                ),
            )
            story["canonical_title"] = str(best.get("title", title))

        title_tokens = set(story["title_tokens"])
        title_tokens.update(_tokens(title))
        story["title_tokens"] = sorted(title_tokens)

        fact_values = {str(value).strip() for value in story["facts"] if str(value).strip()}
        fact_values.update(str(value).strip() for value in facts if str(value).strip())
        story["facts"] = sorted(fact_values)

        fact_tokens = set(story["fact_tokens"])
        for fact in fact_values:
            fact_tokens.update(_tokens(fact))
        story["fact_tokens"] = sorted(fact_tokens)

        for field, values in (
            ("locations", locations),
            ("agencies", agencies),
            ("event_types", event_types),
        ):
            existing = {
                str(value).strip()
                for value in story[field]
                if str(value).strip()
            }
            existing.update(
                str(value).strip()
                for value in values
                if str(value).strip()
            )
            story[field] = sorted(existing)

        if source:
            sources = set(story.get("sources", []))
            sources.add(source)
            story["sources"] = sorted(sources)
        if is_custom:
            story["custom_article_count"] = int(story.get("custom_article_count", 0)) + 1

    def _recalculate_importance(self, story_id: str) -> StoryImportance:
        canonical_id = self._canonical_story_id(story_id)
        story = self.data["stories"][canonical_id]
        importance = self._importance.score(story)
        story["importance"] = importance.to_dict()
        return importance

    def attach_event(
        self,
        story_id: str,
        event_key: str,
        *,
        save: bool = True,
    ) -> str:
        canonical_id = self._canonical_story_id(story_id)
        story = self.data["stories"][canonical_id]

        if event_key not in story["events"]:
            story["events"].append(event_key)

        self.data["event_to_story"][event_key] = canonical_id
        if save:
            self.save()
        return canonical_id

    def merge_events(self, primary_event: str, secondary_event: str) -> str:
        primary_story = self.resolve_story(primary_event)
        secondary_story = self.resolve_story(secondary_event)

        if primary_story == secondary_story:
            return primary_story

        primary = self.data["stories"][primary_story]
        secondary = self.data["stories"][secondary_story]

        for event_key in secondary["events"]:
            if event_key not in primary["events"]:
                primary["events"].append(event_key)
            self.data["event_to_story"][event_key] = primary_story

        for field in (
            "titles",
            "title_tokens",
            "fact_tokens",
            "facts",
            "locations",
            "agencies",
            "event_types",
        ):
            primary[field] = sorted(set(primary[field]) | set(secondary[field]))

        primary["resolution_history"].extend(secondary["resolution_history"])
        primary["custom_article_count"] = (
            int(primary.get("custom_article_count", 0))
            + int(secondary.get("custom_article_count", 0))
        )
        primary["sources"] = sorted(
            set(primary.get("sources", [])) | set(secondary.get("sources", []))
        )

        primary_timeline = StoryTimeline.from_list(primary.get("timeline", []))
        secondary_timeline = StoryTimeline.from_list(
            secondary.get("timeline", [])
        )
        primary_timeline.extend(secondary_timeline.entries)
        primary["timeline"] = primary_timeline.to_list()
        self.data["story_aliases"][secondary_story] = primary_story
        del self.data["stories"][secondary_story]
        self._recalculate_importance(primary_story)
        self.save()
        return primary_story


    def add_timeline_entry(
        self,
        story_id: str,
        entry: TimelineEntry,
        *,
        save: bool = True,
    ) -> bool:
        """Append one distinct event milestone to a story timeline."""

        canonical_id = self._canonical_story_id(story_id)
        story = self.data["stories"].get(canonical_id)
        if story is None:
            raise KeyError(f"Unknown story ID: {story_id}")

        timeline = StoryTimeline.from_list(story.get("timeline", []))
        added = timeline.add(entry)
        if not added:
            return False

        story["timeline"] = timeline.to_list()
        self._recalculate_importance(canonical_id)
        if save:
            self.save()
        return True

    def get_timeline(self, story_id: str) -> StoryTimeline | None:
        canonical_id = self._canonical_story_id(story_id)
        story = self.data["stories"].get(canonical_id)
        if story is None:
            return None
        return StoryTimeline.from_list(story.get("timeline", []))

    def get_story(self, story_id: str) -> dict[str, Any] | None:
        canonical_id = self._canonical_story_id(story_id)
        story = self.data["stories"].get(canonical_id)
        return dict(story) if story is not None else None

    def get_story_for_event(self, event_key: str) -> dict[str, Any] | None:
        story_id = self.data["event_to_story"].get(event_key)
        return self.get_story(story_id) if story_id else None

    def get_importance(self, story_id: str) -> StoryImportance | None:
        canonical_id = self._canonical_story_id(story_id)
        story = self.data["stories"].get(canonical_id)
        if story is None:
            return None
        return StoryImportance.from_dict(story.get("importance"))

    def get_top_stories(
        self,
        limit: int = 10,
        *,
        include_archived: bool = False,
    ) -> tuple[dict[str, Any], ...]:
        if limit < 0:
            raise ValueError("limit must be non-negative")
        stories = list(self.iter_stories())
        if not include_archived:
            stories = [
                story for story in stories
                if StoryImportance.from_dict(story.get("importance")).level
                is not ImportanceLevel.ARCHIVED
            ]
        stories.sort(
            key=lambda story: (
                -StoryImportance.from_dict(story.get("importance")).score,
                str(story.get("story_id", "")),
            )
        )
        return tuple(stories[:limit])

    def get_breaking_stories(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            story
            for story in self.get_top_stories(limit=len(self.data["stories"]))
            if StoryImportance.from_dict(story.get("importance")).level
            is ImportanceLevel.BREAKING
        )

    def iter_stories(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            dict(self.data["stories"][story_id])
            for story_id in sorted(self.data["stories"])
        )
