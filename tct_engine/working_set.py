"""Bound the live editorial working set without discarding historical evidence.

The production story registry and editorial replay journal are operational state, not
an archive.  Keeping every story ever observed in those hot paths makes hourly runs
slower forever.  This module retires old, non-ongoing records from the live registry
into an append-only JSONL history file and trims the replay cache to the same window.

Historical TCT articles, archive metadata, redirects, quarantine tombstones and the
append-only retired-story history remain durable.  Retired stories deliberately stop
participating in ordinary same-story matching: after the hot window, a genuinely new
development may publish as a new article unless the story is explicitly ongoing.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Mapping

WORKING_SET_VERSION = 1
DEFAULT_HOT_DAYS = 21
ONGOING_STATUSES = frozenset({"breaking", "developing", "ongoing"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def file_fingerprint(path: Path | str) -> dict[str, object] | None:
    target = Path(path)
    if not target.exists() or not target.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        size = target.stat().st_size
    except OSError:
        return None
    return {"algorithm": "sha256", "sha256": digest.hexdigest(), "size": size}


def preflight_receipt_path(registry_path: Path | str) -> Path:
    target = Path(registry_path)
    return target.with_name(target.stem + ".preflight.json")


def verify_preflight_receipt(
    registry_path: Path | str,
    *,
    repair_version: int,
) -> dict[str, Any] | None:
    target = Path(registry_path)
    receipt_path = preflight_receipt_path(target)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(receipt, dict) or receipt.get("version") != 1:
        return None
    if int(receipt.get("repair_version", -1)) != int(repair_version):
        return None
    if receipt.get("verification_clean") is not True:
        return None
    current = file_fingerprint(target)
    if not current or receipt.get("registry_fingerprint") != current:
        return None
    return receipt


def _story_latest_timestamp(story: Mapping[str, Any]) -> datetime | None:
    timestamps: list[datetime] = []
    for row in story.get("timeline", ()) or ():
        if isinstance(row, Mapping):
            parsed = _coerce_utc(row.get("published_at"))
            if parsed is not None:
                timestamps.append(parsed)
    for key in (
        "meaningful_update_at",
        "updated_at",
        "last_published_at",
        "first_published_at",
        "published_at",
    ):
        parsed = _coerce_utc(story.get(key))
        if parsed is not None:
            timestamps.append(parsed)
    return max(timestamps) if timestamps else None


def _story_is_explicitly_ongoing(story: Mapping[str, Any]) -> bool:
    if bool(story.get("keep_hot") or story.get("ongoing")):
        return True
    status = str(story.get("status") or "").strip().lower()
    return status in ONGOING_STATUSES


def _append_retired_story_history(
    path: Path,
    rows: list[tuple[str, Mapping[str, Any], datetime | None]],
    *,
    retired_at: datetime,
    hot_days: int,
) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Append-only on purpose: normal production never needs to parse this file.
    # It remains a durable audit/recovery record of the full retired story object.
    with path.open("a", encoding="utf-8") as handle:
        for story_id, story, latest in rows:
            record = {
                "working_set_version": WORKING_SET_VERSION,
                "retired_at": retired_at.isoformat(),
                "hot_window_days": hot_days,
                "story_id": story_id,
                "last_story_timestamp": latest.isoformat() if latest else None,
                "story": story,
            }
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def compact_registry_working_set(
    registry_path: Path | str,
    *,
    history_path: Path | str | None = None,
    now: datetime | None = None,
    hot_days: int = DEFAULT_HOT_DAYS,
) -> dict[str, Any]:
    """Move cold non-ongoing stories out of the live registry.

    The full retired story objects go to JSONL history.  Event mappings and aliases
    pointing only at retired stories are intentionally removed so old incidents no
    longer participate in routine same-story matching.
    """
    target = Path(registry_path)
    effective_now = (now or _utc_now()).astimezone(timezone.utc)
    history = (
        Path(history_path)
        if history_path is not None
        else target.parent / "editorial_story_history"
    )
    if history.suffix.lower() != ".jsonl":
        history = history / f"retired-{effective_now:%Y-%m}.jsonl"
    days = max(1, int(hot_days))
    cutoff = effective_now - timedelta(days=days)

    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "changed": False,
            "reason": "missing_registry",
            "hot_window_days": days,
            "active_before": 0,
            "active_after": 0,
            "retired": 0,
        }
    if not isinstance(payload, dict):
        raise ValueError("Story registry must contain a JSON object")

    stories = payload.get("stories")
    if not isinstance(stories, dict):
        raise ValueError("Story registry stories must contain a JSON object")

    active: dict[str, Any] = {}
    retired: list[tuple[str, Mapping[str, Any], datetime | None]] = []
    kept_recent = 0
    kept_ongoing = 0
    kept_unknown_time = 0

    for raw_story_id, raw_story in stories.items():
        story_id = str(raw_story_id)
        if not isinstance(raw_story, Mapping):
            # Unknown shapes fail safe: keep them live rather than discarding state.
            active[story_id] = raw_story
            kept_unknown_time += 1
            continue
        latest = _story_latest_timestamp(raw_story)
        ongoing = _story_is_explicitly_ongoing(raw_story)
        if ongoing:
            active[story_id] = raw_story
            kept_ongoing += 1
        elif latest is None:
            active[story_id] = raw_story
            kept_unknown_time += 1
        elif latest >= cutoff:
            active[story_id] = raw_story
            kept_recent += 1
        else:
            retired.append((story_id, raw_story, latest))

    if not retired:
        return {
            "changed": False,
            "reason": "already_bounded",
            "hot_window_days": days,
            "cutoff": cutoff.isoformat(),
            "active_before": len(stories),
            "active_after": len(stories),
            "retired": 0,
            "kept_recent": kept_recent,
            "kept_ongoing": kept_ongoing,
            "kept_unknown_time": kept_unknown_time,
        }

    active_ids = set(active)
    aliases = payload.get("story_aliases")
    aliases = aliases if isinstance(aliases, dict) else {}

    def canonical_story_id(story_id: str) -> str:
        seen: set[str] = set()
        current = story_id
        while current in aliases and current not in seen:
            seen.add(current)
            current = str(aliases[current])
        return current

    event_to_story = payload.get("event_to_story")
    if isinstance(event_to_story, dict):
        payload["event_to_story"] = {
            event_key: story_id
            for event_key, story_id in event_to_story.items()
            if canonical_story_id(str(story_id)) in active_ids
        }

    payload["story_aliases"] = {
        alias: target_id
        for alias, target_id in aliases.items()
        if canonical_story_id(str(target_id)) in active_ids
    }
    payload["stories"] = active
    previous = payload.get("working_set") if isinstance(payload.get("working_set"), dict) else {}
    payload["working_set"] = {
        "version": WORKING_SET_VERSION,
        "hot_window_days": days,
        "cutoff": cutoff.isoformat(),
        "last_compacted_at": effective_now.isoformat(),
        "active_story_count": len(active),
        "retired_this_pass": len(retired),
        "retired_story_count_total": int(previous.get("retired_story_count_total", 0) or 0)
        + len(retired),
        "history_file": history.name,
        "policy": "recent_or_explicitly_ongoing",
    }

    # Preserve the full retired records before removing them from the hot file.
    _append_retired_story_history(
        history,
        retired,
        retired_at=effective_now,
        hot_days=days,
    )
    _atomic_write_json(target, payload)

    return {
        "changed": True,
        "reason": "cold_stories_retired",
        "hot_window_days": days,
        "cutoff": cutoff.isoformat(),
        "active_before": len(stories),
        "active_after": len(active),
        "retired": len(retired),
        "kept_recent": kept_recent,
        "kept_ongoing": kept_ongoing,
        "kept_unknown_time": kept_unknown_time,
        "history_path": str(history),
    }


def _editorial_record_timestamp(record: Mapping[str, Any]) -> datetime | None:
    entry = record.get("entry")
    if not isinstance(entry, Mapping):
        return None
    for key in ("published", "updated", "date"):
        parsed = _coerce_utc(entry.get(key))
        if parsed is not None:
            return parsed
    return None


def compact_editorial_state_working_set(
    state_path: Path | str,
    *,
    registry_path: Path | str,
    now: datetime | None = None,
    hot_days: int = DEFAULT_HOT_DAYS,
    repair_version: int,
) -> dict[str, Any]:
    """Trim the replay journal/snapshot to the same bounded live-news horizon.

    If the registry preflight was clean and only the working-set retirement changed
    the authoritative file, the filtered derived snapshot can be rebound to the now
    current registry fingerprint.  If active repair changed identity, we deliberately
    leave the old fingerprint in place so EditorialEngine performs one bounded replay.
    """
    target = Path(state_path)
    registry = Path(registry_path)
    if not target.exists():
        return {"changed": False, "reason": "missing_state"}

    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Editorial state must contain a JSON object")
    articles = payload.get("articles")
    if not isinstance(articles, list):
        raise ValueError("Editorial state articles must be a list")

    effective_now = (now or _utc_now()).astimezone(timezone.utc)
    days = max(1, int(hot_days))
    cutoff = effective_now - timedelta(days=days)

    retained_articles: list[Any] = []
    dropped_articles = 0
    for record in articles:
        if not isinstance(record, Mapping):
            retained_articles.append(record)
            continue
        stamp = _editorial_record_timestamp(record)
        if stamp is None or stamp >= cutoff:
            retained_articles.append(record)
        else:
            dropped_articles += 1

    # The compacted registry is the authority for which event identities remain
    # live.  Filter the derived event snapshot to those exact active event keys.
    # Candidate timestamps are intentionally not used here: historical replay used
    # the engine's run timestamp for many legacy candidates, so those timestamps do
    # not reliably represent source age.
    active_event_keys: set[str] = set()
    try:
        registry_payload = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        registry_payload = {}
    stories = registry_payload.get("stories", {}) if isinstance(registry_payload, dict) else {}
    if isinstance(stories, dict):
        for story in stories.values():
            if isinstance(story, Mapping):
                active_event_keys.update(
                    str(key) for key in (story.get("events") or ()) if str(key)
                )

    pipeline = payload.get("pipeline_state")
    dropped_candidates = 0
    dropped_snapshots = 0
    if isinstance(pipeline, dict) and pipeline.get("version") == 1:
        candidates = pipeline.get("candidates")
        snapshots = pipeline.get("snapshots")
        if isinstance(candidates, list) and isinstance(snapshots, list):
            retained_candidates: list[Any] = []
            retained_event_keys: set[str] = set()
            for row in candidates:
                if not isinstance(row, Mapping):
                    retained_candidates.append(row)
                    continue
                event_key = str(row.get("event_key") or "")
                if event_key and event_key in active_event_keys:
                    retained_candidates.append(row)
                    retained_event_keys.add(event_key)
                else:
                    dropped_candidates += 1
            retained_snapshots: list[Any] = []
            for row in snapshots:
                if not isinstance(row, Mapping):
                    retained_snapshots.append(row)
                    continue
                event_key = str(row.get("event_key") or "")
                if event_key in retained_event_keys:
                    retained_snapshots.append(row)
                else:
                    dropped_snapshots += 1
            pipeline["candidates"] = retained_candidates
            pipeline["snapshots"] = retained_snapshots

    payload["articles"] = retained_articles
    payload["working_set"] = {
        "version": WORKING_SET_VERSION,
        "hot_window_days": days,
        "cutoff": cutoff.isoformat(),
        "compacted_at": effective_now.isoformat(),
        "retained_articles": len(retained_articles),
        "dropped_articles": dropped_articles,
    }

    rebound = False
    receipt = verify_preflight_receipt(registry, repair_version=repair_version)
    if (
        receipt is not None
        and receipt.get("repair_changed") is False
        and isinstance(payload.get("pipeline_state"), dict)
    ):
        current_fingerprint = file_fingerprint(registry)
        if current_fingerprint is not None:
            payload["registry_fingerprint"] = current_fingerprint
            rebound = True

    changed = bool(dropped_articles or dropped_candidates or dropped_snapshots or rebound)
    if changed:
        _atomic_write_json(target, payload)

    return {
        "changed": changed,
        "reason": "working_set_compacted" if changed else "already_bounded",
        "hot_window_days": days,
        "cutoff": cutoff.isoformat(),
        "articles_before": len(articles),
        "articles_after": len(retained_articles),
        "articles_dropped": dropped_articles,
        "pipeline_candidates_dropped": dropped_candidates,
        "pipeline_snapshots_dropped": dropped_snapshots,
        "registry_fingerprint_rebound": rebound,
    }
