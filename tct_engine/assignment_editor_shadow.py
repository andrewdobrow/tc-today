"""Publication-isolated assignment-editor shadow experiment for TCT.

This module contains only normalization and artifact-writing helpers. The generator
owns model execution. No function here participates in live publication state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .model_bakeoff import compact_category_output

ASSIGNMENT_EDITOR_SHADOW_SCHEMA_VERSION = 2
ASSIGNMENT_EDITOR_SHADOW_VERSION = "1.13.6.6a"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_index(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        index = int(value)
    except (TypeError, ValueError):
        return None
    return index if index >= 1 else None


def normalize_assignment_plan(
    data: Any,
    *,
    source_count: int,
    max_cards: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Normalize an editor plan and return deterministic selection diagnostics.

    Invalid/out-of-range/duplicate source indexes are removed rather than silently
    remapped. A missing valid hero leaves the plan unscoreable; callers fail closed.
    """
    source_count = max(0, int(source_count or 0))
    max_cards = max(0, int(max_cards or 0))
    raw = data if isinstance(data, dict) else {}
    raw_hero = raw.get("hero") if isinstance(raw.get("hero"), dict) else {}
    raw_cards = raw.get("cards") if isinstance(raw.get("cards"), list) else []

    invalid_indexes: List[Any] = []
    duplicate_indexes: List[int] = []
    selected: List[int] = []

    hero_index = _coerce_index(raw_hero.get("source_index"))
    if hero_index is None or hero_index > source_count:
        if raw_hero.get("source_index") not in (None, ""):
            invalid_indexes.append(raw_hero.get("source_index"))
        hero_index = None

    hero: Dict[str, Any] = {}
    if hero_index is not None:
        selected.append(hero_index)
        hero = {
            "source_index": hero_index,
            "angle": str(raw_hero.get("angle") or "").strip(),
            "urgency_score": raw_hero.get("urgency_score"),
        }

    cards: List[Dict[str, Any]] = []
    for item in raw_cards:
        if not isinstance(item, dict):
            continue
        index = _coerce_index(item.get("source_index"))
        if index is None or index > source_count:
            if item.get("source_index") not in (None, ""):
                invalid_indexes.append(item.get("source_index"))
            continue
        if index in selected:
            duplicate_indexes.append(index)
            continue
        selected.append(index)
        cards.append({
            "source_index": index,
            "angle": str(item.get("angle") or "").strip(),
            "urgency_score": item.get("urgency_score"),
        })
        if len(cards) >= max_cards:
            break

    all_indexes = list(range(1, source_count + 1))
    diagnostics = {
        "valid_hero": hero_index is not None,
        "source_mapping_valid": hero_index is not None and not invalid_indexes and not duplicate_indexes,
        "selected_source_indexes": selected,
        "omitted_source_indexes": [idx for idx in all_indexes if idx not in selected],
        "invalid_source_indexes": invalid_indexes,
        "duplicate_source_indexes": duplicate_indexes,
    }
    return {"hero": hero, "cards": cards}, diagnostics


def _variant_order(category_key: str, blind_salt: str) -> bool:
    digest = hashlib.sha256(f"assignment-editor:{blind_salt}:{category_key}".encode("utf-8")).digest()
    return bool(digest[0] & 1)


def _source_title_for_index(source_pool: List[Dict[str, Any]], source_index: Any) -> str:
    index = _coerce_index(source_index)
    if index is None:
        return ""
    pos = index - 1
    if 0 <= pos < len(source_pool):
        return str(source_pool[pos].get("title") or "")
    return ""


def _variant_markdown(label: str, output: Dict[str, Any], source_pool: List[Dict[str, Any]]) -> List[str]:
    lines = [f"### Variant {label}", ""]
    hero = output.get("hero") or {}
    if hero:
        lines.append(f"**Hero:** {hero.get('headline') or '(no headline)'}")
        source_index = hero.get("source_index")
        source_title = _source_title_for_index(source_pool, source_index)
        if source_index:
            note = f"Source #{source_index}"
            if source_title:
                note += f": {source_title}"
            lines.append(f"**Hero source choice:** {note}")
        if hero.get("urgency_score") not in (None, ""):
            lines.append(f"**Urgency:** {hero.get('urgency_score')}")
        lines.append("")
        if hero.get("body"):
            lines.extend([str(hero["body"]).strip(), ""])
    else:
        lines.extend(["**Hero:** No usable hero returned.", ""])

    cards = output.get("cards") or []
    if cards:
        lines.extend(["**Additional stories**", ""])
        for idx, card in enumerate(cards, 1):
            lines.append(f"**{idx}. {card.get('headline') or '(no headline)'}**")
            source_index = card.get("source_index")
            source_title = _source_title_for_index(source_pool, source_index)
            if source_index:
                note = f"Source #{source_index}"
                if source_title:
                    note += f": {source_title}"
                lines.append(note)
            if card.get("teaser"):
                lines.append(f"Teaser: {str(card['teaser']).strip()}")
            if card.get("body"):
                lines.extend(["", str(card["body"]).strip()])
            lines.append("")
    return lines


def _selected_sources(output: Dict[str, Any]) -> List[int]:
    indexes: List[int] = []
    hero = output.get("hero") or {}
    hero_idx = _coerce_index(hero.get("source_index"))
    if hero_idx is not None:
        indexes.append(hero_idx)
    for card in output.get("cards") or []:
        if not isinstance(card, dict):
            continue
        idx = _coerce_index(card.get("source_index"))
        if idx is not None:
            indexes.append(idx)
    return indexes


def _comparison_signals(output: Dict[str, Any], source_pool: List[Dict[str, Any]]) -> Dict[str, Any]:
    selected = _selected_sources(output)
    return {
        "selected_source_indexes": selected,
        "duplicate_source_indexes": sorted({idx for idx in selected if selected.count(idx) > 1}),
        "omitted_source_indexes": [
            idx for idx in range(1, len(source_pool) + 1) if idx not in selected
        ],
        "hero_source_index": (output.get("hero") or {}).get("source_index"),
        "hero_headline": str((output.get("hero") or {}).get("headline") or ""),
    }


def write_assignment_editor_artifacts(
    *,
    results: Iterable[Dict[str, Any]],
    report_path: Path,
    review_path: Path,
    answer_key_path: Path,
    production_model: str,
    editor_model: str,
    writer_model: str,
    blind_salt: str,
    enabled: bool,
) -> Dict[str, Any]:
    """Write final-pipeline-aligned machine, blind-review, and answer-key artifacts."""
    report_path = Path(report_path)
    review_path = Path(review_path)
    answer_key_path = Path(answer_key_path)
    rows = list(results)

    report_rows: List[Dict[str, Any]] = []
    answer_categories: Dict[str, Any] = {}
    review_lines = [
        "# TCT Assignment Editor Shadow Experiment — Final-Pipeline Blind Review",
        "",
        "The live publisher was not changed. Both displayed variants are final-pipeline comparison projections: the production side is captured from the actual final live category after normal deterministic corrections, and the publication-isolated shadow side is passed through the same shared eligibility, freshness, publication-quality, identity, suppression, county-authority, and canonical-surface rules before scoring. Raw pre-alignment model outputs remain available only in the machine report.",
        "",
        "Judge the final newsroom result, not verbosity. Score: (1) hero/story choice, (2) supporting-story selection and omissions, (3) ordering, (4) angle/new-development focus, (5) source mapping, (6) headline accuracy and strength, (7) lead/context, (8) factual fidelity, (9) completeness, (10) unnecessary filler, and (11) overall publishability. Record A, B, or Tie before opening the answer key.",
        "",
    ]

    completed = 0
    failed = 0
    for row in rows:
        category_key = str(row.get("category_key") or "unknown")
        category_label = str(row.get("category_label") or category_key)
        source_pool = list(row.get("source_pool") or [])

        raw_baseline = compact_category_output(
            row.get("raw_baseline_output") or row.get("baseline_output")
        )
        final_baseline = compact_category_output(
            row.get("final_baseline_output") or row.get("baseline_output")
        )
        raw_challenger = compact_category_output(
            row.get("raw_challenger_output") or row.get("challenger_output")
        )
        final_challenger = compact_category_output(
            row.get("final_challenger_output") or row.get("challenger_output")
        )
        error = str(row.get("challenger_error") or "")
        baseline_is_a = _variant_order(category_key, blind_salt)

        variant_a = final_baseline if baseline_is_a else final_challenger
        variant_b = final_challenger if baseline_is_a else final_baseline
        variant_a_path = "current_production" if baseline_is_a else "sonnet5_editor_sonnet45_writer"
        variant_b_path = "sonnet5_editor_sonnet45_writer" if baseline_is_a else "current_production"

        if error:
            failed += 1
        else:
            completed += 1

        raw_baseline_signals = _comparison_signals(raw_baseline, source_pool)
        final_baseline_signals = _comparison_signals(final_baseline, source_pool)
        raw_challenger_signals = _comparison_signals(raw_challenger, source_pool)
        final_challenger_signals = _comparison_signals(final_challenger, source_pool)
        assignment_plan = row.get("assignment_plan") or {}
        assignment_diag = row.get("assignment_diagnostics") or {}

        report_rows.append({
            "category_key": category_key,
            "category_label": category_label,
            "source_pool": source_pool,
            "production_model": production_model,
            "editor_model": editor_model,
            "writer_model": writer_model,
            "raw_baseline_output": raw_baseline,
            "final_baseline_output": final_baseline,
            # Backward-compatible aliases now intentionally point at the aligned objects.
            "baseline_output": final_baseline,
            "assignment_plan": assignment_plan,
            "assignment_diagnostics": assignment_diag,
            "raw_challenger_output": raw_challenger,
            "final_challenger_output": final_challenger,
            "challenger_output": final_challenger,
            "alignment_diagnostics": row.get("alignment_diagnostics") or {},
            "challenger_error": error or None,
            "editor_duration_seconds": row.get("editor_duration_seconds"),
            "editor_actual_model": row.get("editor_actual_model"),
            "writer_duration_seconds": row.get("writer_duration_seconds"),
            "writer_actual_models": row.get("writer_actual_models") or [],
            "raw_comparison_signals": {
                "baseline": raw_baseline_signals,
                "challenger": raw_challenger_signals,
                "same_hero_source_index": (
                    raw_baseline_signals["hero_source_index"] == raw_challenger_signals["hero_source_index"]
                    if raw_baseline_signals["hero_source_index"] is not None
                    and raw_challenger_signals["hero_source_index"] is not None
                    else None
                ),
            },
            "comparison_signals": {
                "same_hero_source_index": (
                    final_baseline_signals["hero_source_index"] == final_challenger_signals["hero_source_index"]
                    if final_baseline_signals["hero_source_index"] is not None
                    and final_challenger_signals["hero_source_index"] is not None
                    else None
                ),
                "baseline_selected_source_indexes": final_baseline_signals["selected_source_indexes"],
                "challenger_selected_source_indexes": final_challenger_signals["selected_source_indexes"],
                "baseline_duplicate_source_indexes": final_baseline_signals["duplicate_source_indexes"],
                "challenger_duplicate_source_indexes": final_challenger_signals["duplicate_source_indexes"],
                "baseline_omitted_source_indexes": final_baseline_signals["omitted_source_indexes"],
                "challenger_omitted_source_indexes": final_challenger_signals["omitted_source_indexes"],
                "baseline_final_hero_headline": final_baseline_signals["hero_headline"],
                "challenger_final_hero_headline": final_challenger_signals["hero_headline"],
                "challenger_source_mapping_valid": bool(assignment_diag.get("source_mapping_valid")),
            },
        })

        answer_categories[category_key] = {
            "category_label": category_label,
            "variant_a_path": variant_a_path,
            "variant_b_path": variant_b_path,
            "current_production_model": production_model,
            "shadow_assignment_editor_model": editor_model,
            "shadow_writer_model": writer_model,
            "comparison_stage": "final_pipeline_aligned",
        }

        review_lines.extend([f"## {category_label}", "", "### Source pool", ""])
        for index, source in enumerate(source_pool, 1):
            review_lines.append(f"{index}. {source.get('title') or '(untitled source)'}")
        review_lines.append("")
        if error:
            review_lines.extend([
                "**The shadow architecture failed for this category. This category is not scoreable.**",
                "",
            ])
        else:
            review_lines.extend(_variant_markdown("A", variant_a, source_pool))
            review_lines.extend(_variant_markdown("B", variant_b, source_pool))
            review_lines.extend([
                "**Scorecard**",
                "",
                "- Hero/story choice: A / B / Tie",
                "- Supporting-story selection/omissions: A / B / Tie",
                "- Story ordering: A / B / Tie",
                "- Angle/new-development focus: A / B / Tie",
                "- Source mapping: A / B / Tie",
                "- Headline: A / B / Tie",
                "- Lead and context: A / B / Tie",
                "- Factual fidelity: A / B / Tie",
                "- Completeness: A / B / Tie",
                "- Least filler: A / B / Tie",
                "- Overall publishability: A / B / Tie",
                "",
            ])
        review_lines.extend(["---", ""])

    generated_at = _utc_now_iso()
    report = {
        "schema_version": ASSIGNMENT_EDITOR_SHADOW_SCHEMA_VERSION,
        "experiment_version": ASSIGNMENT_EDITOR_SHADOW_VERSION,
        "generated_at": generated_at,
        "enabled": bool(enabled),
        "publication_isolation": True,
        "comparison_stage": "final_pipeline_aligned",
        "current_production_model": production_model,
        "shadow_architecture": {
            "assignment_editor_model": editor_model,
            "writer_model": writer_model,
            "editor_role": "story selection, hero/supporting order, angle, urgency, exact source mapping",
            "writer_role": "write only the preassigned single source/angle; no story selection",
        },
        "queued_categories": len(rows),
        "completed_categories": completed,
        "failed_categories": failed,
        "categories": report_rows,
    }
    answer_key = {
        "schema_version": 2,
        "experiment_version": ASSIGNMENT_EDITOR_SHADOW_VERSION,
        "generated_at": generated_at,
        "instruction": "Open only after scoring the final-pipeline blind review.",
        "comparison_stage": "final_pipeline_aligned",
        "categories": answer_categories,
    }

    for path in (report_path, review_path, answer_key_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    answer_key_path.write_text(json.dumps(answer_key, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    review_path.write_text("\n".join(review_lines).rstrip() + "\n", encoding="utf-8")
    return report

