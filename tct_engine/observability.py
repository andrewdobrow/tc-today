"""Observability reporting for the TCT editorial engine and activation layer.

This module owns the diagnostics schema and version labels so production
orchestration does not need to know the engine's internal data model.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ENGINE_NAME = "tct-editorial-engine"
ENGINE_VERSION = "1.11.5.3"
ENGINE_RELEASE = "compact-auto-sized-product-media"
OBSERVABILITY_SCHEMA_VERSION = 12
RESOLVER_VERSION = "2.4"
RELATIONSHIP_ENGINE_VERSION = "1.3"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _story_title(story: Mapping[str, Any]) -> str:
    canonical = str(story.get("canonical_title") or "").strip()
    if canonical:
        return canonical
    titles = story.get("titles") or []
    return str(titles[-1]).strip() if titles else ""


def build_editorial_observability(
    engine: Any,
    audit_rows: Iterable[Mapping[str, Any]],
    *,
    registry_path: str = "data/editorial_story_registry.json",
    mode: str = "shadow",
    activation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, JSON-safe diagnostics report.

    The function intentionally uses only the engine's public story query plus
    persisted story dictionaries. Missing future fields degrade to safe defaults.
    """

    rows = [dict(row) for row in audit_rows]
    stories = list(engine.get_top_stories(limit=100000))
    registry_health = (
        dict(engine.get_registry_health())
        if hasattr(engine, "get_registry_health")
        else {}
    )

    route_counts: Counter[str] = Counter()
    eligibility_counts: Counter[str] = Counter()
    source_class_counts: Counter[str] = Counter()
    rejected_examples: list[dict[str, Any]] = []
    relationship_counts: Counter[str] = Counter()
    decision_trace_examples: list[dict[str, Any]] = []
    relationship_examples: list[dict[str, Any]] = []
    follow_up_candidate_count = 0
    high_confidence_follow_up_candidate_count = 0
    follow_up_candidate_milestones: Counter[str] = Counter()
    follow_up_candidate_current_relationships: Counter[str] = Counter()
    follow_up_candidate_reason_codes: Counter[str] = Counter()
    follow_up_candidate_examples: list[dict[str, Any]] = []

    has_current_relationships = any(bool(row.get("relationship")) for row in rows)

    for row in rows:
        route_counts[str(row.get("route") or "unknown")] += 1
        eligibility_counts[str(row.get("eligibility_status") or "publishable")] += 1
        source_class_counts[str(row.get("source_class") or "unknown")] += 1
        relationship = str(row.get("relationship") or "")
        if relationship:
            relationship_counts[relationship] += 1
            if len(relationship_examples) < 20:
                relationship_examples.append({
                    "story_id": row.get("story_id", ""),
                    "title": row.get("headline", ""),
                    "event_key": row.get("event_key", ""),
                    "relationship": relationship,
                    "confidence": row.get("relationship_confidence", 0),
                    "reason": row.get("relationship_reason", ""),
                    "decision_trace": list(row.get("decision_trace") or []),
                })
            trace = list(row.get("decision_trace") or [])
            if trace and len(decision_trace_examples) < 20:
                decision_trace_examples.append({
                    "story_id": row.get("story_id", ""),
                    "title": row.get("headline", ""),
                    "event_key": row.get("event_key", ""),
                    "relationship": relationship,
                    "confidence": row.get("relationship_confidence", 0),
                    "matched_existing": relationship in {"same_event", "follow_up"},
                    "reason": row.get("relationship_reason", ""),
                    "decision_trace": trace,
                })

        candidate_story_id = str(row.get("follow_up_candidate_story_id") or "").strip()
        candidate_confidence = float(row.get("follow_up_candidate_confidence") or 0.0)
        candidate_milestones = [
            str(value).strip()
            for value in (row.get("follow_up_candidate_milestones") or [])
            if str(value).strip()
        ]
        candidate_reason_codes = [
            str(value).strip()
            for value in (row.get("follow_up_candidate_reason_codes") or [])
            if str(value).strip()
        ]
        if candidate_story_id:
            follow_up_candidate_count += 1
            if candidate_confidence >= 0.75:
                high_confidence_follow_up_candidate_count += 1
            follow_up_candidate_current_relationships[relationship or "unknown"] += 1
            follow_up_candidate_milestones.update(candidate_milestones)
            follow_up_candidate_reason_codes.update(candidate_reason_codes)
            if len(follow_up_candidate_examples) < 25:
                follow_up_candidate_examples.append({
                    "headline": row.get("headline", ""),
                    "event_key": row.get("event_key", ""),
                    "current_story_id": row.get("story_id", ""),
                    "current_relationship": relationship or "unknown",
                    "candidate_story_id": candidate_story_id,
                    "candidate_confidence": round(candidate_confidence, 6),
                    "candidate_milestones": candidate_milestones,
                    "candidate_reason_codes": candidate_reason_codes,
                    "candidate_trace": list(row.get("follow_up_candidate_trace") or []),
                })

        if not bool(row.get("eligible", True)) and len(rejected_examples) < 20:
            rejected_examples.append(
                {
                    "headline": row.get("headline", ""),
                    "source_url": row.get("source_url", ""),
                    "status": row.get("eligibility_status", "non_news"),
                    "reasons": list(row.get("eligibility_reasons") or []),
                    "source_class": row.get("source_class", "unknown"),
                }
            )

    importance_levels: Counter[str] = Counter()
    locality_scopes: Counter[str] = Counter()
    proximity_scopes: Counter[str] = Counter()
    scores: list[int] = []
    priority_scores: list[int] = []
    locality_scores: list[int] = []
    lifecycle_counts: Counter[str] = Counter()

    for story in stories:
        importance = story.get("importance") or {}
        level = str(importance.get("level") or "low").lower()
        if level not in {"breaking", "high", "normal", "low", "archived"}:
            level = "low"
        importance_levels[level] += 1
        scores.append(_safe_int(importance.get("score")))

        locality = story.get("local_relevance") or {}
        scope = str(locality.get("scope") or "unknown")
        locality_scopes[scope] += 1
        locality_scores.append(_safe_int(locality.get("score"), 35))
        proximity = story.get("editorial_proximity") or {}
        proximity_scopes[str(proximity.get("scope") or "unknown")] += 1
        priority_scores.append(_safe_int(story.get("editorial_score", story.get("editorial_priority"))))
        lifecycle = story.get("lifecycle") or {}
        lifecycle_counts[str(lifecycle.get("state") or story.get("status") or "unknown")] += 1

        for relation in story.get("relationship_history") or []:
            relationship = str(relation.get("relationship") or "unknown")
            if not has_current_relationships:
                relationship_counts[relationship] += 1
            if len(relationship_examples) < 20:
                relationship_examples.append(
                    {
                        "story_id": story.get("story_id", ""),
                        "title": _story_title(story),
                        "event_key": relation.get("event_key", ""),
                        "relationship": relationship,
                        "confidence": relation.get("confidence", 0),
                        "reason": relation.get("reason", ""),
                        "decision_trace": list(relation.get("decision_trace") or []),
                    }
                )

        for resolution in story.get("resolution_history") or []:
            relationship = str(resolution.get("relationship") or "unknown")
            # Resolution records include SAME_EVENT and NEW_STORY decisions that may
            # not have a corresponding relationship_history record.
            if not has_current_relationships and relationship in {"same_event", "new_story"}:
                relationship_counts[relationship] += 1
            trace = list(resolution.get("decision_trace") or [])
            if trace and len(decision_trace_examples) < 20:
                decision_trace_examples.append(
                    {
                        "story_id": story.get("story_id", ""),
                        "title": _story_title(story),
                        "event_key": resolution.get("event_key", ""),
                        "relationship": relationship,
                        "confidence": resolution.get("confidence", 0),
                        "matched_existing": bool(resolution.get("matched_existing", False)),
                        "reason": resolution.get("reason", ""),
                        "decision_trace": trace,
                    }
                )

    top_stories: list[dict[str, Any]] = []
    for story in stories[:20]:
        importance = story.get("importance") or {}
        locality = story.get("local_relevance") or {}
        top_stories.append(
            {
                "story_id": story.get("story_id", ""),
                "title": _story_title(story),
                "score": _safe_int(importance.get("score")),
                "editorial_priority": _safe_int(story.get("editorial_priority")),
                "editorial_score": _safe_int(story.get("editorial_score", story.get("editorial_priority"))),
                "score_breakdown": dict(story.get("score_breakdown") or {}),
                "level": importance.get("level", "low"),
                "importance_reasons": list(importance.get("reasons") or []),
                "local_relevance": {
                    "scope": locality.get("scope", "unknown"),
                    "score": _safe_int(locality.get("score"), 35),
                    "counties": list(locality.get("counties") or []),
                    "places": list(locality.get("places") or []),
                },
                "editorial_proximity": dict(story.get("editorial_proximity") or {}),
                "event_count": len(story.get("events") or []),
                "timeline_entries": len(story.get("timeline") or []),
                "relationship_decisions": len(story.get("relationship_history") or []),
                "canonical_source_candidates": len(story.get("title_candidates") or []),
                "lifecycle": dict(story.get("lifecycle") or {}),
            }
        )

    return {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "engine": {
            "name": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "release": ENGINE_RELEASE,
            "resolver_version": RESOLVER_VERSION,
            "relationship_engine_version": RELATIONSHIP_ENGINE_VERSION,
        },
        "generated_at": _utc_now(),
        "mode": mode,
        "publication_behavior_changed": bool((activation or {}).get("publication_behavior_changed", False)),
        "activation": dict(activation or {}),
        "registry_path": registry_path,
        "audit": {
            "candidates_processed": len(rows),
            "routes": dict(sorted(route_counts.items())),
            "eligibility": dict(sorted(eligibility_counts.items())),
            "source_classes": dict(sorted(source_class_counts.items())),
            "rejected_count": sum(1 for row in rows if not bool(row.get("eligible", True))),
            "rejected_examples": rejected_examples,
        },
        "relationships": {
            "counts": dict(sorted(relationship_counts.items())),
            "examples": relationship_examples,
            "decision_trace_examples": decision_trace_examples,
        },
        "follow_up_detection": {
            "mode": "observe_only",
            "publication_behavior_changed": False,
            "candidate_count": follow_up_candidate_count,
            "high_confidence_candidate_count": high_confidence_follow_up_candidate_count,
            "current_relationships": dict(
                sorted(follow_up_candidate_current_relationships.items())
            ),
            "milestones": dict(sorted(follow_up_candidate_milestones.items())),
            "reason_codes": dict(sorted(follow_up_candidate_reason_codes.items())),
            "examples": follow_up_candidate_examples,
            "enforcement_ready": False,
            "enforcement_readiness_reason": (
                "Observe-only candidate evidence must be reviewed across production runs "
                "before broader follow-up grouping is activated."
            ),
        },
        "local_relevance": {
            "scopes": dict(sorted(locality_scopes.items())),
            "average_score": round(sum(locality_scores) / len(locality_scores), 2)
            if locality_scores
            else 0.0,
        },
        "editorial_proximity": {
            "scopes": dict(sorted(proximity_scopes.items())),
            "average_priority": round(sum(priority_scores) / len(priority_scores), 2)
            if priority_scores else 0.0,
        },
        "story_lifecycle": {
            "counts": dict(sorted(lifecycle_counts.items())),
        },
        "registry_health": registry_health,
        "stories": {
            "total": len(stories),
            "importance_levels": {
                key: importance_levels.get(key, 0)
                for key in ("breaking", "high", "normal", "low", "archived")
            },
            "average_importance": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "top": top_stories,
        },
        "status": "healthy",
    }


def write_editorial_observability(
    engine: Any,
    audit_rows: Iterable[Mapping[str, Any]],
    output_path: str | Path,
    *,
    registry_path: str = "data/editorial_story_registry.json",
    mode: str = "shadow",
    activation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Atomically write the diagnostics report and return its payload."""

    report = build_editorial_observability(
        engine,
        audit_rows,
        registry_path=registry_path,
        mode=mode,
        activation=activation,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return report
