"""Persistent story identity and cross-event grouping."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
import re
from pathlib import Path
from typing import Any, Iterable

from .story_importance import StoryImportance, StoryImportanceEngine, ImportanceLevel
from .story_resolver import StoryResolution, StoryResolver
from .story_relationship import (
    StoryRelationship,
    StoryRelationshipEngine,
    StoryRelationshipType,
)
from .story_timeline import StoryTimeline, TimelineEntry
from .editorial_policy import EditorialPolicy
from .local_relevance import classify_local_relevance
from .story_lifecycle import classify_story_lifecycle
from .editorial_proximity import (
    calculate_editorial_score,
    classify_editorial_proximity,
    latest_story_timestamp,
    story_source_trust,
)
from .incident_identity import find_matching_incident_story
from .source_identity import find_matching_source_story
from .unified_incident_identity import (
    evidence_from_mapping,
    find_matching_unified_incident_story,
)
from .registry_repair import (
    choose_primary_story_id,
    is_sparse_event_key,
    is_broad_event_class_key,
    normalize_identity_title,
    normalize_title,
    repair_registry_payload,
    quarantine_active_story_contamination,
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _WORD_RE.findall((value or "").lower())
        if len(token) >= 3
    }


class StoryRegistry:
    SCHEMA_VERSION = 10
    RESOLUTION_HISTORY_LIMIT = 250
    UNIFIED_INCIDENT_EVIDENCE_LIMIT = 8
    UNIFIED_INCIDENT_EVIDENCE_PRESSURE_LIMIT = 4
    UNIFIED_INCIDENT_EVIDENCE_EMERGENCY_LIMIT = 2
    REGISTRY_PRESSURE_BYTES = 45 * 1024 * 1024
    REGISTRY_MAX_BYTES = 50 * 1024 * 1024

    @staticmethod
    def _resolution_history_key(entry: dict[str, Any]) -> str:
        """Return a deterministic key for one resolver decision record."""
        return json.dumps(
            entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )

    @classmethod
    def _compact_resolution_entries(
        cls, entries: Iterable[dict[str, Any]] | None
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """Keep newest unique resolver decisions and discard replay duplicates."""
        original = [entry for entry in (entries or ()) if isinstance(entry, dict)]
        seen: set[str] = set()
        newest_unique: list[dict[str, Any]] = []
        for entry in reversed(original):
            key = cls._resolution_history_key(entry)
            if key in seen:
                continue
            seen.add(key)
            newest_unique.append(entry)
            if len(newest_unique) >= cls.RESOLUTION_HISTORY_LIMIT:
                break
        compacted = list(reversed(newest_unique))
        unique_count = len({cls._resolution_history_key(entry) for entry in original})
        return compacted, {
            "entries_before": len(original),
            "entries_after": len(compacted),
            "duplicates_removed": max(0, len(original) - unique_count),
            "unique_entries_truncated": max(0, unique_count - len(compacted)),
        }

    @classmethod
    def _compact_unified_incident_evidence_entries(
        cls,
        entries: Iterable[dict[str, Any]] | None,
        *,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """Keep only newest unique candidate-only unified-incident evidence.

        These rows are diagnostic relationship evidence, not authoritative story
        identity. Persisting dozens of full evidence payloads per story caused the
        registry to grow beyond its 50 MiB safety ceiling and abort publication.
        """
        original = [entry for entry in (entries or ()) if isinstance(entry, dict)]
        effective_limit = max(1, int(limit or cls.UNIFIED_INCIDENT_EVIDENCE_LIMIT))
        seen: set[str] = set()
        newest_unique: list[dict[str, Any]] = []
        for entry in reversed(original):
            key = json.dumps(
                entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            if key in seen:
                continue
            seen.add(key)
            newest_unique.append(entry)
            if len(newest_unique) >= effective_limit:
                break
        compacted = list(reversed(newest_unique))
        unique_count = len({
            json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            for entry in original
        })
        return compacted, {
            "entries_before": len(original),
            "entries_after": len(compacted),
            "duplicates_removed": max(0, len(original) - unique_count),
            "unique_entries_truncated": max(0, unique_count - len(compacted)),
        }

    @classmethod
    def _compact_payload_unified_incident_evidence(
        cls, payload: dict[str, Any], *, limit: int | None = None
    ) -> dict[str, int]:
        totals = {
            "entries_before": 0,
            "entries_after": 0,
            "duplicates_removed": 0,
            "unique_entries_truncated": 0,
            "stories_compacted": 0,
        }
        stories = payload.get("stories", {})
        if not isinstance(stories, dict):
            return totals
        for story in stories.values():
            if not isinstance(story, dict):
                continue
            compacted, stats = cls._compact_unified_incident_evidence_entries(
                story.get("unified_incident_evidence"), limit=limit
            )
            if stats["entries_before"] != stats["entries_after"]:
                totals["stories_compacted"] += 1
            story["unified_incident_evidence"] = compacted
            for key in (
                "entries_before",
                "entries_after",
                "duplicates_removed",
                "unique_entries_truncated",
            ):
                totals[key] += stats[key]
        return totals

    @classmethod
    def _compact_payload_resolution_history(
        cls, payload: dict[str, Any]
    ) -> dict[str, int]:
        totals = {
            "entries_before": 0,
            "entries_after": 0,
            "duplicates_removed": 0,
            "unique_entries_truncated": 0,
            "stories_compacted": 0,
        }
        stories = payload.get("stories", {})
        if not isinstance(stories, dict):
            return totals
        for story in stories.values():
            if not isinstance(story, dict):
                continue
            compacted, stats = cls._compact_resolution_entries(
                story.get("resolution_history")
            )
            if stats["entries_before"] != stats["entries_after"]:
                totals["stories_compacted"] += 1
            story["resolution_history"] = compacted
            for key in (
                "entries_before",
                "entries_after",
                "duplicates_removed",
                "unique_entries_truncated",
            ):
                totals[key] += stats[key]
        return totals

    def _append_resolution_history(
        self, story: dict[str, Any], entry: dict[str, Any]
    ) -> bool:
        """Append one resolver decision only when it adds new audit evidence."""
        history = story.setdefault("resolution_history", [])
        key = self._resolution_history_key(entry)
        if any(
            isinstance(existing, dict)
            and self._resolution_history_key(existing) == key
            for existing in history
        ):
            return False
        history.append(entry)
        if len(history) > self.RESOLUTION_HISTORY_LIMIT:
            story["resolution_history"], _ = self._compact_resolution_entries(history)
        return True

    def __init__(self, filename: str | Path = "story-registry.json") -> None:
        self.path = Path(filename)
        self._save_defer_depth = 0
        self._save_pending = False
        self._resolver = StoryResolver()
        self._relationships = StoryRelationshipEngine()
        self._importance = StoryImportanceEngine()
        self._policy = EditorialPolicy()
        self.data = self._load()
        self.last_decision: dict[str, Any] = {}
        load_compaction = (self.data.get("history_compaction") or {}).get(
            "last_load", {}
        )
        if int(load_compaction.get("duplicates_removed", 0) or 0) > 0:
            print(
                "  Editorial registry history compacted: "
                f"{load_compaction.get('entries_before', 0)} -> "
                f"{load_compaction.get('entries_after', 0)} entries "
                f"({load_compaction.get('duplicates_removed', 0)} duplicates removed)"
            )
        repair_changed = bool(
            ((self.data.get("registry_repair") or {}).get("last_run") or {}).get(
                "changed", False
            )
        )
        history_compacted = bool(
            int(load_compaction.get("duplicates_removed", 0) or 0)
            or int(load_compaction.get("unique_entries_truncated", 0) or 0)
        )
        if repair_changed or history_compacted:
            self.save()

    @staticmethod
    def _follow_up_candidate_fields(relationship: StoryRelationship | None) -> dict[str, Any]:
        if relationship is None or not relationship.candidate_story_id:
            return {
                "follow_up_candidate_story_id": "",
                "follow_up_candidate_confidence": 0.0,
                "follow_up_candidate_milestones": [],
                "follow_up_candidate_reason_codes": [],
                "follow_up_candidate_trace": [],
                "follow_up_candidate_mode": "observe_only",
            }
        return {
            "follow_up_candidate_story_id": str(relationship.candidate_story_id),
            "follow_up_candidate_confidence": round(
                float(relationship.candidate_confidence or 0.0), 6
            ),
            "follow_up_candidate_milestones": list(
                relationship.candidate_milestones or ()
            ),
            "follow_up_candidate_reason_codes": list(
                relationship.candidate_reason_codes or ()
            ),
            "follow_up_candidate_trace": list(relationship.candidate_trace or ()),
            "follow_up_candidate_mode": "observe_only",
        }

    def _empty(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA_VERSION,
            "next_story_id": 1,
            "stories": {},
            "event_to_story": {},
            "story_aliases": {},
            "quarantined_stories": {},
            "registry_repair": {},
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
        payload.setdefault("quarantined_stories", {})
        payload.setdefault("registry_repair", {})

        # Backward-compatible migration from the original minimal registry.
        for story_id, story in payload["stories"].items():
            story.setdefault("story_id", story_id)
            story.setdefault("events", [])
            story.setdefault("status", "developing")
            story.setdefault("lifecycle", {})
            story.setdefault("lifecycle_history", [])
            story.setdefault("titles", [])
            story.setdefault("title_tokens", [])
            story.setdefault("fact_tokens", [])
            story.setdefault("facts", [])
            story.setdefault("locations", [])
            story.setdefault("agencies", [])
            story.setdefault("event_types", [])
            story.setdefault("entities", [])
            story.setdefault("unified_incident_evidence", [])
            story.setdefault("local_relevance", {"scope":"unknown","score":35,"counties":[],"places":[]})
            story.setdefault("resolution_history", [])
            story.setdefault("relationship_history", [])
            story.setdefault("editorial_proximity", {"score":35,"scope":"unknown","reason":"Not yet classified"})
            story.setdefault("editorial_priority", 0)
            story.setdefault("editorial_score", int(story.get("editorial_priority", 0) or 0))
            story.setdefault("score_breakdown", {})
            story.setdefault("custom_article_count", 0)
            story.setdefault("sources", [])
            story.setdefault("title_candidates", [])
            story.setdefault("canonical_title", story.get("titles", [""])[0] if story.get("titles") else "")
            story["timeline"] = StoryTimeline.from_list(story.get("timeline", [])).to_list()

        repair_registry_payload(payload)
        compaction = self._compact_payload_resolution_history(payload)
        previous_compaction = payload.get("history_compaction", {})
        payload["history_compaction"] = {
            "version": 1,
            "resolution_history_limit_per_story": self.RESOLUTION_HISTORY_LIMIT,
            "last_load": compaction,
            "total_duplicates_removed": int(
                (previous_compaction or {}).get("total_duplicates_removed", 0) or 0
            ) + compaction["duplicates_removed"],
            "total_unique_entries_truncated": int(
                (previous_compaction or {}).get("total_unique_entries_truncated", 0) or 0
            ) + compaction["unique_entries_truncated"],
        }

        for story in payload["stories"].values():
            story["importance"] = self._importance.score(story).to_dict()
            proximity = classify_editorial_proximity(story)
            story["editorial_proximity"] = proximity.to_dict()
            ranking = calculate_editorial_score(
                int((story.get("importance") or {}).get("score", 0) or 0),
                proximity.score,
                source_trust=story_source_trust(story),
                published_at=latest_story_timestamp(story),
            )
            story["editorial_score"] = ranking.score
            story["editorial_priority"] = ranking.score
            story["score_breakdown"] = ranking.to_dict()
            lifecycle = classify_story_lifecycle(story)
            story["lifecycle"] = lifecycle.to_dict()
            story["status"] = lifecycle.state.value

        payload["schema"] = self.SCHEMA_VERSION
        return payload

    def _find_exact_title_story(self, title: str) -> str | None:
        normalized = normalize_identity_title(title)
        if len(normalized.split()) < 4:
            return None

        matches: list[str] = []
        for story_id, story in self.data["stories"].items():
            known_titles = [story.get("canonical_title", ""), *story.get("titles", ())]
            if any(normalize_identity_title(value) == normalized for value in known_titles):
                matches.append(story_id)

        if not matches:
            return None
        return choose_primary_story_id(matches, self.data["stories"])

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        compaction = self._compact_payload_resolution_history(self.data)
        incident_compaction = self._compact_payload_unified_incident_evidence(self.data)
        report = self.data.setdefault("history_compaction", {})
        report.update({
            "version": 1,
            "resolution_history_limit_per_story": self.RESOLUTION_HISTORY_LIMIT,
            "unified_incident_evidence_limit_per_story": self.UNIFIED_INCIDENT_EVIDENCE_LIMIT,
            "last_write": compaction,
            "last_unified_incident_evidence_write": incident_compaction,
        })
        report["total_duplicates_removed"] = int(
            report.get("total_duplicates_removed", 0) or 0
        ) + compaction["duplicates_removed"]
        report["total_unique_entries_truncated"] = int(
            report.get("total_unique_entries_truncated", 0) or 0
        ) + compaction["unique_entries_truncated"]
        report["total_unified_incident_evidence_duplicates_removed"] = int(
            report.get("total_unified_incident_evidence_duplicates_removed", 0) or 0
        ) + incident_compaction["duplicates_removed"]
        report["total_unified_incident_evidence_truncated"] = int(
            report.get("total_unified_incident_evidence_truncated", 0) or 0
        ) + incident_compaction["unique_entries_truncated"]
        serialized = json.dumps(self.data, indent=2, ensure_ascii=False)
        size_bytes = len(serialized.encode("utf-8"))
        pressure_mode = "normal"
        if size_bytes > self.REGISTRY_PRESSURE_BYTES:
            pressure_compaction = self._compact_payload_unified_incident_evidence(
                self.data, limit=self.UNIFIED_INCIDENT_EVIDENCE_PRESSURE_LIMIT
            )
            report["last_unified_incident_evidence_pressure_write"] = pressure_compaction
            pressure_mode = "pressure"
            serialized = json.dumps(self.data, indent=2, ensure_ascii=False)
            size_bytes = len(serialized.encode("utf-8"))
        if size_bytes > self.REGISTRY_MAX_BYTES:
            emergency_compaction = self._compact_payload_unified_incident_evidence(
                self.data, limit=self.UNIFIED_INCIDENT_EVIDENCE_EMERGENCY_LIMIT
            )
            report["last_unified_incident_evidence_emergency_write"] = emergency_compaction
            pressure_mode = "emergency"
            serialized = json.dumps(self.data, indent=2, ensure_ascii=False)
            size_bytes = len(serialized.encode("utf-8"))
        report["last_serialized_bytes"] = size_bytes
        report["max_serialized_bytes"] = self.REGISTRY_MAX_BYTES
        report["pressure_serialized_bytes"] = self.REGISTRY_PRESSURE_BYTES
        report["last_pressure_mode"] = pressure_mode
        # Re-serialize once so the recorded byte count and pressure mode are present.
        serialized = json.dumps(self.data, indent=2, ensure_ascii=False)
        size_bytes = len(serialized.encode("utf-8"))
        if size_bytes > self.REGISTRY_MAX_BYTES:
            raise RuntimeError(
                "Editorial story registry exceeds the 50 MiB safety ceiling after "
                "adaptive candidate-evidence compaction: "
                f"{size_bytes / (1024 * 1024):.2f} MiB"
            )
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(serialized, encoding="utf-8")
        os.replace(temporary, self.path)

    def save(self) -> None:
        """Persist immediately unless a bulk operation has deferred writes."""
        if self._save_defer_depth:
            self._save_pending = True
            return
        self._write()

    def quarantine_active_contamination(self) -> dict[str, tuple[str, ...]]:
        """Fail closed on story contamination introduced after registry load.

        This is called at a production audit batch boundary, after the article's
        timeline entry has been recorded.  A contaminated story is removed from
        active identity authority instead of being allowed to abort the entire site
        build several minutes later at the final publication gate.
        """
        quarantined = quarantine_active_story_contamination(self.data)
        if quarantined:
            self._write()
        return quarantined

    @contextmanager
    def defer_saves(self, *, commit: bool = True):
        """Coalesce repeated registry saves into at most one atomic write.

        Historical state replay can use ``commit=False`` when an existing
        persistent registry is already authoritative. The replayed state remains
        available to the current process, but the multi-megabyte registry is not
        rewritten once per historical article.
        """
        outermost = self._save_defer_depth == 0
        self._save_defer_depth += 1
        failed = False
        try:
            yield self
        except Exception:
            failed = True
            raise
        finally:
            self._save_defer_depth -= 1
            if outermost:
                pending = self._save_pending
                self._save_pending = False
                if pending and commit and not failed:
                    self._write()

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
            "status": "active",
            "lifecycle": {},
            "lifecycle_history": [],
            "titles": [],
            "title_tokens": [],
            "fact_tokens": [],
            "facts": [],
            "locations": [],
            "agencies": [],
            "event_types": [],
            "entities": [],
            "unified_incident_evidence": [],
            "local_relevance": {"scope":"unknown","score":35,"counties":[],"places":[]},
            "resolution_history": [],
            "relationship_history": [],
            "editorial_proximity": {"score":35,"scope":"unknown","reason":"Not yet classified"},
            "editorial_priority": 0,
            "editorial_score": 0,
            "score_breakdown": {},
            "timeline": [],
            "custom_article_count": 0,
            "sources": [],
            "title_candidates": [],
            "canonical_title": "",
            "importance": StoryImportance(score=0, level=ImportanceLevel.LOW).to_dict(),
        }
        if not is_broad_event_class_key(event_key):
            self.data["event_to_story"][event_key] = story_id
        return story_id

    def resolve_story(self, event_key: str) -> str:
        mapped = (
            None
            if is_broad_event_class_key(event_key)
            else self.data["event_to_story"].get(event_key)
        )
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
        entities: Iterable[str] = (),
        published_at=None,
        county: str = "",
        source: str = "",
        is_custom: bool = False,
        source_class: str = "unknown",
        source_trust: int = 50,
        unified_incident_evidence: dict[str, object] | None = None,
    ) -> str:
        mapped = (
            None
            if is_broad_event_class_key(event_key)
            else self.data["event_to_story"].get(event_key)
        )
        if mapped:
            story_id = self._canonical_story_id(mapped)
            mapped_story = self.get_story(story_id)
            relationship = self._relationships.classify(
                event_key=event_key,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                stories=(mapped_story,) if mapped_story is not None else (),
            )
            relationship_won = bool(
                relationship.attaches_to_story
                and relationship.story_id
                and self._canonical_story_id(str(relationship.story_id)) == story_id
            )
            relationship_value = (
                StoryRelationshipType.FOLLOW_UP.value
                if relationship_won
                else StoryRelationshipType.SAME_EVENT.value
            )
            confidence = relationship.confidence if relationship_won else 1.0
            reason = (
                relationship.reason
                if relationship_won
                else "Exact event key already belongs to this story"
            )
            trace = (
                list(relationship.decision_trace)
                if relationship_won
                else [
                    "Relationship: same_event",
                    "Exact event-key mapping: true",
                    "No novel follow-up milestone: true",
                    "Confidence: 1.00",
                ]
            )
            self.last_decision = {
                "event_key": event_key,
                "relationship": relationship_value,
                "confidence": round(confidence, 6),
                "reason": reason,
                "decision_trace": trace,
                "matched_existing": True,
                "story_id": story_id,
            }
            self.last_decision.update(self._follow_up_candidate_fields(relationship))
            self._enrich_story(
                story_id,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                county=county,
                source=source,
                is_custom=is_custom,
                source_class=source_class,
                source_trust=source_trust,
                unified_incident_evidence=unified_incident_evidence,
            )
            self._recalculate_importance(story_id)
            story = self.data["stories"][story_id]
            self._append_resolution_history(
                story,
                {
                    "event_key": event_key,
                    "confidence": round(confidence, 6),
                    "reason": reason,
                    "decision_trace": trace,
                    "resolver_version": "2.1",
                    "matched_existing": True,
                    "relationship": relationship_value,
                }
            )
            if relationship_won:
                story.setdefault("relationship_history", []).append(
                    {
                        "event_key": event_key,
                        "relationship": relationship_value,
                        "confidence": round(confidence, 6),
                        "reason": reason,
                        "decision_trace": trace,
                        "relationship_engine_version": "1.3",
                    }
                )
            self.save()
            return story_id

        exact_title_story = self._find_exact_title_story(title)
        if exact_title_story:
            story_id = self._canonical_story_id(exact_title_story)
            self.attach_event(story_id, event_key, save=False)
            trace = [
                "Relationship: same_event",
                "Exact normalized title match: true",
                "Confidence: 1.00",
            ]
            reason = "Exact normalized title already belongs to this story"
            self._enrich_story(
                story_id,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                county=county,
                source=source,
                is_custom=is_custom,
                source_class=source_class,
                source_trust=source_trust,
                unified_incident_evidence=unified_incident_evidence,
            )
            self._recalculate_importance(story_id)
            story = self.data["stories"][story_id]
            self._append_resolution_history(
                story,
                {
                    "event_key": event_key,
                    "confidence": 1.0,
                    "reason": reason,
                    "decision_trace": trace,
                    "resolver_version": "2.2",
                    "matched_existing": True,
                    "relationship": StoryRelationshipType.SAME_EVENT.value,
                }
            )
            self.last_decision = {
                "event_key": event_key,
                "relationship": StoryRelationshipType.SAME_EVENT.value,
                "confidence": 1.0,
                "reason": reason,
                "decision_trace": trace,
                "matched_existing": True,
                "story_id": story_id,
            }
            self.last_decision.update(self._follow_up_candidate_fields(None))
            self.save()
            return story_id

        source_match = find_matching_source_story(
            source, self.iter_stories(), title=title
        )
        if source_match.matched and source_match.story_id:
            story_id = self._canonical_story_id(source_match.story_id)
            matched_story = self.get_story(story_id)
            relationship = self._relationships.classify(
                event_key=event_key,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                stories=(matched_story,) if matched_story is not None else (),
            )
            relationship_won = bool(
                relationship.attaches_to_story
                and relationship.story_id
                and self._canonical_story_id(str(relationship.story_id)) == story_id
            )
            relationship_value = (
                StoryRelationshipType.FOLLOW_UP.value
                if relationship_won
                else StoryRelationshipType.SAME_EVENT.value
            )
            confidence = (
                max(source_match.confidence, relationship.confidence)
                if relationship_won
                else source_match.confidence
            )
            reason = (
                relationship.reason
                if relationship_won
                else source_match.reason
            )
            trace = list(source_match.decision_trace)
            if relationship_won:
                trace.extend(relationship.decision_trace)

            self.attach_event(story_id, event_key, save=False)
            self._enrich_story(
                story_id,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                county=county,
                source=source,
                is_custom=is_custom,
                source_class=source_class,
                source_trust=source_trust,
                unified_incident_evidence=unified_incident_evidence,
            )
            self._recalculate_importance(story_id)
            story = self.data["stories"][story_id]
            self._append_resolution_history(
                story,
                {
                    "event_key": event_key,
                    "confidence": round(confidence, 6),
                    "reason": reason,
                    "decision_trace": trace,
                    "resolver_version": "2.4",
                    "matched_existing": True,
                    "relationship": relationship_value,
                }
            )
            if relationship_won:
                story.setdefault("relationship_history", []).append(
                    {
                        "event_key": event_key,
                        "relationship": relationship_value,
                        "confidence": round(confidence, 6),
                        "reason": reason,
                        "decision_trace": trace,
                        "relationship_engine_version": "1.3",
                    }
                )
            self.last_decision = {
                "event_key": event_key,
                "relationship": relationship_value,
                "confidence": round(confidence, 6),
                "reason": reason,
                "decision_trace": trace,
                "matched_existing": True,
                "story_id": story_id,
            }
            self.last_decision.update(self._follow_up_candidate_fields(relationship))
            self.save()
            return story_id

        incident_match = find_matching_incident_story(
            title=title,
            facts=facts,
            locations=locations,
            agencies=agencies,
            event_types=event_types,
            entities=entities,
            published_at=published_at,
            stories=self.iter_stories(),
        )
        if incident_match.matched and incident_match.story_id:
            story_id = self._canonical_story_id(incident_match.story_id)
            matched_story = self.get_story(story_id)
            relationship = self._relationships.classify(
                event_key=event_key,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                stories=(matched_story,) if matched_story is not None else (),
            )
            relationship_won = bool(
                relationship.attaches_to_story
                and relationship.story_id
                and self._canonical_story_id(str(relationship.story_id)) == story_id
            )
            relationship_value = (
                StoryRelationshipType.FOLLOW_UP.value
                if relationship_won
                else StoryRelationshipType.SAME_EVENT.value
            )
            confidence = (
                max(incident_match.confidence, relationship.confidence)
                if relationship_won
                else incident_match.confidence
            )
            reason = (
                relationship.reason
                if relationship_won
                else "High-confidence incident signature already belongs to this story"
            )
            trace = [
                "Deterministic incident identity: true",
                *incident_match.decision_trace,
            ]
            if relationship_won:
                trace.extend(relationship.decision_trace)

            self.attach_event(story_id, event_key, save=False)
            self._enrich_story(
                story_id,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                county=county,
                source=source,
                is_custom=is_custom,
                source_class=source_class,
                source_trust=source_trust,
                unified_incident_evidence=unified_incident_evidence,
            )
            self._recalculate_importance(story_id)
            story = self.data["stories"][story_id]
            self._append_resolution_history(
                story,
                {
                    "event_key": event_key,
                    "confidence": round(confidence, 6),
                    "reason": reason,
                    "decision_trace": trace,
                    "resolver_version": "2.3",
                    "matched_existing": True,
                    "relationship": relationship_value,
                }
            )
            if relationship_won:
                story.setdefault("relationship_history", []).append(
                    {
                        "event_key": event_key,
                        "relationship": relationship_value,
                        "confidence": round(confidence, 6),
                        "reason": reason,
                        "decision_trace": trace,
                        "relationship_engine_version": "1.3",
                    }
                )
            self.last_decision = {
                "event_key": event_key,
                "relationship": relationship_value,
                "confidence": round(confidence, 6),
                "reason": reason,
                "decision_trace": trace,
                "matched_existing": True,
                "story_id": story_id,
            }
            self.last_decision.update(self._follow_up_candidate_fields(relationship))
            self.save()
            return story_id

        unified_match = None
        if unified_incident_evidence:
            unified_match = find_matching_unified_incident_story(
                evidence_from_mapping(unified_incident_evidence),
                self.iter_stories(),
            )
        if unified_match is not None and unified_match.matched and unified_match.story_id:
            story_id = self._canonical_story_id(unified_match.story_id)
            matched_story = self.get_story(story_id)
            relationship = self._relationships.classify(
                event_key=event_key,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                stories=(matched_story,) if matched_story is not None else (),
            )
            relationship_won = bool(
                relationship.attaches_to_story
                and relationship.story_id
                and self._canonical_story_id(str(relationship.story_id)) == story_id
            )
            relationship_value = (
                StoryRelationshipType.FOLLOW_UP.value
                if relationship_won
                else StoryRelationshipType.SAME_EVENT.value
            )
            confidence = max(
                unified_match.confidence,
                relationship.confidence if relationship_won else 0.0,
            )
            reason = (
                relationship.reason if relationship_won else unified_match.reason
            )
            trace = list(unified_match.decision_trace)
            if relationship_won:
                trace.extend(relationship.decision_trace)
            self.attach_event(story_id, event_key, save=False)
            self._enrich_story(
                story_id,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                county=county,
                source=source,
                is_custom=is_custom,
                source_class=source_class,
                source_trust=source_trust,
                unified_incident_evidence=unified_incident_evidence,
            )
            self._recalculate_importance(story_id)
            story = self.data["stories"][story_id]
            self._append_resolution_history(
                story,
                {
                    "event_key": event_key,
                    "confidence": round(confidence, 6),
                    "reason": reason,
                    "decision_trace": trace,
                    "resolver_version": "3.0",
                    "matched_existing": True,
                    "relationship": relationship_value,
                },
            )
            self.last_decision = {
                "event_key": event_key,
                "relationship": relationship_value,
                "confidence": round(confidence, 6),
                "reason": reason,
                "decision_trace": trace,
                "matched_existing": True,
                "story_id": story_id,
                "identity_contract": "unified_incident_v1",
            }
            self.last_decision.update(self._follow_up_candidate_fields(relationship))
            self.save()
            return story_id

        if is_sparse_event_key(event_key):
            resolution = StoryResolution(
                None,
                False,
                0.0,
                "Created new story: sparse event keys require exact-title identity or a supported follow-up",
                (
                    "Sparse event-key resolver guard: true",
                    "Resolver same-event merge bypassed: true",
                ),
            )
        else:
            resolution = self._resolver.resolve(
                event_key=event_key,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                published_at=published_at,
                stories=self.iter_stories(),
            )

        # Evaluate follow-up relationships even when Resolver v2 finds a
        # high-confidence identity match. Previously the resolver won first,
        # causing the strongest follow-ups to be mislabeled as same_event.
        if is_sparse_event_key(event_key):
            advisory_relationship = self._relationships.classify(
                event_key=event_key,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                stories=self.iter_stories(),
            )
            advisory_reason_codes = tuple(
                advisory_relationship.candidate_reason_codes
                or (
                    ("would_be_enforced_follow_up",)
                    if advisory_relationship.relationship is StoryRelationshipType.FOLLOW_UP
                    else ()
                )
            )
            candidate_is_identity_anchored = (
                "identity_anchor_qualified" in advisory_reason_codes
            )
            # Sparse keys remain prohibited from attaching in this release. Preserve
            # only identity-anchored observe-only candidate metadata so production can
            # show which sparse new-story decisions may actually be follow-ups. A
            # milestone plus generic fact overlap is not enough.
            relationship = StoryRelationship(
                StoryRelationshipType.NEW_STORY,
                None,
                0.0,
                "Sparse event keys require exact-title identity before attachment",
                (
                    "Relationship: new_story",
                    "Sparse event-key relationship guard: true",
                ),
                candidate_story_id=(
                    (
                        advisory_relationship.candidate_story_id
                        or advisory_relationship.story_id
                    )
                    if candidate_is_identity_anchored
                    else None
                ),
                candidate_confidence=(
                    (
                        advisory_relationship.candidate_confidence
                        or advisory_relationship.confidence
                    )
                    if candidate_is_identity_anchored
                    else 0.0
                ),
                candidate_milestones=(
                    advisory_relationship.candidate_milestones
                    if candidate_is_identity_anchored
                    else ()
                ),
                candidate_reason_codes=(
                    advisory_reason_codes if candidate_is_identity_anchored else ()
                ),
                candidate_trace=(
                    (
                        advisory_relationship.candidate_trace
                        or advisory_relationship.decision_trace
                    )
                    if candidate_is_identity_anchored
                    else ()
                ),
            )
        else:
            relationship = self._relationships.classify(
                event_key=event_key,
                title=title,
                facts=facts,
                locations=locations,
                agencies=agencies,
                event_types=event_types,
                entities=entities,
                stories=self.iter_stories(),
            )
        relationship_won = bool(
            relationship.attaches_to_story and relationship.story_id
        )
        if relationship_won:
            story_id = self._canonical_story_id(str(relationship.story_id))
            self.attach_event(story_id, event_key, save=False)
        elif resolution.merge and resolution.story_id:
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
            entities=entities,
            county=county,
            source=source,
            is_custom=is_custom,
            source_class=source_class,
            source_trust=source_trust,
            unified_incident_evidence=unified_incident_evidence,
        )
        self._recalculate_importance(story_id)
        story = self.data["stories"][story_id]
        matched_existing = bool(resolution.merge) or relationship_won
        relationship_value = (
            StoryRelationshipType.FOLLOW_UP.value
            if relationship_won
            else (
                StoryRelationshipType.SAME_EVENT.value
                if resolution.merge
                else StoryRelationshipType.NEW_STORY.value
            )
        )
        selected_confidence = relationship.confidence if relationship_won else resolution.confidence
        selected_reason = relationship.reason if relationship_won else resolution.reason
        selected_trace = list(relationship.decision_trace if relationship_won else resolution.decision_trace)
        self.last_decision = {
            "event_key": event_key,
            "relationship": relationship_value,
            "confidence": round(selected_confidence, 6),
            "reason": selected_reason,
            "decision_trace": selected_trace,
            "matched_existing": matched_existing,
            "story_id": story_id,
        }
        self.last_decision.update(self._follow_up_candidate_fields(relationship))
        self._append_resolution_history(
            story,
            {
                "event_key": event_key,
                "confidence": round(
                    relationship.confidence if relationship_won else resolution.confidence,
                    6,
                ),
                "reason": (
                    relationship.reason if relationship_won else resolution.reason
                ),
                "decision_trace": list(
                    relationship.decision_trace if relationship_won else resolution.decision_trace
                ),
                "resolver_version": "2.1",
                "matched_existing": matched_existing,
                "relationship": (
                    relationship_value
                ),
            }
        )
        if relationship_won or not resolution.merge:
            story.setdefault("relationship_history", []).append(
                {
                    "event_key": event_key,
                    "relationship": relationship_value,
                    "confidence": round(selected_confidence, 6),
                    "reason": selected_reason,
                    "decision_trace": selected_trace,
                    "relationship_engine_version": "1.3",
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
        entities: Iterable[str] = (),
        published_at=None,
        county: str = "",
        source: str = "",
        is_custom: bool = False,
        source_class: str = "unknown",
        source_trust: int = 50,
        unified_incident_evidence: dict[str, object] | None = None,
    ) -> None:
        story = self.data["stories"][self._canonical_story_id(story_id)]

        if unified_incident_evidence:
            normalized_evidence = evidence_from_mapping(unified_incident_evidence).to_dict()
            evidence_rows = story.setdefault("unified_incident_evidence", [])
            evidence_key = json.dumps(normalized_evidence, sort_keys=True, separators=(",", ":"))
            existing_keys = {
                json.dumps(row, sort_keys=True, separators=(",", ":"))
                for row in evidence_rows if isinstance(row, dict)
            }
            if evidence_key not in existing_keys:
                evidence_rows.append(normalized_evidence)
                if len(evidence_rows) > self.UNIFIED_INCIDENT_EVIDENCE_LIMIT:
                    story["unified_incident_evidence"], _ = (
                        self._compact_unified_incident_evidence_entries(evidence_rows)
                    )

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
            ("entities", entities),
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

        locality = classify_local_relevance(
            locations=story.get("locations", ()),
            county=county,
            text=" ".join([title, *story.get("facts", ()), *story.get("entities", ())]),
        )
        current = story.get("local_relevance", {})
        if locality.score >= int(current.get("score", 0)):
            story["local_relevance"] = {
                "scope": locality.scope, "score": locality.score,
                "counties": list(locality.counties), "places": list(locality.places),
            }

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
        proximity = classify_editorial_proximity(story)
        story["editorial_proximity"] = proximity.to_dict()
        ranking = calculate_editorial_score(
            importance.score,
            proximity.score,
            source_trust=story_source_trust(story),
            published_at=latest_story_timestamp(story),
        )
        story["editorial_score"] = ranking.score
        story["score_breakdown"] = ranking.to_dict()
        # Retain the previous field so existing observability and integrations
        # remain backward compatible during shadow evaluation.
        story["editorial_priority"] = ranking.score
        lifecycle = classify_story_lifecycle(story)
        previous_state = str((story.get("lifecycle") or {}).get("state") or story.get("status") or "")
        story["lifecycle"] = lifecycle.to_dict()
        story["status"] = lifecycle.state.value
        if previous_state and previous_state != lifecycle.state.value:
            story.setdefault("lifecycle_history", []).append(
                {
                    "from": previous_state,
                    "to": lifecycle.state.value,
                    "reason": lifecycle.reason,
                    "last_updated": lifecycle.last_updated,
                }
            )
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

        if not is_broad_event_class_key(event_key):
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
            if not is_broad_event_class_key(event_key):
                self.data["event_to_story"][event_key] = primary_story

        for field in (
            "titles",
            "title_tokens",
            "fact_tokens",
            "facts",
            "locations",
            "agencies",
            "event_types",
            "entities",
        ):
            primary[field] = sorted(set(primary[field]) | set(secondary[field]))

        primary["resolution_history"], _ = self._compact_resolution_entries(
            [
                *primary.get("resolution_history", ()),
                *secondary.get("resolution_history", ()),
            ]
        )
        primary.setdefault("relationship_history", []).extend(secondary.get("relationship_history", []))
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
                -int(story.get("editorial_score", story.get("editorial_priority", 0)) or 0),
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

    def get_registry_health(self) -> dict[str, Any]:
        repair = dict(self.data.get("registry_repair") or {})
        last_run = dict(repair.get("last_run") or {})
        last_run["quarantined_story_records_retained"] = len(
            self.data.get("quarantined_stories") or {}
        )
        last_run["active_story_count"] = len(self.data.get("stories") or {})
        return last_run

    def iter_stories(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            dict(self.data["stories"][story_id])
            for story_id in sorted(self.data["stories"])
        )
