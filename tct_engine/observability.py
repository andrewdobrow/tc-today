"""Observability reporting for the TCT editorial engine and activation layer.

This module owns the diagnostics schema and version labels so production
orchestration does not need to know the engine's internal data model.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .story_relationship import detect_advisory_follow_up_evidence

ENGINE_NAME = "tct-editorial-engine"
ENGINE_VERSION = "1.11.7.0"
ENGINE_RELEASE = "trusted-source-and-county-membership-recovery"
OBSERVABILITY_SCHEMA_VERSION = 13
RESOLVER_VERSION = "2.4"
RELATIONSHIP_ENGINE_VERSION = "1.4"


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


_RETROSPECTIVE_STOP_WORDS = {
    "the", "and", "for", "with", "from", "after", "before", "into",
    "county", "news", "update", "says", "said", "earlier", "reported",
    "florida", "local", "treasure", "coast",
}
_RETROSPECTIVE_SOCIAL_MARKERS = (
    "facebook.com", "instagram.com", "x.com", "twitter.com", "tiktok.com",
    "reddit.com", "youtube.com", "youtu.be", "threads.net", "nextdoor.com",
)
_RETROSPECTIVE_LOW_VALUE_TITLE_PATTERNS = (
    r"^expert (?:breaks down|explains)\b",
    r"^what to know\b",
    r"^watch(?: below|:)\b",
    r"^video:\s*",
    r"^photos?:\s*",
    r"^opinion:\s*",
    r"^analysis:\s*",
    r"^live updates?\b",
    r"^a happy ending\b",
)
_RETROSPECTIVE_HIGH_CONFIDENCE = 0.80


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _retrospective_tokens(value: object) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", _normalized_text(value))
        if len(token) >= 3 and token not in _RETROSPECTIVE_STOP_WORDS
    }


def _retrospective_overlap(left: object, right: object) -> float:
    left_tokens = _retrospective_tokens(left)
    right_tokens = _retrospective_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))


def _timeline_datetime(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timeline_entry_payload(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "article_id": str(entry.get("article_id") or ""),
        "event_key": str(entry.get("event_key") or ""),
        "published_at": str(entry.get("published_at") or ""),
        "title": str(entry.get("title") or ""),
        "source": str(entry.get("source") or ""),
        "url": str(entry.get("url") or ""),
    }


def _retrospective_exclusion_reasons(entry: Mapping[str, Any]) -> tuple[str, ...]:
    title = _normalized_text(entry.get("title"))
    source_blob = " ".join((
        title,
        _normalized_text(entry.get("source")),
        _normalized_text(entry.get("url")),
    ))
    reasons: list[str] = []
    if any(marker in source_blob for marker in _RETROSPECTIVE_SOCIAL_MARKERS):
        reasons.append("social_source")
    if len(_retrospective_tokens(title)) < 5:
        reasons.append("insufficient_title_detail")
    if any(re.search(pattern, title) for pattern in _RETROSPECTIVE_LOW_VALUE_TITLE_PATTERNS):
        reasons.append("low_value_title")
    return tuple(reasons)


def _build_retrospective_follow_up_observability(
    stories: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Inspect persisted timelines for milestone transitions without changing them.

    Timeline order and title evidence are treated conservatively.  Ambiguous
    transitions are still reported for review, but blocking conflicts prevent them
    from becoming activation evidence.
    """

    candidates: list[dict[str, Any]] = []
    milestone_counts: Counter[str] = Counter()
    blocking_conflicts: Counter[str] = Counter()
    exclusion_reasons: Counter[str] = Counter()
    excluded_entry_count = 0
    transitions_examined = 0
    timeline_entries_examined = 0
    stories_with_timelines = 0

    for story in stories:
        raw_timeline = story.get("timeline") or []
        timeline = [dict(entry) for entry in raw_timeline if isinstance(entry, Mapping)]
        if len(timeline) < 2:
            continue
        timeline.sort(key=lambda entry: (
            _timeline_datetime(entry.get("published_at")),
            str(entry.get("article_id") or ""),
        ))
        stories_with_timelines += 1
        known_milestones: set[str] = set()
        previous_eligible: dict[str, Any] | None = None

        for entry in timeline:
            timeline_entries_examined += 1
            excluded = _retrospective_exclusion_reasons(entry)
            if excluded:
                excluded_entry_count += 1
                exclusion_reasons.update(excluded)
                continue

            evidence = detect_advisory_follow_up_evidence(
                entry.get("title"), entry.get("event_key")
            )
            milestones = set(evidence)
            if previous_eligible is not None:
                transitions_examined += 1
                novel_milestones = milestones - known_milestones
                if novel_milestones:
                    prior_title_overlap = _retrospective_overlap(
                        previous_eligible.get("title"), entry.get("title")
                    )
                    canonical_title_overlap = _retrospective_overlap(
                        story.get("canonical_title"), entry.get("title")
                    )
                    same_timestamp = (
                        _timeline_datetime(previous_eligible.get("published_at"))
                        == _timeline_datetime(entry.get("published_at"))
                    )
                    conflicts: list[str] = []
                    if same_timestamp:
                        conflicts.append("same_timestamp_order_uncertain")
                    if max(prior_title_overlap, canonical_title_overlap) < 0.22:
                        conflicts.append("weak_title_continuity")
                    terminal = novel_milestones & {
                        "death", "resolution", "opening", "closure"
                    }
                    if len(terminal) > 1:
                        conflicts.append("multiple_terminal_milestones")

                    confidence = (
                        0.58
                        + 0.16 * min(1.0, prior_title_overlap)
                        + 0.14 * min(1.0, canonical_title_overlap)
                        + 0.08 * float(not same_timestamp)
                        + 0.08 * float(len(novel_milestones) == 1)
                        - 0.16 * float("weak_title_continuity" in conflicts)
                    )
                    confidence = max(0.0, min(1.0, confidence))
                    reason_codes = [
                        "retrospective_timeline_transition",
                        "novel_milestone",
                        "persistent_story_identity",
                    ]
                    if prior_title_overlap >= 0.35:
                        reason_codes.append("prior_title_continuity")
                    if canonical_title_overlap >= 0.35:
                        reason_codes.append("canonical_title_continuity")
                    if not same_timestamp:
                        reason_codes.append("chronology_supported")
                    activation_eligible = (
                        confidence >= _RETROSPECTIVE_HIGH_CONFIDENCE
                        and not conflicts
                    )
                    if activation_eligible:
                        reason_codes.append("activation_evidence_candidate")

                    milestone_counts.update(novel_milestones)
                    blocking_conflicts.update(conflicts)
                    candidates.append({
                        "story_id": str(story.get("story_id") or ""),
                        "story_title": _story_title(story),
                        "milestones": sorted(novel_milestones),
                        "matched_phrases": {
                            milestone: list(evidence.get(milestone, ()))
                            for milestone in sorted(novel_milestones)
                        },
                        "confidence": round(confidence, 6),
                        "activation_eligible": activation_eligible,
                        "blocking_conflicts": conflicts,
                        "reason_codes": reason_codes,
                        "prior_title_overlap": round(prior_title_overlap, 6),
                        "canonical_title_overlap": round(canonical_title_overlap, 6),
                        "prior_article": _timeline_entry_payload(previous_eligible),
                        "newer_article": _timeline_entry_payload(entry),
                        "candidate_trace": [
                            "Follow-up candidate mode: retrospective_observe_only",
                            f"Story: {story.get('story_id') or ''}",
                            f"Novel milestones: {', '.join(sorted(novel_milestones))}",
                            f"Prior title overlap: {prior_title_overlap:.2f}",
                            f"Canonical title overlap: {canonical_title_overlap:.2f}",
                            f"Same timestamp: {same_timestamp}",
                            f"Blocking conflicts: {', '.join(conflicts) or 'none'}",
                            f"Candidate confidence: {confidence:.2f}",
                            f"Activation eligible: {activation_eligible}",
                        ],
                    })

            known_milestones.update(milestones)
            previous_eligible = entry

    candidates.sort(key=lambda candidate: (
        not bool(candidate.get("activation_eligible")),
        -float(candidate.get("confidence") or 0.0),
        str(candidate.get("story_id") or ""),
        str((candidate.get("newer_article") or {}).get("published_at") or ""),
    ))
    high_confidence_count = sum(
        1 for candidate in candidates
        if float(candidate.get("confidence") or 0.0) >= _RETROSPECTIVE_HIGH_CONFIDENCE
    )
    activation_eligible_count = sum(
        1 for candidate in candidates if candidate.get("activation_eligible")
    )
    return {
        "mode": "retrospective_observe_only",
        "publication_behavior_changed": False,
        "stories_with_timelines": stories_with_timelines,
        "timeline_entries_examined": timeline_entries_examined,
        "transitions_examined": transitions_examined,
        "candidate_count": len(candidates),
        "high_confidence_candidate_count": high_confidence_count,
        "activation_eligible_candidate_count": activation_eligible_count,
        "milestones": dict(sorted(milestone_counts.items())),
        "blocking_conflicts": dict(sorted(blocking_conflicts.items())),
        "excluded_entry_count": excluded_entry_count,
        "exclusion_reasons": dict(sorted(exclusion_reasons.items())),
        "examples": candidates[:50],
        "review_ready": bool(candidates),
        "enforcement_ready": False,
        "enforcement_readiness_reason": (
            "Retrospective candidates are evidence for manual review only. "
            "No relationship, grouping, ranking or publication behavior changes."
        ),
    }


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

    retrospective_follow_up = _build_retrospective_follow_up_observability(stories)

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
            "retrospective_candidate_count": retrospective_follow_up["candidate_count"],
            "retrospective_high_confidence_candidate_count": retrospective_follow_up[
                "high_confidence_candidate_count"
            ],
            "retrospective_activation_eligible_candidate_count": retrospective_follow_up[
                "activation_eligible_candidate_count"
            ],
            "retrospective": retrospective_follow_up,
            "enforcement_ready": False,
            "enforcement_readiness_reason": (
                "Current-run and retrospective candidate evidence must be manually reviewed "
                "across production runs before broader follow-up grouping is activated."
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
