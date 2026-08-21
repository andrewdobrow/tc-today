import json
from pathlib import Path

from tct_engine.model_bakeoff import compact_category_output, write_bakeoff_artifacts


def _sample_output(prefix, hero_source=1):
    return {
        "hero": {
            "headline": f"{prefix} hero headline",
            "body": f"{prefix} hero body with enough context to review.",
            "urgency_score": 8,
            "source_index": hero_source,
        },
        "cards": [
            {
                "headline": f"{prefix} card headline",
                "teaser": f"{prefix} teaser",
                "body": f"{prefix} card body",
                "source_index": 2,
            }
        ],
        "internal_field_that_must_not_survive": "ignore",
    }


def test_compact_output_keeps_only_editorial_review_fields():
    compact = compact_category_output(_sample_output("Baseline"))
    assert compact["hero"]["headline"] == "Baseline hero headline"
    assert compact["hero"]["source_index"] == 1
    assert compact["cards"][0]["teaser"] == "Baseline teaser"
    assert "internal_field_that_must_not_survive" not in compact


def test_blind_review_hides_model_names_and_answer_key_reveals_them(tmp_path):
    report_path = tmp_path / "data" / "model-bakeoff-report.json"
    review_path = tmp_path / "data" / "model-bakeoff-review.md"
    key_path = tmp_path / "data" / "model-bakeoff-answer-key.json"
    results = [{
        "category_key": "martin",
        "category_label": "Martin County",
        "source_pool": [
            {"title": "First source"},
            {"title": "Second source"},
        ],
        "baseline_output": _sample_output("Baseline", 1),
        "challenger_output": _sample_output("Challenger", 2),
        "challenger_error": "",
        "challenger_duration_seconds": 12.3,
    }]

    report = write_bakeoff_artifacts(
        results=results,
        report_path=report_path,
        review_path=review_path,
        answer_key_path=key_path,
        baseline_model="claude-sonnet-4-5-20250929",
        challenger_model="claude-sonnet-5",
        blind_salt="run-123",
        enabled=True,
    )

    review = review_path.read_text()
    assert "Variant A" in review and "Variant B" in review
    assert "claude-sonnet" not in review.lower()
    assert "Hero/story choice: A / B / Tie" in review
    assert "First source" in review and "Second source" in review

    key = json.loads(key_path.read_text())
    models = {
        key["categories"]["martin"]["variant_a_model"],
        key["categories"]["martin"]["variant_b_model"],
    }
    assert models == {"claude-sonnet-4-5-20250929", "claude-sonnet-5"}
    assert report["publication_isolation"] is True
    assert report["completed_categories"] == 1


def test_generator_bakeoff_is_opt_in_post_build_and_challenger_cannot_publish():
    source = Path("scripts/generate.py").read_text()
    assert 'MODEL_BAKEOFF_ENABLED = os.environ.get("TCT_MODEL_BAKEOFF", "false")' in source
    assert '"TCT_MODEL_BAKEOFF_CHALLENGER", "claude-sonnet-5"' in source
    assert 'request_kwargs["thinking"] = {"type": "disabled"}' in source
    assert 'request_kwargs["max_tokens"] = MODEL_BAKEOFF_MAX_TOKENS' in source
    assert "_queue_model_bakeoff_category(" in source
    assert "_run_model_bakeoff_after_build()" in source

    normal_timing = source.index('print(f"  Timing: total generator runtime')
    shadow_run = source.index("        _run_model_bakeoff_after_build()")
    done = source.index('print(f"Done. {len(all_categories)} categories written.")')
    assert normal_timing < shadow_run < done

    # The challenger result is written only into the bake-off result structure; it
    # is never assigned to live `data` or `all_categories`.
    runner_start = source.index("def _run_model_bakeoff_after_build():")
    runner_end = source.index("\ndef _parse_json_index_array", runner_start)
    runner = source[runner_start:runner_end]
    assert 'result["challenger_output"] = challenger' in runner
    assert "all_categories.append(challenger)" not in runner
    assert "GENERATION_CACHE.put" not in runner


def test_update_workflow_exposes_manual_bakeoff_checkbox_and_artifact():
    workflow = Path(".github/workflows/update.yml").read_text()
    assert "model_bakeoff:" in workflow
    assert 'description: "Run Sonnet 5 shadow model bake-off"' in workflow
    assert "default: false" in workflow
    assert "TCT_MODEL_BAKEOFF: ${{ inputs.model_bakeoff }}" in workflow
    assert "Upload model bake-off review" in workflow
    assert "data/model-bakeoff-review.md" in workflow
    assert "data/model-bakeoff-answer-key.json" in workflow
    assert "data/model-usage-report.json" in workflow
