"""Deterministic story-importance scoring for editorial prioritization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Iterable, Mapping


class ImportanceLevel(str, Enum):
    BREAKING = "breaking"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class ImportanceReason:
    code: str
    label: str
    points: int

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "label": self.label, "points": self.points}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ImportanceReason":
        return cls(
            code=str(value.get("code", "unknown")),
            label=str(value.get("label", "Unknown signal")),
            points=int(value.get("points", 0)),
        )


@dataclass(frozen=True, slots=True)
class StoryImportance:
    score: int
    level: ImportanceLevel
    reasons: tuple[ImportanceReason, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level.value,
            "reasons": [reason.to_dict() for reason in self.reasons],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "StoryImportance":
        if not isinstance(value, Mapping):
            return cls(score=0, level=ImportanceLevel.LOW)
        try:
            level = ImportanceLevel(str(value.get("level", "low")))
        except ValueError:
            level = ImportanceLevel.LOW
        raw_reasons = value.get("reasons", [])
        reasons = tuple(
            ImportanceReason.from_dict(item)
            for item in raw_reasons
            if isinstance(item, Mapping)
        )
        return cls(
            score=max(0, min(100, int(value.get("score", 0)))),
            level=level,
            reasons=reasons,
        )


class StoryImportanceEngine:
    """Score a registry story using transparent, deterministic newsroom rules."""

    _FATALITY = {"fatal", "fatality", "killed", "dead", "dies", "died", "death"}
    _SERIOUS_INJURY = {
        "serious injury", "seriously injured", "critical condition",
        "life threatening", "trauma alert",
    }
    _WEATHER_EMERGENCY = {
        "hurricane", "tropical storm", "tornado", "storm surge",
        "flash flood", "evacuation order", "weather emergency",
    }
    _PUBLIC_SAFETY = {
        "shooting", "stabbing", "fire", "wildfire", "crash", "collision",
        "missing person", "amber alert", "silver alert", "hazmat", "explosion",
        "armed suspect", "lockdown", "rescue",
    }
    _SCHOOL_CLOSURE = {
        "school closed", "schools closed", "school closure", "classes canceled",
        "classes cancelled", "campus closed",
    }
    _GOVERNMENT_ACTION = {
        "city council", "county commission", "school board", "approved", "adopted",
        "ordinance", "resolution", "budget", "public hearing", "emergency declaration",
    }
    _COURT_ACTION = {
        "court", "hearing", "sentenced", "sentencing", "indicted", "trial",
        "lawsuit", "arraignment", "pleaded guilty", "pleads guilty",
    }
    _COUNTIES = {
        "martin county", "st. lucie county", "saint lucie county",
        "indian river county", "okeechobee county", "palm beach county",
    }

    def score(self, story: Mapping[str, Any]) -> StoryImportance:
        status = str(story.get("status", "developing")).strip().lower()
        if status == "archived":
            return StoryImportance(
                score=0,
                level=ImportanceLevel.ARCHIVED,
                reasons=(ImportanceReason("archived", "Archived story", -40),),
            )

        text = self._story_text(story)
        reasons: list[ImportanceReason] = []

        self._add_keyword_reason(reasons, text, self._FATALITY, "fatality", "Fatality reported", 40)
        self._add_phrase_reason(reasons, text, self._SERIOUS_INJURY, "serious_injury", "Serious injury reported", 30)
        self._add_phrase_reason(reasons, text, self._WEATHER_EMERGENCY, "weather_emergency", "Weather emergency", 35)
        self._add_phrase_reason(reasons, text, self._PUBLIC_SAFETY, "public_safety", "Public-safety event", 25)
        self._add_phrase_reason(reasons, text, self._SCHOOL_CLOSURE, "school_closure", "School closure", 20)
        self._add_phrase_reason(reasons, text, self._GOVERNMENT_ACTION, "government_action", "Government action", 15)
        self._add_phrase_reason(reasons, text, self._COURT_ACTION, "court_action", "Court action", 10)

        timeline = story.get("timeline", [])
        if isinstance(timeline, list) and len(timeline) > 1:
            reasons.append(ImportanceReason("follow_up", "Story has follow-up coverage", 10))

        agencies = self._normalized_values(story.get("agencies", []))
        if len(agencies) >= 2:
            reasons.append(ImportanceReason("multi_agency", "Multiple agencies involved", 10))

        if int(story.get("custom_article_count", 0) or 0) > 0:
            reasons.append(ImportanceReason("tct_original", "TCT original coverage", 5))

        county_hits = {county for county in self._COUNTIES if county in text}
        if len(county_hits) >= 2:
            reasons.append(ImportanceReason("multi_county", "Multi-county impact", 10))

        raw_score = sum(reason.points for reason in reasons)
        score = max(0, min(100, raw_score))
        level = self._level_for_score(score)
        return StoryImportance(score=score, level=level, reasons=tuple(reasons))

    @staticmethod
    def _normalized_values(values: Any) -> set[str]:
        if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
            return set()
        return {str(value).strip().lower() for value in values if str(value).strip()}

    def _story_text(self, story: Mapping[str, Any]) -> str:
        values: list[str] = []
        for field in ("titles", "facts", "locations", "agencies", "event_types"):
            raw = story.get(field, [])
            if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
                values.extend(str(value) for value in raw)
        return " ".join(values).lower()

    @staticmethod
    def _add_phrase_reason(
        reasons: list[ImportanceReason],
        text: str,
        phrases: set[str],
        code: str,
        label: str,
        points: int,
    ) -> None:
        if any(phrase in text for phrase in phrases):
            reasons.append(ImportanceReason(code, label, points))

    @staticmethod
    def _add_keyword_reason(
        reasons: list[ImportanceReason],
        text: str,
        keywords: set[str],
        code: str,
        label: str,
        points: int,
    ) -> None:
        words = set(re.findall(r"[a-z0-9]+", text.lower()))
        if words & keywords:
            reasons.append(ImportanceReason(code, label, points))

    @staticmethod
    def _level_for_score(score: int) -> ImportanceLevel:
        if score >= 80:
            return ImportanceLevel.BREAKING
        if score >= 55:
            return ImportanceLevel.HIGH
        if score >= 25:
            return ImportanceLevel.NORMAL
        return ImportanceLevel.LOW
