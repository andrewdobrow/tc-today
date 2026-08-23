import json
import os
import sys
import types
from pathlib import Path

import pytest

# Keep generator imports offline-safe in local validation environments. GitHub
# installs the real dependencies before running this same suite.
if "feedparser" not in sys.modules:
    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
    sys.modules["feedparser"] = feedparser
if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class _Anthropic:
        def __init__(self, *args, **kwargs):
            self.messages = types.SimpleNamespace(
                create=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline test"))
            )

    anthropic.Anthropic = _Anthropic
    sys.modules["anthropic"] = anthropic
os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")

from tct_engine.assignment_editor_shadow import (
    normalize_assignment_plan,
    write_assignment_editor_artifacts,
)
from tct_engine.model_usage import _WORKLOAD_CLASS_BY_FUNCTION


def _sample_output(prefix, hero_source=1, card_source=2):
    return {
        "hero": {
            "headline": f"{prefix} hero",
            "body": f"{prefix} hero body with local context.",
            "urgency_score": 8,
            "published": "Fri, 21 Aug 2026 20:00:00 -0400",
            "source_index": hero_source,
        },
        "cards": [
            {
                "headline": f"{prefix} card",
                "teaser": f"{prefix} teaser",
                "body": f"{prefix} card body.",
                "urgency_score": 6,
                "published": "Fri, 21 Aug 2026 19:00:00 -0400",
                "source_index": card_source,
            }
        ],
    }


def test_assignment_plan_enforces_exact_unique_source_mapping():
    plan, diagnostics = normalize_assignment_plan(
        {
            "hero": {"source_index": 2, "angle": "Lead with the new arrest", "urgency_score": 9},
            "cards": [
                {"source_index": 2, "angle": "duplicate", "urgency_score": 5},
                {"source_index": 9, "angle": "out of range", "urgency_score": 5},
                {"source_index": 1, "angle": "supporting update", "urgency_score": 6},
            ],
        },
        source_count=3,
        max_cards=2,
    )
    assert plan["hero"]["source_index"] == 2
    assert [card["source_index"] for card in plan["cards"]] == [1]
    assert diagnostics["duplicate_source_indexes"] == [2]
    assert diagnostics["invalid_source_indexes"] == [9]
    assert diagnostics["source_mapping_valid"] is False
    assert diagnostics["omitted_source_indexes"] == [3]


def test_assignment_plan_requires_valid_hero():
    plan, diagnostics = normalize_assignment_plan(
        {"hero": {"source_index": 7}, "cards": []},
        source_count=2,
        max_cards=1,
    )
    assert plan["hero"] == {}
    assert diagnostics["valid_hero"] is False
    assert diagnostics["source_mapping_valid"] is False


def test_blind_review_hides_architecture_and_models_but_answer_key_reveals_them(tmp_path):
    report_path = tmp_path / "data" / "assignment-editor-shadow-report.json"
    review_path = tmp_path / "data" / "assignment-editor-shadow-review.md"
    key_path = tmp_path / "data" / "assignment-editor-shadow-answer-key.json"
    results = [{
        "category_key": "crime",
        "category_label": "Crime & Safety",
        "source_pool": [{"title": "First source"}, {"title": "Second source"}],
        "raw_baseline_output": _sample_output("RAW BASELINE", 1, 2),
        "final_baseline_output": _sample_output("FINAL BASELINE", 2, 1),
        "assignment_plan": {
            "hero": {"source_index": 2, "angle": "Lead with arrest", "urgency_score": 9},
            "cards": [{"source_index": 1, "angle": "Support", "urgency_score": 6}],
        },
        "assignment_diagnostics": {
            "source_mapping_valid": True,
            "selected_source_indexes": [2, 1],
            "omitted_source_indexes": [],
            "invalid_source_indexes": [],
            "duplicate_source_indexes": [],
        },
        "raw_challenger_output": _sample_output("RAW SHADOW", 2, 1),
        "final_challenger_output": _sample_output("FINAL SHADOW", 1, 2),
        "alignment_diagnostics": {"production": {"aligned": True}, "shadow": {"aligned": True}},
        "challenger_error": "",
        "editor_duration_seconds": 4.2,
        "writer_duration_seconds": 8.5,
        "writer_actual_models": ["claude-sonnet-4-5-20250929", "claude-sonnet-4-5-20250929"],
    }]

    report = write_assignment_editor_artifacts(
        results=results,
        report_path=report_path,
        review_path=review_path,
        answer_key_path=key_path,
        production_model="claude-sonnet-4-5-20250929",
        editor_model="claude-sonnet-5",
        writer_model="claude-sonnet-4-5",
        blind_salt="run-456",
        enabled=True,
    )

    review = review_path.read_text()
    assert "Variant A" in review and "Variant B" in review
    assert "claude-sonnet" not in review.lower()
    assert "Supporting-story selection/omissions" in review
    assert "Angle/new-development focus" in review
    assert "Source mapping" in review
    assert "First source" in review and "Second source" in review
    assert "FINAL BASELINE" in review and "FINAL SHADOW" in review
    assert "RAW BASELINE" not in review and "RAW SHADOW" not in review
    assert "final-pipeline" in review.lower()

    key = json.loads(key_path.read_text())
    paths = {
        key["categories"]["crime"]["variant_a_path"],
        key["categories"]["crime"]["variant_b_path"],
    }
    assert paths == {"current_production", "sonnet5_editor_sonnet45_writer"}
    assert report["publication_isolation"] is True
    assert report["comparison_stage"] == "final_pipeline_aligned"
    assert report["completed_categories"] == 1
    row = report["categories"][0]
    assert row["raw_baseline_output"]["hero"]["headline"] == "RAW BASELINE hero"
    assert row["final_baseline_output"]["hero"]["headline"] == "FINAL BASELINE hero"
    assert row["raw_challenger_output"]["hero"]["headline"] == "RAW SHADOW hero"
    assert row["final_challenger_output"]["hero"]["headline"] == "FINAL SHADOW hero"
    assert row["comparison_signals"]["challenger_source_mapping_valid"] is True


class _Block:
    def __init__(self, text):
        self.text = text


class _Response:
    def __init__(self, text, model="claude-sonnet-4-5-20250929"):
        self.content = [_Block(text)]
        self.model = model


class _QueueMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("No fake response queued")
        return self.responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.messages = _QueueMessages(responses)

    def with_options(self, **kwargs):
        return self


def _shadow_packet():
    return {
        "category_key": "martin",
        "category_label": "Martin County",
        "source_inputs": [
            {
                "source_index": 1,
                "title": "PALM CITY SOURCE TITLE",
                "published": "Fri, 21 Aug 2026 20:00:00 -0400",
                "source_type": "publisher",
                "source_quality": "full",
                "hero_eligible": True,
                "category_match_score": 9,
                "story_form": "new",
                "article_text": "UNIQUE_SOURCE_ONE_FACTS about Palm City and thirty-six dogs.",
                "canonical_context_headline": "",
                "canonical_context_body": "",
            },
            {
                "source_index": 2,
                "title": "HOBE SOUND SOURCE TITLE",
                "published": "Fri, 21 Aug 2026 19:00:00 -0400",
                "source_type": "publisher",
                "source_quality": "full",
                "hero_eligible": True,
                "category_match_score": 8,
                "story_form": "new",
                "article_text": "UNIQUE_SOURCE_TWO_FACTS about a train collision.",
                "canonical_context_headline": "",
                "canonical_context_body": "",
            },
        ],
    }


def test_writer_receives_only_preassigned_single_source(monkeypatch):
    # Import after test collection so generate.py remains side-effect free without an API key.
    from scripts import generate

    response = _Response(json.dumps({
        "headline": "Palm City update",
        "teaser": "A concise teaser.",
        "body": "Paragraph one.\n\nParagraph two.",
        "urgency_score": 1,
        "published": "wrong",
        "source_index": 99,
    }))
    fake = _FakeClient([response])
    monkeypatch.setattr(generate, "client", fake)

    item, actual_model, _duration = generate._run_assignment_writer(
        _shadow_packet(),
        {"source_index": 1, "angle": "Lead with the surrender", "urgency_score": 8},
        role="card",
    )
    call = fake.messages.calls[0]
    prompt = call["messages"][0]["content"]
    assert "UNIQUE_SOURCE_ONE_FACTS" in prompt
    assert "PALM CITY SOURCE TITLE" in prompt
    assert "UNIQUE_SOURCE_TWO_FACTS" not in prompt
    assert "HOBE SOUND SOURCE TITLE" not in prompt
    assert call["model"] == generate.MODEL_ARTICLES
    # Writer cannot override assignment metadata.
    assert item["source_index"] == 1
    assert item["urgency_score"] == 8
    assert item["published"] == "Fri, 21 Aug 2026 20:00:00 -0400"
    assert actual_model == "claude-sonnet-4-5-20250929"


def test_editor_has_selection_authority_but_no_publication_writing_task(monkeypatch):
    from scripts import generate

    response = _Response(
        json.dumps({
            "hero": {"source_index": 2, "angle": "Lead with the collision impact", "urgency_score": 8},
            "cards": [{"source_index": 1, "angle": "Lead with the surrender", "urgency_score": 7}],
        }),
        model="claude-sonnet-5",
    )
    fake = _FakeClient([response])
    monkeypatch.setattr(generate, "client", fake)

    plan, diagnostics, actual_model, _duration = generate._run_assignment_editor(_shadow_packet())
    prompt = fake.messages.calls[0]["messages"][0]["content"]
    assert "Your job is ONLY editorial assignment" in prompt
    assert "Do not write an article, teaser, headline, or prose for publication" in prompt
    assert [plan["hero"]["source_index"]] + [c["source_index"] for c in plan["cards"]] == [2, 1]
    assert diagnostics["source_mapping_valid"] is True
    assert actual_model == "claude-sonnet-5"


def test_generator_shadow_is_opt_in_post_build_and_cannot_publish():
    source = Path("scripts/generate.py").read_text()
    assert '"TCT_ASSIGNMENT_EDITOR_SHADOW", "false"' in source
    assert '"TCT_ASSIGNMENT_EDITOR_MODEL", "claude-sonnet-5"' in source
    assert "_queue_assignment_editor_category(" in source
    assert "_run_assignment_editor_shadow_after_build(all_categories, _pre_generation_archive)" in source

    normal_timing = source.index('print(f"  Timing: total generator runtime')
    shadow_run = source.index("        _run_assignment_editor_shadow_after_build(all_categories, _pre_generation_archive)")
    done = source.index('print(f"Done. {len(all_categories)} categories written.")')
    assert normal_timing < shadow_run < done

    runner_start = source.index("def _run_assignment_editor_shadow_after_build(all_categories, pre_generation_archive):")
    runner_end = source.index("\ndef _parse_json_index_array", runner_start)
    runner = source[runner_start:runner_end]
    assert 'result["raw_challenger_output"] = raw_challenger' in runner
    assert 'result["final_challenger_output"] = final_challenger' in runner
    assert "_assignment_shadow_final_production_projection" in runner
    assert "_assignment_shadow_final_projection" in runner
    assert "all_categories.append" not in runner
    assert "GENERATION_CACHE.put" not in runner



def test_final_production_projection_uses_actual_live_hero_and_omits_archive_filler_cards():
    from scripts import generate

    packet = _shadow_packet()
    packet["source_inputs"][0]["link"] = "https://example.com/source-one"
    packet["source_inputs"][0]["source_url"] = "https://example.com/source-one"
    final_categories = [{
        "category_key": "martin",
        "category_label": "Martin County",
        "hero": {
            "headline": "Brightline archive recovery hero",
            "body": "A final deterministic recovery hero body with enough context.",
            "_archive_only": True,
            "_archive_verified_quality": True,
        },
        "cards": [
            {
                "headline": "Current packet story",
                "source_title": "PALM CITY SOURCE TITLE",
                "source_url": "https://example.com/source-one",
                "body": "Current packet story body.",
            },
            {
                "headline": "Older archive filler",
                "_archive_only": True,
                "_archive_verified_quality": True,
            },
        ],
    }]
    projection, diagnostics = generate._assignment_shadow_final_production_projection(
        packet, final_categories
    )
    assert projection["hero"]["headline"] == "Brightline archive recovery hero"
    assert [card["headline"] for card in projection["cards"]] == ["Current packet story"]
    assert projection["cards"][0]["source_index"] == 1
    assert diagnostics["archive_filler_cards_omitted"] == 1
    assert diagnostics["final_live_hero_from_source_pool"] is False


def test_shadow_alignment_uses_same_final_recovery_hero_when_shadow_is_suppressed(monkeypatch):
    from scripts import generate

    packet = _shadow_packet()
    raw_shadow = _sample_output("Shadow", 1, 2)
    final_baseline = {
        "hero": {
            "headline": "Shared deterministic archive recovery",
            "body": "Recovered final production body.",
            "_archive_only": True,
            "_archive_verified_quality": True,
        },
        "cards": [],
    }

    monkeypatch.setattr(generate, "_assignment_shadow_quality_guard", lambda data, packet: {})
    monkeypatch.setattr(generate, "_stamp_current_run_story_ids", lambda data, headlines: 0)

    def suppress_hero(data, archive, category_key=""):
        data["hero"] = None
        data["cards"] = []
        return [{"surface": "hero", "reason": "published_skip_placement_suppressed"}]

    monkeypatch.setattr(generate, "_suppress_published_skip_placements", suppress_hero)
    monkeypatch.setattr(
        generate,
        "enforce_live_county_membership_authority",
        lambda categories: {"assessed_placements": 0, "rejections": []},
    )
    monkeypatch.setattr(
        generate,
        "_assignment_shadow_apply_canonical_surface",
        lambda data, output_root: {"hero_rewritten": False, "card_duplicate_removals": 0, "card_canonical_rewrites": 0},
    )
    final_shadow, diagnostics = generate._assignment_shadow_final_projection(
        raw_shadow, packet, final_baseline, []
    )
    assert final_shadow["hero"]["headline"] == "Shared deterministic archive recovery"
    assert diagnostics["shared_archive_recovery_used"] is True
    assert diagnostics["published_story_suppressions"][0]["surface"] == "hero"

def test_update_workflow_exposes_separate_assignment_editor_shadow_checkbox_and_artifact():
    workflow = Path(".github/workflows/update.yml").read_text()
    assert "assignment_editor_shadow:" in workflow
    assert 'description: "Run Sonnet 5 assignment editor + Sonnet 4.5 writer shadow"' in workflow
    assert "TCT_ASSIGNMENT_EDITOR_SHADOW: ${{ inputs.assignment_editor_shadow }}" in workflow
    assert "Upload assignment editor shadow review" in workflow
    assert "data/assignment-editor-shadow-report.json" in workflow
    assert "data/assignment-editor-shadow-review.md" in workflow
    assert "data/assignment-editor-shadow-answer-key.json" in workflow
    assert "data/model-usage-report.json" in workflow


def test_model_usage_distinguishes_editor_and_writer_shadow_costs():
    assert _WORKLOAD_CLASS_BY_FUNCTION["_run_assignment_editor"] == "assignment_editor_shadow"
    assert _WORKLOAD_CLASS_BY_FUNCTION["_run_assignment_writer"] == "assignment_writer_shadow"


def test_assignment_writer_uses_live_lead_and_headline_integrity_standard(monkeypatch):
    from scripts import generate

    response = _Response(json.dumps({
        "headline": "Palm City update",
        "teaser": "A concise teaser.",
        "body": "Paragraph one with the assigned news.\n\nParagraph two with supporting detail.",
        "urgency_score": 8,
        "published": "Fri, 21 Aug 2026 20:00:00 -0400",
        "source_index": 1,
    }))
    fake = _FakeClient([response])
    monkeypatch.setattr(generate, "client", fake)

    generate._run_assignment_writer(
        _shadow_packet(),
        {"source_index": 1, "angle": "Lead with the surrender", "urgency_score": 8},
        role="card",
    )

    prompt = fake.messages.calls[0]["messages"][0]["content"]
    assert generate.LEAD_AND_HEADLINE_INTEGRITY_STANDARD in prompt
    assert "Every specific jurisdiction and monetary amount stated in the headline" in prompt
    assert "FIRST paragraph must explicitly state BOTH the original incident" in prompt
    assert "If it is `update`, treat the item as [story_form:update]" in prompt
    assert "if the lead cannot support that claim cleanly, remove it from the headline" in prompt


def test_exact_crime_shadow_fort_pierce_update_lead_accepts_killing_as_original_event_context():
    from scripts import generate

    # Exact wording from the final-pipeline-aligned Crime challenger that was
    # previously rejected as original_event_context_missing even though the lead
    # states both the shooting death and the new suspect identification.
    item = {
        "headline": "Fort Pierce police identify suspect in fatal shooting day after Fourth of July",
        "source_title": "Fort Pierce police identify suspect in deadly shooting after Fourth of July - WPEC",
        "story_form": "update",
        "article_text": (
            "Fort Pierce police identified Cornelius Trevon Ivory in the July 5 shooting. "
            "A 28-year-old man died after being shot on South 14th Street."
        ),
        "body": (
            "The Fort Pierce Police Department announced Friday that investigators identified "
            "Cornelius Trevon Ivory as the suspect accused of shooting and killing a 28-year-old "
            "man on South 14th Street the day after the Fourth of July. Investigators obtained a "
            "warrant charging Ivory in connection with the shooting. Ivory was served with the "
            "warrant while in custody at the St. Lucie County Jail, where he is being held on "
            "unrelated charges.\n\n"
            "The shooting occurred at about 3:43 a.m. on July 5. When officers arrived, they found "
            "two victims suffering from gunshot wounds."
        ),
    }

    diagnostics = generate._update_lead_diagnostics(item, item)

    assert diagnostics["required"] is True
    assert diagnostics["baseline_anchor"] == "fatality"
    assert diagnostics["baseline_anchor_present"] is True
    assert diagnostics["novelty_anchor"] == "identity"
    assert diagnostics["novelty_present"] is True
    assert diagnostics["passed"] is True
    assert diagnostics["missing"] == []


def test_exact_crime_shadow_22k_headline_requires_amount_in_first_paragraph():
    from scripts import generate

    item = {
        "headline": "Man accused of $22K gold chain grab at Treasure Coast Square Mall arrested, bonded out",
        "body": (
            "Dezmone Karlde' Rome Johnson, 25, of Lauderhill was arrested July 31 by Broward County "
            "Sheriff's Office with help from the U.S. Marshals Fugitive Task Force for the July 20 "
            "robbery at Royal Jewelers kiosk near the main entrance of Treasure Coast Square Mall "
            "in Jensen Beach. He recently bonded out of Broward County Jail on separate charges.\n\n"
            "Deputies say Johnson grabbed a display of nine gold chains. The stolen merchandise was "
            "worth more than $22,000."
        ),
    }

    diagnostics = generate._article_framing_diagnostics(item, item)

    assert diagnostics["passed"] is False
    assert diagnostics["claim_consistency"]["headline_money_claims"] == [22_000]
    assert diagnostics["claim_consistency"]["missing_money_claims"] == [22_000]
    assert "headline_money_claim_missing_from_lead" in diagnostics["missing"]

    repaired = dict(item)
    repaired["body"] = (
        "Dezmone Karlde' Rome Johnson, 25, of Lauderhill was arrested in connection with the July 20 "
        "robbery of more than $22,000 in gold chains from the Royal Jewelers kiosk at Treasure Coast "
        "Square Mall in Jensen Beach, according to the Martin County Sheriff's Office. He later "
        "bonded out on separate charges.\n\n"
        "Deputies say Johnson grabbed a display holding nine gold chains before running from the mall."
    )
    repaired_diagnostics = generate._article_framing_diagnostics(repaired, repaired)
    assert repaired_diagnostics["claim_consistency"]["passed"] is True
    assert repaired_diagnostics["claim_consistency"]["missing_money_claims"] == []
