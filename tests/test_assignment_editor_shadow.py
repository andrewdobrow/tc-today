import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
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


def test_three_way_blind_review_randomizes_production_sonnet_and_opus_without_model_leak(tmp_path):
    report_path = tmp_path / "report.json"
    review_path = tmp_path / "review.md"
    key_path = tmp_path / "key.json"
    results = [{
        "category_key": "st_lucie",
        "category_label": "St. Lucie County",
        "source_pool": [{"title": "First source"}, {"title": "Second source"}],
        "raw_baseline_output": _sample_output("PRODUCTION RAW", 1, 2),
        "final_baseline_output": _sample_output("PRODUCTION FINAL", 1, 2),
        "assignment_plan": {"hero": {"source_index": 2}},
        "assignment_diagnostics": {"source_mapping_valid": True},
        "raw_challenger_output": _sample_output("SONNET RAW", 2, 1),
        "final_challenger_output": _sample_output("SONNET FINAL", 2, 1),
        "challenger_error": "",
        "opus_assignment_plan": {"hero": {"source_index": 1}},
        "opus_assignment_diagnostics": {"source_mapping_valid": True},
        "raw_opus_challenger_output": _sample_output("OPUS RAW", 1, 2),
        "final_opus_challenger_output": _sample_output("OPUS FINAL", 1, 2),
        "opus_challenger_error": "",
        "alignment_diagnostics": {
            "production": {"aligned": True},
            "shadow": {"final_source_mapping": {"source_mapping_valid": True, "mismatches": []}},
            "opus_shadow": {"final_source_mapping": {"source_mapping_valid": True, "mismatches": []}},
        },
    }]

    report = write_assignment_editor_artifacts(
        results=results,
        report_path=report_path,
        review_path=review_path,
        answer_key_path=key_path,
        production_model="claude-sonnet-4-5-20250929",
        editor_model="claude-sonnet-5",
        opus_editor_model="claude-opus-5",
        writer_model="claude-sonnet-4-5",
        blind_salt="three-way-test",
        enabled=True,
    )

    review = review_path.read_text()
    assert "Variant A" in review and "Variant B" in review and "Variant C" in review
    assert "A / B / C / Tie" in review
    assert "claude-sonnet" not in review.lower()
    assert "claude-opus" not in review.lower()
    assert "PRODUCTION FINAL" in review
    assert "SONNET FINAL" in review
    assert "OPUS FINAL" in review
    assert "PRODUCTION RAW" not in review and "SONNET RAW" not in review and "OPUS RAW" not in review

    key = json.loads(key_path.read_text())
    entry = key["categories"]["st_lucie"]
    paths = {entry["variant_a_path"], entry["variant_b_path"], entry["variant_c_path"]}
    assert paths == {
        "current_production",
        "sonnet5_editor_sonnet45_writer",
        "opus5_editor_sonnet45_writer",
    }
    assert key["schema_version"] == 3
    assert report["schema_version"] == 4
    assert report["challenger_architectures"]["opus5_editor_sonnet45_writer"]["assignment_editor_model"] == "claude-opus-5"
    row = report["categories"][0]
    assert row["comparison_signals"]["opus_source_mapping_valid"] is True
    assert row["final_opus_challenger_output"]["hero"]["headline"] == "OPUS FINAL hero"


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


def test_writer_uses_concise_breaking_contract_for_fresh_short_verified_source(monkeypatch):
    from scripts import generate

    published = format_datetime(datetime.now(timezone.utc) - timedelta(hours=1))
    source_text = " ".join(
        [
            "Martin County Fire Rescue transported a 76-year-old man after a golf cart crash in Tropical Farms."
        ]
        * 7
    )
    packet = {
        "category_key": "martin",
        "category_label": "Martin County",
        "source_inputs": [
            {
                "source_index": 1,
                "title": "76-year-old man ejected after golf cart crashes into tractor",
                "published": published,
                "source_type": "full_source",
                "source_quality": "full",
                "hero_eligible": True,
                "category_match_score": 10,
                "story_form": "standard",
                "article_text": source_text,
                "canonical_context_headline": "",
                "canonical_context_body": "",
            }
        ],
    }
    # Keep the fixture inside the breaking-brief source ceiling.
    assert 80 <= generate._word_count(source_text) <= generate.BREAKING_BRIEF_MAX_SOURCE_WORDS

    response = _Response(json.dumps({
        "headline": "76-year-old man ejected after Martin County golf cart crash",
        "body": "Paragraph one with verified facts.\n\nParagraph two with verified facts.",
        "urgency_score": 6,
        "published": published,
        "source_index": 1,
    }))
    fake = _FakeClient([response])
    monkeypatch.setattr(generate, "client", fake)

    generate._run_assignment_writer(
        packet,
        {"source_index": 1, "angle": "Lead with the ejection and hospitalization", "urgency_score": 6},
        role="hero",
    )

    prompt = fake.messages.calls[0]["messages"][0]["content"]
    assert "fresh source-constrained breaking brief" in prompt
    assert "Cover it now rather than rejecting it for being short" in prompt
    assert "roughly 90-160 words in 2-3 short paragraphs" in prompt
    assert "do not add generic background" in prompt


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


def test_assignment_editor_accepts_explicit_opus_model_without_changing_prompt_contract(monkeypatch):
    from scripts import generate

    response = _Response(
        json.dumps({
            "hero": {"source_index": 2, "angle": "Lead with the collision impact", "urgency_score": 8},
            "cards": [{"source_index": 1, "angle": "Lead with the surrender", "urgency_score": 7}],
        }),
        model="claude-opus-5",
    )
    fake = _FakeClient([response])
    monkeypatch.setattr(generate, "client", fake)

    plan, diagnostics, actual_model, _duration = generate._run_assignment_editor(
        _shadow_packet(), model="claude-opus-5"
    )
    assert fake.messages.calls[0]["model"] == "claude-opus-5"
    prompt = fake.messages.calls[0]["messages"][0]["content"]
    assert "Your job is ONLY editorial assignment" in prompt
    assert [plan["hero"]["source_index"]] + [c["source_index"] for c in plan["cards"]] == [2, 1]
    assert diagnostics["source_mapping_valid"] is True
    assert actual_model == "claude-opus-5"


def test_generator_shadow_is_opt_in_post_build_and_cannot_publish():
    source = Path("scripts/generate.py").read_text()
    assert '"TCT_ASSIGNMENT_EDITOR_LIVE", "true"' in source
    assert 'not ASSIGNMENT_EDITOR_LIVE_ENABLED' in source
    assert 'os.environ.get("TCT_ASSIGNMENT_EDITOR_SHADOW", "false")' in source
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
    helper_start = source.index("def _run_assignment_editor_shadow_variant(")
    helper = source[helper_start:runner_start]
    assert '"raw_challenger_output": sonnet["raw_output"]' in runner
    assert '"raw_opus_challenger_output": opus["raw_output"]' in runner
    assert "ASSIGNMENT_EDITOR_OPUS_MODEL" in runner
    assert "_assignment_shadow_final_production_projection" in runner
    assert "_assignment_shadow_final_projection" in helper
    assert "all_categories.append" not in runner + helper
    assert "GENERATION_CACHE.put" not in runner + helper



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

def test_update_workflow_promotes_live_assignment_editor_and_retires_three_way_checkbox():
    workflow = Path(".github/workflows/update.yml").read_text()
    assert "assignment_editor_shadow:" not in workflow
    assert "TCT_ASSIGNMENT_EDITOR_SHADOW:" not in workflow
    assert "Upload assignment editor shadow review" not in workflow
    assert "TCT_ASSIGNMENT_EDITOR_LIVE: ${{ vars.TCT_ASSIGNMENT_EDITOR_LIVE || 'true' }}" in workflow


def test_model_usage_tracks_promoted_editor_and_writer_as_live_workloads():
    assert _WORKLOAD_CLASS_BY_FUNCTION["_run_assignment_editor"] == "assignment_editor"
    assert _WORKLOAD_CLASS_BY_FUNCTION["_run_assignment_writer"] == "assignment_writer"


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


def test_topic_category_fit_rejection_is_binding_before_assignment():
    plan, diagnostics = normalize_assignment_plan(
        {
            "category_fit": [
                {"source_index": 1, "fits_category": True, "reason": "Fits the section."},
                {"source_index": 2, "fits_category": False, "reason": "Wrong topic."},
            ],
            "hero": {"source_index": 2, "angle": "Should never survive", "urgency_score": 9},
            "cards": [
                {"source_index": 1, "angle": "Valid section story", "urgency_score": 7},
            ],
        },
        source_count=2,
        max_cards=1,
        require_category_fit=True,
    )
    assert plan["hero"] == {}
    assert [card["source_index"] for card in plan["cards"]] == [1]
    assert diagnostics["category_fit_required"] is True
    assert diagnostics["category_fit_complete"] is True
    assert diagnostics["category_fit_accepted_source_indexes"] == [1]
    assert diagnostics["category_fit_rejected_source_indexes"] == [2]
    assert diagnostics["category_fit_selected_rejections"] == [2]
    assert diagnostics["source_mapping_valid"] is False


def test_topic_assignment_editor_adjudicates_tornado_out_of_crime_without_exclusion_list(monkeypatch):
    from scripts import generate

    packet = _shadow_packet()
    packet["category_key"] = "crime"
    packet["category_label"] = "Crime & Safety"
    packet["source_inputs"][0]["title"] = "BB gun shooting turns deadly: Fort Pierce man killed, suspect charged"
    packet["source_inputs"][0]["article_text"] = "A Fort Pierce man died and a suspect was charged with manslaughter."
    packet["source_inputs"][1]["title"] = "National Weather Service confirms EF0 tornado touchdown in Port St. Lucie"
    packet["source_inputs"][1]["article_text"] = "The National Weather Service confirmed an EF0 tornado damaged homes."

    response = _Response(
        json.dumps({
            "category_fit": [
                {"source_index": 1, "fits_category": True, "reason": "The central subject is a fatal shooting and manslaughter charge."},
                {"source_index": 2, "fits_category": False, "reason": "The central subject does not belong in Crime & Safety."},
            ],
            "hero": {"source_index": 1, "angle": "Lead with the manslaughter charge", "urgency_score": 9},
            "cards": [],
        }),
        model="claude-sonnet-5",
    )
    fake = _FakeClient([response])
    monkeypatch.setattr(generate, "client", fake)

    plan, diagnostics, actual_model, _duration = generate._run_assignment_editor(packet)
    prompt = fake.messages.calls[0]["messages"][0]["content"]

    assert "independently judge whether EACH numbered source genuinely belongs" in prompt
    assert "Do not assume upstream routing is correct" in prompt
    assert "Only sources you mark fits_category:true may be assigned" in prompt
    # The contract asks for editorial judgment rather than encoding a weather-specific exclusion rule.
    assert "exclude weather" not in prompt.lower()
    assert "do not use weather" not in prompt.lower()
    assert plan["hero"]["source_index"] == 1
    assert plan["cards"] == []
    assert diagnostics["category_fit_rejected_source_indexes"] == [2]
    assert diagnostics["category_fit_selected_rejections"] == []
    assert diagnostics["source_mapping_valid"] is True
    assert actual_model == "claude-sonnet-5"


def test_topic_assignment_editor_fails_closed_if_it_selects_a_source_it_rejected(monkeypatch):
    from scripts import generate

    packet = _shadow_packet()
    packet["category_key"] = "crime"
    packet["category_label"] = "Crime & Safety"
    response = _Response(json.dumps({
        "category_fit": [
            {"source_index": 1, "fits_category": True, "reason": "Fits."},
            {"source_index": 2, "fits_category": False, "reason": "Does not fit."},
        ],
        "hero": {"source_index": 2, "angle": "Invalid rejected assignment", "urgency_score": 8},
        "cards": [],
    }), model="claude-sonnet-5")
    fake = _FakeClient([response])
    monkeypatch.setattr(generate, "client", fake)

    with pytest.raises(ValueError, match="selected source\\(s\\) it did not accept for category fit"):
        generate._run_assignment_editor(packet)


def test_county_assignment_editor_does_not_require_topic_fit_and_tornado_can_be_selected(monkeypatch):
    from scripts import generate

    packet = _shadow_packet()
    packet["category_key"] = "st_lucie"
    packet["category_label"] = "St. Lucie County"
    packet["source_inputs"][1]["title"] = "National Weather Service confirms EF0 tornado touchdown in Port St. Lucie"
    packet["source_inputs"][1]["article_text"] = "The National Weather Service confirmed an EF0 tornado in Port St. Lucie."

    response = _Response(json.dumps({
        "hero": {"source_index": 2, "angle": "Lead with the confirmed tornado damage", "urgency_score": 8},
        "cards": [{"source_index": 1, "angle": "Supporting county story", "urgency_score": 6}],
    }), model="claude-sonnet-5")
    fake = _FakeClient([response])
    monkeypatch.setattr(generate, "client", fake)

    plan, diagnostics, _actual_model, _duration = generate._run_assignment_editor(packet)
    prompt = fake.messages.calls[0]["messages"][0]["content"]

    assert "independently judge whether EACH numbered source genuinely belongs" not in prompt
    assert "category_fit" not in prompt
    assert plan["hero"]["source_index"] == 2
    assert diagnostics["category_fit_required"] is False
    assert diagnostics["source_mapping_valid"] is True


def test_fresh_current_day_confirmation_of_yesterdays_event_is_not_stale():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime
    from scripts import generate

    now = datetime.now(timezone.utc)
    today = now.strftime("%A")
    yesterday = (now - timedelta(days=1)).strftime("%A")
    item = {
        "headline": "National Weather Service confirms EF0 tornado damage in Port St. Lucie",
        "teaser": f"The National Weather Service confirmed {today} that an EF0 tornado touched down {yesterday} evening.",
        "body": (
            f"The National Weather Service confirmed {today} morning that an EF0 tornado with peak winds "
            f"of 75 mph touched down in Port St. Lucie {yesterday} evening after completing a damage survey."
        ),
    }
    published = format_datetime(now - timedelta(hours=2))

    assert generate._category_story_is_stale(item, [], published, now=now) is False


def test_recent_feed_retouch_does_not_make_old_event_fresh_without_current_day_development():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime
    from scripts import generate

    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).strftime("%A")
    source_url = "https://www.wptv.com/news/local/old-birthday-party-assault"
    item = {
        "headline": "Vero Beach man arrested on attempted murder charge after birthday party assault",
        "teaser": f"Deputies said the assault happened {yesterday} at a birthday party.",
        "body": (
            f"Investigators said the assault occurred {yesterday}. The suspect was arrested after the incident. "
            "The article contains no new current-day development."
        ),
        "source_url": source_url,
    }
    # A fresh feed timestamp is a proven retouch only because this exact publisher URL
    # already has an older archive receipt.
    published = format_datetime(now - timedelta(hours=2))
    archive = [{
        "headline": item["headline"],
        "source_url": source_url,
        "first_published": (now - timedelta(days=3)).isoformat(),
    }]

    assert generate._category_story_is_stale(item, archive, published, now=now) is True


def test_exact_st_lucie_shadow_keeps_fresh_tornado_hero_instead_of_swapping_to_city_attorney():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime
    from scripts import generate

    now = datetime.now(timezone.utc)
    today = now.strftime("%A")
    yesterday = (now - timedelta(days=1)).strftime("%A")
    packet = {
        "category_key": "st_lucie",
        "category_label": "St. Lucie County",
        "source_inputs": [
            {
                "source_index": 1,
                "title": "GALLERY: EF-0 tornado carrying peak winds of 75 mph touches down in Port St. Lucie - WPEC",
                "published": format_datetime(now - timedelta(hours=2)),
                "source_type": "full_source",
                "source_quality": "full",
                "hero_eligible": True,
                "category_match_score": 10,
                "article_text": "Fresh NWS confirmation and damage survey.",
            },
            {
                "source_index": 2,
                "title": "Fort Pierce city meeting gets heated amid search for new city attorney",
                "published": format_datetime(now - timedelta(hours=3)),
                "source_type": "full_source",
                "source_quality": "full",
                "hero_eligible": True,
                "category_match_score": 10,
                "article_text": "Fresh city attorney resignation story.",
            },
        ],
    }
    data = {
        "hero": {
            "headline": "EF0 tornado with 75 mph winds damages Port St. Lucie Southbend neighborhood",
            "teaser": f"The National Weather Service confirmed {today} that the tornado touched down {yesterday} evening.",
            "body": (
                f"The National Weather Service confirmed {today} morning that an EF0 tornado touched down in "
                f"Port St. Lucie {yesterday} evening after a damage survey. No injuries were reported."
            ),
            "source_index": 1,
            "urgency_score": 8,
        },
        "cards": [
            {
                "headline": "Fort Pierce left without city attorneys after nearly entire legal team resigns",
                "teaser": f"Fort Pierce commissioners met {today} after nearly the entire legal team resigned.",
                "body": "The city approved an outside attorney search.",
                "source_index": 2,
                "urgency_score": 7,
            }
        ],
    }

    swap = generate._assignment_shadow_apply_stale_hero_swap(data, packet, [])

    assert swap is None
    assert data["hero"]["source_index"] == 1
    assert "tornado" in data["hero"]["headline"].lower()



def test_shadow_terminal_alignment_cannot_publish_a_source_live_terminal_authority_held(monkeypatch):
    from scripts import generate

    source_url = "https://example.com/byron-donalds-running-mate"
    packet = {
        "category_key": "florida",
        "category_label": "Florida",
        "source_inputs": [{
            "source_index": 1,
            "title": "Byron Donalds selects Miami-Dade Sen. Bryan Avila as running mate",
            "source_url": source_url,
            "link": source_url,
        }],
    }
    data = {
        "hero": {
            "headline": "Byron Donalds selects Bryan Avila as running mate",
            "source_index": 1,
        },
        "cards": [],
    }
    normalized = generate._normalized_external_source_url(source_url) or source_url
    monkeypatch.setitem(generate.SEMANTIC_PUBLICATION_SOURCE_OUTCOMES, normalized, {
        "authority_stage": "terminal_permalink_authority",
        "action": generate.SEMANTIC_ACTION_HOLD,
        "status": "validated",
        "selected_candidate_slug": "",
    })

    diagnostics = generate._assignment_shadow_apply_terminal_publication_authority(data, packet)

    assert data["hero"] is None
    assert diagnostics == [{
        "role": "hero",
        "source_index": 1,
        "headline": "Byron Donalds selects Bryan Avila as running mate",
        "action": generate.SEMANTIC_ACTION_HOLD,
        "selected_candidate_slug": "",
        "result": "dropped_terminal_hold",
    }]


def test_corgi_shadow_blocks_contaminated_story_id_rewrite_to_unrelated_orbeez_canonical(monkeypatch, tmp_path):
    """Regression from 2026-08-27 St. Lucie shadow: corgi source #2 -> Orbeez canonical."""
    import copy
    from scripts import generate

    corgi_url = "https://www.wpbf.com/article/corgi-reunited-tornado-port-st-lucie-florida/73542668"
    orbeez_url = "https://cbs12.com/news/local/florida-crime-news-citizens-arrest-charges-dropped-against-man-who-held-teens-at-gunpoint-orbeez-prank-port-st-lucie-felony-state-attorney"
    orbeez_slug = "2026-06-27-port-st-lucie-man-arrested-after-holding-teens-at-gunpoint-during-orbeez-prank"
    archive = [{
        "slug": orbeez_slug,
        "headline": "Charges dropped against Port St. Lucie man who held teens at gunpoint after Orbeez shooting",
        "body": "Prosecutors dropped six felony charges after the Orbeez incident.",
        "source_url": orbeez_url,
        "editorial_story_id": "story_002646",
        "date": "2026-06-27",
        "lastmod": "2026-07-31",
    }]
    context = {
        "archive_by_slug": {orbeez_slug: archive[0]},
        "redirect_map": {},
        "safe_story_ids": {"story_002646"},
        "story_canonical_slugs": {"story_002646": orbeez_slug},
        "custom_event_canonical_slugs": {},
        "incident_anchor_canonical_slugs": {},
    }
    monkeypatch.setattr(generate, "load_archive", lambda _path: copy.deepcopy(archive))
    monkeypatch.setattr(
        generate,
        "_build_final_canonical_surface_context",
        lambda _archive, _root: context,
    )
    monkeypatch.setattr(generate, "_durable_incident_anchor", lambda *_a, **_k: "")

    packet = {
        "category_key": "st_lucie",
        "category_label": "St. Lucie County",
        "source_inputs": [
            {"source_index": 1, "title": "Other story", "source_url": "https://example.com/other"},
            {
                "source_index": 2,
                "title": "Corgi reunited with owner after tornado in Port St. Lucie - WPBF",
                "source_url": corgi_url,
                "link": corgi_url,
            },
        ],
    }
    card = {
        "headline": "Corgi swept away in Port St. Lucie tornado reunited with owner in Bay St. Lucie",
        "body": "Luna was found three streets away and reunited with her owner.",
        "teaser": "A 6-year-old corgi was reunited with her owner after the EF0 tornado.",
        "published": "Thu, 27 Aug 2026 16:53:00 GMT",
        "source_index": 2,
        "_assignment_source_index": 2,
        "_assignment_source_url": corgi_url,
        "_assignment_source_title": packet["source_inputs"][1]["title"],
        "source_url": corgi_url,
        "source_title": packet["source_inputs"][1]["title"],
        "link": corgi_url,
        # Reproduce the contaminated persistent identity that previously authorized
        # final canonical copy adoption into the unrelated Orbeez archive story.
        "editorial_story_id": "story_002646",
        "_editorial_story_id": "story_002646",
    }
    data = {"hero": None, "cards": [card]}

    probe = generate._final_canonical_surface_identity(
        copy.deepcopy(card), corgi_url, context
    )
    assert probe["identity_basis"] == "persistent_story_id"
    assert probe["canonical_slug"] == orbeez_slug

    diagnostics = generate._assignment_shadow_apply_canonical_surface(data, tmp_path)

    assert diagnostics["blocked_source_integrity_rewrite_count"] == 1
    assert diagnostics["card_canonical_rewrites"] == 0
    assert diagnostics["blocked_source_integrity_rewrites"][0]["source_index"] == 2
    assert diagnostics["blocked_source_integrity_rewrites"][0]["canonical_slug"] == orbeez_slug
    assert data["cards"][0]["headline"].startswith("Corgi swept away")
    assert data["cards"][0]["source_url"] == corgi_url
    assert "Orbeez" not in data["cards"][0]["headline"]

    final_mapping = generate._assignment_shadow_final_source_mapping(data, packet)
    assert final_mapping["source_mapping_valid"] is True
    assert final_mapping["mismatches"] == []


def test_shadow_canonical_surface_allows_exact_assigned_source_provenance(monkeypatch, tmp_path):
    from scripts import generate

    source_url = "https://www.wpec.com/local/current-story"
    slug = "2026-08-27-current-story"
    archive = [{
        "slug": slug,
        "headline": "Canonical current story headline",
        "body": "Canonical current story body.",
        "source_url": source_url,
        "editorial_story_id": "story_current",
        "date": "2026-08-27",
    }]
    context = {
        "archive_by_slug": {slug: archive[0]},
        "redirect_map": {},
        "safe_story_ids": {"story_current"},
        "story_canonical_slugs": {"story_current": slug},
        "custom_event_canonical_slugs": {},
        "incident_anchor_canonical_slugs": {},
    }
    monkeypatch.setattr(generate, "load_archive", lambda _path: archive)
    monkeypatch.setattr(generate, "_build_final_canonical_surface_context", lambda _a, _r: context)
    monkeypatch.setattr(generate, "_durable_incident_anchor", lambda *_a, **_k: "")

    data = {"hero": {
        "headline": "Draft current story headline",
        "body": "Draft body.",
        "source_index": 1,
        "_assignment_source_index": 1,
        "_assignment_source_url": source_url,
        "source_url": source_url,
        "link": source_url,
        "editorial_story_id": "story_current",
        "_editorial_story_id": "story_current",
    }, "cards": []}

    diagnostics = generate._assignment_shadow_apply_canonical_surface(data, tmp_path)

    assert diagnostics["hero_rewritten"] is True
    assert diagnostics["blocked_source_integrity_rewrite_count"] == 0
    assert data["hero"]["headline"] == "Canonical current story headline"
    assert data["hero"]["source_url"] == source_url
    assert data["hero"]["_assignment_source_url"] == source_url


def test_final_shadow_source_mapping_rejects_unrelated_story_even_when_source_index_survives():
    from scripts import generate

    corgi_url = "https://www.wpbf.com/article/corgi-reunited-tornado-port-st-lucie-florida/73542668"
    orbeez_url = "https://cbs12.com/news/local/orbeez-charges-dropped"
    packet = {
        "source_inputs": [
            {"source_index": 1, "title": "Other", "source_url": "https://example.com/other"},
            {"source_index": 2, "title": "Corgi reunited with owner after tornado", "source_url": corgi_url},
        ]
    }
    corrupted = {
        "hero": None,
        "cards": [{
            "headline": "Charges dropped against Port St. Lucie man after Orbeez shooting",
            "source_index": 2,
            "_assignment_source_index": 2,
            "_assignment_source_url": corgi_url,
            "source_url": orbeez_url,
            "link": "/articles/2026-06-27-orbeez.html",
            "_archived_slug": "2026-06-27-orbeez",
        }],
    }

    diagnostics = generate._assignment_shadow_final_source_mapping(corrupted, packet)

    assert diagnostics["source_mapping_valid"] is False
    assert diagnostics["selected_source_indexes"] == [2]
    assert diagnostics["mismatches"][0]["reason"] == "final_story_no_longer_matches_assigned_source"
    assert diagnostics["mismatches"][0]["expected_source_url"] == corgi_url


def test_shadow_artifact_reports_final_mapping_validity_not_only_assignment_plan(tmp_path):
    report_path = tmp_path / "report.json"
    review_path = tmp_path / "review.md"
    key_path = tmp_path / "key.json"
    results = [{
        "category_key": "st_lucie",
        "category_label": "St. Lucie County",
        "source_pool": [{"title": "Corgi story"}],
        "raw_baseline_output": _sample_output("BASE", 1, 1),
        "final_baseline_output": _sample_output("BASE", 1, 1),
        "assignment_plan": {"hero": {"source_index": 1}},
        "assignment_diagnostics": {"source_mapping_valid": True},
        "raw_challenger_output": _sample_output("SHADOW", 1, 1),
        "final_challenger_output": _sample_output("SHADOW", 1, 1),
        "alignment_diagnostics": {
            "shadow": {
                "final_source_mapping": {
                    "source_mapping_valid": False,
                    "mismatches": [{"source_index": 1, "reason": "different_story"}],
                }
            }
        },
        "challenger_error": "FinalSourceMappingError: failed closed",
    }]

    report = write_assignment_editor_artifacts(
        results=results,
        report_path=report_path,
        review_path=review_path,
        answer_key_path=key_path,
        production_model="claude-sonnet-4-5-20250929",
        editor_model="claude-sonnet-5",
        writer_model="claude-sonnet-4-5",
        blind_salt="source-integrity-regression",
        enabled=True,
    )

    row = report["categories"][0]
    assert report["schema_version"] == 4
    assert report["failed_categories"] == 1
    assert row["comparison_signals"]["challenger_source_mapping_valid"] is False
    assert row["comparison_signals"]["challenger_final_source_mapping"]["mismatches"][0]["source_index"] == 1
    assert "not scoreable" in review_path.read_text().lower()


def test_promoted_live_path_runs_sonnet5_editor_then_sonnet45_single_source_writers(monkeypatch):
    from scripts import generate

    editor = _Response(
        json.dumps({
            "hero": {"source_index": 2, "angle": "Lead with the collision impact", "urgency_score": 8},
            "cards": [{"source_index": 1, "angle": "Lead with the surrender", "urgency_score": 7}],
        }),
        model="claude-sonnet-5",
    )
    hero_writer = _Response(
        json.dumps({
            "headline": "Hobe Sound collision update",
            "body": "Paragraph one about the Hobe Sound collision.\n\nParagraph two.\n\nParagraph three.\n\nParagraph four.",
            "urgency_score": 999,
            "published": "wrong",
            "source_index": 999,
        })
    )
    card_writer = _Response(
        json.dumps({
            "headline": "Palm City surrender update",
            "teaser": "A concise Palm City teaser.",
            "body": "Paragraph one about the Palm City surrender.\n\nParagraph two.",
            "urgency_score": 999,
            "published": "wrong",
            "source_index": 999,
        })
    )
    fake = _FakeClient([editor, hero_writer, card_writer])
    monkeypatch.setattr(generate, "client", fake)

    headlines = []
    for row in _shadow_packet()["source_inputs"]:
        source = dict(row)
        source.update({
            "summary": row["article_text"],
            "link": f"https://example.com/source-{row['source_index']}",
            "source_url": f"https://example.com/source-{row['source_index']}",
            "image_url": "",
            "feed_url": "https://example.com/rss",
        })
        headlines.append(source)

    data = generate._run_live_assignment_editor_category(
        "martin", "Martin County", headlines, timeout_seconds=120
    )

    assert len(fake.messages.calls) == 3
    assert fake.messages.calls[0]["model"] == "claude-sonnet-5"
    assert fake.messages.calls[1]["model"] == generate.MODEL_ARTICLES
    assert fake.messages.calls[2]["model"] == generate.MODEL_ARTICLES
    assert "Your job is ONLY editorial assignment" in fake.messages.calls[0]["messages"][0]["content"]
    assert "UNIQUE_SOURCE_TWO_FACTS" in fake.messages.calls[1]["messages"][0]["content"]
    assert "UNIQUE_SOURCE_ONE_FACTS" not in fake.messages.calls[1]["messages"][0]["content"]
    assert "UNIQUE_SOURCE_ONE_FACTS" in fake.messages.calls[2]["messages"][0]["content"]
    assert "UNIQUE_SOURCE_TWO_FACTS" not in fake.messages.calls[2]["messages"][0]["content"]
    assert data["hero"]["source_index"] == 2
    assert data["hero"]["urgency_score"] == 8
    assert data["cards"][0]["source_index"] == 1
    assert data["cards"][0]["urgency_score"] == 7


def test_promoted_live_architecture_is_default_and_disables_three_way_shadow():
    from scripts import generate

    assert generate.ASSIGNMENT_EDITOR_LIVE_ENABLED is True
    assert generate.ASSIGNMENT_EDITOR_MODEL == "claude-sonnet-5"
    assert generate.MODEL_ARTICLES == "claude-sonnet-4-5"
    assert generate.ASSIGNMENT_EDITOR_SHADOW_ENABLED is False
