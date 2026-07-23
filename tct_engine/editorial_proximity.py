"""Mission-aligned ranking for a Treasure Coast local newsroom."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class EditorialProximity:
    score: int
    scope: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"score": self.score, "scope": self.scope, "reason": self.reason}


_SCOPE_SCORES = {
    "treasure_coast_local": 100,
    "treasure_coast_region": 95,
    "florida": 55,
    "national": 20,
    "unknown": 35,
}


def classify_editorial_proximity(story: Mapping[str, Any]) -> EditorialProximity:
    locality = story.get("local_relevance") or {}
    scope = str(locality.get("scope") or "unknown")
    score = _SCOPE_SCORES.get(scope, 35)

    if int(story.get("custom_article_count", 0) or 0) > 0:
        score = max(score, 100)
        reason = "TCT original coverage receives maximum mission proximity"
    elif scope == "treasure_coast_local":
        reason = "Directly affects a Treasure Coast county or municipality"
    elif scope == "treasure_coast_region":
        reason = "Directly affects the Treasure Coast region"
    elif scope == "florida":
        reason = "Florida-wide coverage with indirect local relevance"
    elif scope == "national":
        reason = "National coverage outside TCT's primary local mission"
    else:
        reason = "Local mission proximity could not be established"

    return EditorialProximity(score=score, scope=scope, reason=reason)


def calculate_editorial_priority(importance_score: int, proximity_score: int) -> int:
    """Blend consequence with mission proximity while preserving a 0-100 scale."""
    importance = max(0, min(100, int(importance_score)))
    proximity = max(0, min(100, int(proximity_score)))
    return round(importance * proximity / 100)
