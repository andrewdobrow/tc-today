"""Bounded semantic final gate for public-permalink identity.

Deterministic identity remains the first publication authority.  This module is a
last-mile backstop for the narrow case where a fully generated article strongly
resembles a recent canonical story but exact source/story/incident keys did not
survive source extraction.  It performs two separate jobs:

1. retrieve only a small, recent, high-similarity candidate set; and
2. ask a model to distinguish same-event duplication from a material update.

The model never searches the archive and never writes files.  Its output is parsed,
validated, and converted into one of four deterministic actions by the caller.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping, Sequence

SEMANTIC_PUBLICATION_GATE_VERSION = "1.0"
SEMANTIC_PUBLICATION_GATE_PROMPT_VERSION = "1.0"
DEFAULT_RECENT_WINDOW_DAYS = 7
DEFAULT_MAX_CANDIDATES = 4
DEFAULT_MIN_CONFIDENCE = 0.82

ACTION_DUPLICATE = "duplicate_use_existing_canonical"
ACTION_UPDATE = "update_existing_canonical"
ACTION_NEW = "new_story"
ACTION_HOLD = "hold"
ALLOWED_ACTIONS = frozenset({ACTION_DUPLICATE, ACTION_UPDATE, ACTION_NEW, ACTION_HOLD})

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "by",
    "for", "from", "has", "have", "in", "into", "is", "it", "its", "of",
    "on", "or", "that", "the", "this", "to", "was", "were", "will", "with",
    "after", "before", "over", "under", "near", "about", "following",
}

_TOKEN_CANONICAL = {
    "died": "death", "dies": "death", "dead": "death", "fatal": "death",
    "killed": "death", "kills": "death",
    "crashes": "crash", "crashed": "crash", "collision": "crash",
    "collisions": "crash", "wreck": "crash", "wrecks": "crash",
    "woman": "woman", "women": "woman", "man": "man", "men": "man",
    "charged": "charge", "charges": "charge", "charging": "charge",
    "arrested": "arrest", "arrests": "arrest",
    "approves": "approve", "approved": "approve", "approval": "approve",
    "votes": "vote", "voted": "vote", "voting": "vote",
}


def _clean_text(value: object) -> str:
    text = str(value or "").casefold()
    text = text.replace("st.", "st")
    text = re.sub(r"(?<=\d)[–—-](?=\d)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def headline_tokens(value: object) -> tuple[str, ...]:
    """Return stable, order-independent headline tokens.

    Ages and place-name words are intentionally retained.  Those are unusually useful
    in local-news duplicate retrieval, while generic function words are discarded.
    """
    tokens: list[str] = []
    for token in _clean_text(value).split():
        if token in _STOP_WORDS:
            continue
        token = _TOKEN_CANONICAL.get(token, token)
        if len(token) < 2 and not token.isdigit():
            continue
        tokens.append(token)
    return tuple(tokens)


def normalized_headline(value: object) -> str:
    return " ".join(headline_tokens(value))


def headline_similarity(left: object, right: object) -> dict[str, float]:
    """Measure order-insensitive similarity without treating it as identity proof."""
    left_tokens = headline_tokens(left)
    right_tokens = headline_tokens(right)
    left_set, right_set = set(left_tokens), set(right_tokens)
    if not left_set or not right_set:
        return {
            "score": 0.0,
            "overlap": 0.0,
            "jaccard": 0.0,
            "sorted_sequence": 0.0,
            "ordered_sequence": 0.0,
            "shared_token_count": 0.0,
        }
    shared = left_set & right_set
    overlap = len(shared) / min(len(left_set), len(right_set))
    jaccard = len(shared) / len(left_set | right_set)
    sorted_sequence = SequenceMatcher(
        None, " ".join(sorted(left_set)), " ".join(sorted(right_set))
    ).ratio()
    ordered_sequence = SequenceMatcher(
        None, " ".join(left_tokens), " ".join(right_tokens)
    ).ratio()
    score = max(
        0.50 * overlap + 0.30 * jaccard + 0.20 * sorted_sequence,
        0.88 * ordered_sequence,
    )
    return {
        "score": round(min(1.0, score), 4),
        "overlap": round(overlap, 4),
        "jaccard": round(jaccard, 4),
        "sorted_sequence": round(sorted_sequence, 4),
        "ordered_sequence": round(ordered_sequence, 4),
        "shared_token_count": float(len(shared)),
    }


def _string_set(article: Mapping[str, Any], key: str) -> set[str]:
    values = article.get(key) or ()
    if isinstance(values, str):
        values = (values,)
    return {str(value).strip().casefold() for value in values if str(value).strip()}


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        dt = None
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(text)
        except Exception:
            pass
        if dt is None:
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception:
                try:
                    dt = datetime.strptime(text[:10], "%Y-%m-%d")
                except Exception:
                    return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _article_datetime(article: Mapping[str, Any]) -> datetime | None:
    for key in (
        "published_at", "first_published", "published", "source_published",
        "date", "lastmod",
    ):
        dt = _parse_datetime(article.get(key))
        if dt is not None:
            return dt
    return None


def _shared_feature_evidence(
    incoming: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    shared_locality = _string_set(incoming, "locality") & _string_set(candidate, "locality")
    shared_families = _string_set(incoming, "event_families") & _string_set(candidate, "event_families")
    shared_people = _string_set(incoming, "people") & _string_set(candidate, "people")
    shared_precise = _string_set(incoming, "precise_locations") & _string_set(candidate, "precise_locations")
    shared_agencies = _string_set(incoming, "agencies") & _string_set(candidate, "agencies")
    left_anchor = str(incoming.get("incident_anchor") or "").strip().casefold()
    right_anchor = str(candidate.get("incident_anchor") or "").strip().casefold()
    left_known = str(incoming.get("known_event_key") or "").strip().casefold()
    right_known = str(candidate.get("known_event_key") or "").strip().casefold()
    exact_anchor = bool(left_anchor and left_anchor == right_anchor)
    exact_known = bool(left_known and left_known == right_known)
    anchor_conflict = bool(left_anchor and right_anchor and left_anchor != right_anchor)
    known_conflict = bool(left_known and right_known and left_known != right_known)
    return {
        "shared_locality": sorted(shared_locality),
        "shared_event_families": sorted(shared_families),
        "shared_people": sorted(shared_people),
        "shared_precise_locations": sorted(shared_precise),
        "shared_agencies": sorted(shared_agencies),
        "exact_incident_anchor": exact_anchor,
        "exact_known_event_key": exact_known,
        "incident_anchor_conflict": anchor_conflict,
        "known_event_key_conflict": known_conflict,
    }


def candidate_evidence(
    incoming: Mapping[str, Any], candidate: Mapping[str, Any], *, window_days: int
) -> dict[str, Any]:
    incoming_headline = incoming.get("headline") or incoming.get("title") or ""
    candidate_headline = candidate.get("headline") or candidate.get("title") or ""
    final_similarity = headline_similarity(incoming_headline, candidate_headline)
    incoming_source_headline = str(incoming.get("source_headline") or "").strip()
    candidate_source_headline = str(candidate.get("source_headline") or "").strip()
    source_similarity = headline_similarity(
        incoming_source_headline, candidate_source_headline
    )
    source_generic = bool(
        re.search(r"\bweek of\b|\bnews roundup\b|\blocal briefs?\b", incoming_source_headline, re.I)
        or re.search(r"\bweek of\b|\bnews roundup\b|\blocal briefs?\b", candidate_source_headline, re.I)
        or len(headline_tokens(incoming_source_headline)) < 5
        or len(headline_tokens(candidate_source_headline)) < 5
    )
    if source_generic:
        source_similarity = {**source_similarity, "score": 0.0}
    similarity = final_similarity if final_similarity["score"] >= source_similarity["score"] else source_similarity
    features = _shared_feature_evidence(incoming, candidate)
    incoming_dt = _article_datetime(incoming)
    candidate_dt = _article_datetime(candidate)
    day_gap = None
    if incoming_dt is not None and candidate_dt is not None:
        day_gap = abs((incoming_dt.date() - candidate_dt.date()).days)
    time_safe = day_gap is None or day_gap <= max(1, int(window_days))

    score = float(similarity["score"])
    if features["shared_locality"]:
        score += 0.06
    if features["shared_event_families"]:
        score += 0.06
    if features["shared_people"]:
        score += 0.10
    if features["shared_precise_locations"]:
        score += 0.10
    if features["shared_agencies"]:
        score += 0.03
    if features["exact_incident_anchor"] or features["exact_known_event_key"]:
        score += 0.15
    score = min(1.0, score)

    shared_count = int(similarity["shared_token_count"])
    contextual_anchor = bool(
        features["shared_people"]
        or features["shared_precise_locations"]
        or features["exact_incident_anchor"]
        or features["exact_known_event_key"]
    )
    context_compatible = bool(
        features["shared_locality"] and features["shared_event_families"]
    )
    conflict = bool(
        features["incident_anchor_conflict"] or features["known_event_key_conflict"]
    )

    eligible = bool(
        time_safe
        and not conflict
        and shared_count >= 4
        and (
            similarity["score"] >= 0.64
            or (similarity["score"] >= 0.50 and context_compatible and contextual_anchor)
            or (similarity["score"] >= 0.56 and context_compatible and shared_count >= 6)
        )
    )
    reasons: list[str] = []
    if similarity["score"] >= 0.64:
        reasons.append("strong_fuzzy_headline")
    elif similarity["score"] >= 0.50:
        reasons.append("moderate_fuzzy_headline")
    if context_compatible:
        reasons.append("shared_locality_and_event_family")
    if contextual_anchor:
        reasons.append("shared_incident_anchor")
    if day_gap is not None:
        reasons.append(f"publication_gap_{day_gap}_days")
    if conflict:
        reasons.append("structured_identity_conflict")
    if not time_safe:
        reasons.append("outside_recent_window")

    return {
        "eligible": eligible,
        "retrieval_score": round(score, 4),
        "headline_similarity": similarity,
        "final_headline_similarity": final_similarity,
        "source_headline_similarity": source_similarity,
        "day_gap": day_gap,
        "time_safe": time_safe,
        "reasons": reasons,
        **features,
    }


def retrieve_recent_candidates(
    incoming: Mapping[str, Any],
    archive_articles: Iterable[Mapping[str, Any]],
    *,
    window_days: int = DEFAULT_RECENT_WINDOW_DAYS,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> list[dict[str, Any]]:
    """Return a bounded candidate set; fuzzy similarity never makes the decision."""
    candidates: list[dict[str, Any]] = []
    incoming_slug = str(incoming.get("slug") or "").strip()
    for candidate in archive_articles:
        if not isinstance(candidate, Mapping):
            continue
        slug = str(candidate.get("slug") or "").strip()
        if not slug or slug == incoming_slug:
            continue
        evidence = candidate_evidence(incoming, candidate, window_days=window_days)
        if not evidence.get("eligible"):
            continue
        candidates.append({
            "slug": slug,
            "headline": str(candidate.get("headline") or candidate.get("title") or ""),
            "article": dict(candidate),
            "evidence": evidence,
        })
    candidates.sort(
        key=lambda row: (
            float(row["evidence"].get("retrieval_score") or 0.0),
            -int(row["evidence"].get("day_gap") or 0),
            row.get("slug", ""),
        ),
        reverse=True,
    )
    return candidates[: max(1, int(max_candidates))]


def _compact_article(article: Mapping[str, Any]) -> dict[str, Any]:
    body = str(article.get("body") or article.get("article_text") or "").strip()
    body = re.sub(r"\s+", " ", body)
    return {
        "slug": str(article.get("slug") or ""),
        "headline": str(article.get("headline") or article.get("title") or ""),
        "source_headline": str(article.get("source_headline") or ""),
        "published_at": str(
            article.get("published_at")
            or article.get("first_published")
            or article.get("published")
            or article.get("date")
            or ""
        ),
        "source_url": str(article.get("source_url") or ""),
        "lead": str(article.get("lead") or article.get("teaser") or "")[:800],
        "body": body[:4200],
        "locality": sorted(_string_set(article, "locality")),
        "event_families": sorted(_string_set(article, "event_families")),
        "people": sorted(_string_set(article, "people")),
        "precise_locations": sorted(_string_set(article, "precise_locations")),
        "agencies": sorted(_string_set(article, "agencies")),
        "incident_anchor": str(article.get("incident_anchor") or ""),
        "known_event_key": str(article.get("known_event_key") or ""),
    }


def decision_cache_key(
    incoming: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], *, model: str
) -> str:
    payload = {
        "gate_version": SEMANTIC_PUBLICATION_GATE_VERSION,
        "prompt_version": SEMANTIC_PUBLICATION_GATE_PROMPT_VERSION,
        "model": str(model or ""),
        "incoming": _compact_article(incoming),
        "candidates": [
            {
                "article": _compact_article(row.get("article") or row),
                "evidence": row.get("evidence") or {},
            }
            for row in candidates
        ],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    try:
        from json_repair import repair_json

        parsed = json.loads(repair_json(text))
    except Exception:
        try:
            parsed = json.loads(text)
        except Exception:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("semantic gate model returned no JSON object")
            parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("semantic gate model response was not a JSON object")
    return parsed


def _clamp_confidence(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return min(1.0, max(0.0, number))


def validate_model_decision(
    raw_decision: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> dict[str, Any]:
    candidate_slugs = {
        str(row.get("slug") or (row.get("article") or {}).get("slug") or "").strip()
        for row in candidates
    }
    candidate_slugs.discard("")
    selected = str(raw_decision.get("selected_candidate_slug") or "").strip()
    same_event = raw_decision.get("same_real_world_event") is True
    material_update = raw_decision.get("material_new_update") is True
    confidence = _clamp_confidence(raw_decision.get("confidence"))
    requested_action = str(raw_decision.get("recommended_action") or "").strip()
    reason = str(raw_decision.get("reason") or "").strip()
    shared_anchors = [str(v).strip() for v in (raw_decision.get("shared_anchors") or []) if str(v).strip()]
    novel_facts = [str(v).strip() for v in (raw_decision.get("novel_facts") or []) if str(v).strip()]

    validation_errors: list[str] = []
    if requested_action not in ALLOWED_ACTIONS:
        validation_errors.append("unknown_recommended_action")
    if same_event and selected not in candidate_slugs:
        validation_errors.append("same_event_without_valid_candidate")
    if not same_event and requested_action in {ACTION_DUPLICATE, ACTION_UPDATE}:
        validation_errors.append("same_event_action_without_same_event")
    if same_event and confidence < float(min_confidence):
        validation_errors.append("same_event_confidence_below_threshold")

    if validation_errors:
        action = ACTION_HOLD
    elif same_event:
        action = ACTION_UPDATE if material_update else ACTION_DUPLICATE
    elif requested_action == ACTION_HOLD or confidence < 0.65:
        action = ACTION_HOLD
    else:
        action = ACTION_NEW

    return {
        "status": "validated" if not validation_errors else "invalid_model_response",
        "action": action,
        "recommended_action": requested_action,
        "selected_candidate_slug": selected if selected in candidate_slugs else "",
        "same_real_world_event": same_event,
        "material_new_update": material_update,
        "confidence": confidence,
        "shared_anchors": shared_anchors[:20],
        "novel_facts": novel_facts[:20],
        "reason": reason,
        "validation_errors": validation_errors,
    }


def _prompt(
    incoming: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]
) -> str:
    candidate_payload = []
    for row in candidates:
        article = row.get("article") or row
        candidate_payload.append({
            "article": _compact_article(article),
            "retrieval_evidence": row.get("evidence") or {},
        })
    return f"""You are the final duplicate-publication gate for a local news site.

Compare the fully written INCOMING article with the RECENT CANONICAL CANDIDATES. Decide whether the incoming article covers the exact same real-world incident, case, meeting, game, government action, business event, or continuing proceeding as one candidate.

Do not merge merely because two stories share a city, agency, topic, crime type, road, team, or generic headline vocabulary. The same real-world event requires concrete shared anchors such as the same named participant, exact location, date/time, vehicle, case, governing action, victim, business, or distinctive fact pattern.

Then separately decide whether the incoming article contains a MATERIAL NEW UPDATE. Material updates include a victim being identified, a death after an earlier injury report, an arrest or charge, an official cause or finding, a court ruling or sentence, a consequential government vote, a meaningful casualty revision, or another development that changes what readers need to know. Another outlet repeating the same facts, reordered wording, an additional photograph, routine scene detail, or background explanation is NOT a material update.

Choose exactly one action:
- duplicate_use_existing_canonical: same event, no material update; preserve the candidate page without rewriting it.
- update_existing_canonical: same event and material update; update the candidate page rather than minting a new URL.
- new_story: no candidate is the same event.
- hold: evidence is ambiguous or insufficient.

Return ONLY one JSON object with this exact shape:
{{
  "selected_candidate_slug": "candidate slug or null",
  "same_real_world_event": true,
  "material_new_update": false,
  "confidence": 0.0,
  "shared_anchors": ["specific shared facts"],
  "novel_facts": ["specific genuinely new facts"],
  "reason": "brief evidence-based explanation",
  "recommended_action": "duplicate_use_existing_canonical"
}}

INCOMING ARTICLE:
{json.dumps(_compact_article(incoming), ensure_ascii=False, indent=2)}

RECENT CANONICAL CANDIDATES:
{json.dumps(candidate_payload, ensure_ascii=False, indent=2)}
"""


def adjudicate_candidates(
    client: Any,
    *,
    model: str,
    incoming: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    timeout_seconds: float = 45.0,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> dict[str, Any]:
    """Call the model once and fail closed whenever suspicious candidates exist."""
    if not candidates:
        return {
            "status": "no_candidates",
            "action": ACTION_NEW,
            "selected_candidate_slug": "",
            "same_real_world_event": False,
            "material_new_update": False,
            "confidence": 1.0,
            "shared_anchors": [],
            "novel_facts": [],
            "reason": "No recent fuzzy candidates crossed the retrieval threshold.",
            "validation_errors": [],
        }
    if client is None or not getattr(client, "messages", None):
        return {
            "status": "model_unavailable",
            "action": ACTION_HOLD,
            "selected_candidate_slug": "",
            "same_real_world_event": False,
            "material_new_update": False,
            "confidence": 0.0,
            "shared_anchors": [],
            "novel_facts": [],
            "reason": "Semantic gate model client unavailable; fail-closed hold.",
            "validation_errors": ["model_unavailable"],
        }

    request_client = client
    kwargs = {
        "model": model,
        "max_tokens": 900,
        "temperature": 0,
        "messages": [{"role": "user", "content": _prompt(incoming, candidates)}],
    }
    try:
        if hasattr(client, "with_options"):
            request_client = client.with_options(
                timeout=max(1.0, float(timeout_seconds)), max_retries=0
            )
        else:
            kwargs["timeout"] = max(1.0, float(timeout_seconds))
        response = request_client.messages.create(**kwargs)
        raw_text = response.content[0].text if getattr(response, "content", None) else ""
        parsed = _json_object(raw_text)
        validated = validate_model_decision(
            parsed, candidates, min_confidence=min_confidence
        )
        validated["raw_model_decision"] = parsed
        return validated
    except Exception as exc:
        return {
            "status": "model_error",
            "action": ACTION_HOLD,
            "selected_candidate_slug": "",
            "same_real_world_event": False,
            "material_new_update": False,
            "confidence": 0.0,
            "shared_anchors": [],
            "novel_facts": [],
            "reason": f"Semantic gate model failure; fail-closed hold: {exc}",
            "validation_errors": ["model_error"],
        }
