"""Offline contracts for production-prompt shadow; never contact provider APIs."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tct_production_prompt_shadow", ROOT / "scripts/production_prompt_shadow.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _record(url, title, index=1):
    return {"source_url": url, "title": title, "published": "Thu, 03 Sep 2026 12:00:00 GMT",
            "source_type": "full_source", "source_quality": "full", "hero_eligible": "yes",
            "category_match_score": 10}


def test_preserves_live_source_indexes_and_requires_all_original_source_urls():
    url1 = "https://example.com/news/martin-county-one"
    url2 = "https://example.com/news/martin-county-two"
    report = {"categories": [{
        "category_key": "martin", "category_label": "Martin County",
        "source_pool": [_record(url1, "A"), _record(url2, "B")],
        "assignment_plan": {"hero": {"source_index": 2, "angle": "Lead verified changes",
                                     "urgency_score": 8}},
        "final_baseline_output": {"hero": {"source_index": 2}}
    }]}
    evidence = {
        MOD.urlkey(url1): {"evidence": "first archived evidence"},
        MOD.urlkey(url2): {"evidence": "second archived evidence"},
    }
    cases, checks = MOD.prepare_cases(report, evidence, limit=2)
    assert len(cases) == 1
    packet = cases[0]["packet"]
    assert [x["source_index"] for x in packet["source_inputs"]] == [1, 2]
    assert [x["article_text"] for x in packet["source_inputs"]] == [
        "first archived evidence", "second archived evidence"]
    assert cases[0]["fixed_writer_assignment"]["source_index"] == 2
    assert cases[0]["production_reference"]["hero_source_index"] == 2
    assert packet["source_inputs"][0]["canonical_context_body"] == ""
    missing, diagnostics = MOD.prepare_cases(report, {MOD.urlkey(url1): evidence[MOD.urlkey(url1)]}, limit=2)
    assert missing == []
    assert diagnostics[0]["ready"] is False
    assert diagnostics[0]["missing_source_urls"] == [url2]


def test_writer_and_editor_json_contracts_are_distinct():
    a = MOD.schema("editor", True)
    b = MOD.schema("editor", False)
    w = MOD.schema("writer", False)
    assert "category_fit" in a["required"]
    assert "category_fit" not in b["properties"]
    assert "body" in w["required"]
    assert a["additionalProperties"] is False


def test_blind_labels_consistent_and_different_for_two_providers():
    for name in ("martin", "st_lucie", "crime", "indian_river"):
        assert {MOD.blind_label(name, provider, 2) for provider in MOD.MODELS} == {"A", "B"}


def test_budget_initial_limit_requires_headroom():
    budget = MOD.Budget(1.0)
    budget.check()
    budget.estimated_usd = .81
    try:
        budget.check()
        assert False, "expected limit"
    except RuntimeError:
        pass


def test_gateway_preserves_model_facing_prompt_without_network():
    captured = {}
    class MockOpenAI:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(create=self.create)

        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_text='{"headline":"H","teaser":"T","body":"B","urgency_score":6}',
                usage=SimpleNamespace(input_tokens=1000, output_tokens=100),
                status="completed")

    adapter = MOD.Adapter("openai", MOD.Budget(2), False)
    adapter.mode = "writer"
    with patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=MockOpenAI)}):
        result = adapter.create(
            model="claude-sonnet-5", max_tokens=800,
            messages=[{"role": "user", "content": "REAL TCT WRITER PROMPT"}])
    assert captured["input"] == [{"role": "user", "content": "REAL TCT WRITER PROMPT"}]
    assert captured["text"]["format"]["strict"] is True
    assert "instructions" not in captured
    assert captured["model"] == "gpt-6.1-sol"
    assert result.model == "gpt-6.1-sol"
    assert adapter.budget.estimated_usd > 0
    assert len(adapter.budget.calls) == 1


def test_workflow_remains_manual_and_safely_gates_paid_shadow():
    workflow = (ROOT / ".github/workflows/historical-editorial-bakeoff.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "comparison_mode:" in workflow
    assert "production_prompt_shadow" in workflow
    assert "contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "scripts/generate.py" not in workflow
    assert "git push" not in workflow
    assert "scripts/production_prompt_shadow.py" in workflow
    assert "&& inputs.dry_run == false" in workflow
    assert "editorial-shadow-output/" in workflow
    assert "inputs.comparison_mode == 'historical' && inputs.dry_run == false" in workflow
    assert "inputs.comparison_mode == 'production_prompt_shadow' && inputs.dry_run == false" in workflow
    assert "Validate production-prompt shadow safety and response contracts" in workflow


def test_no_generator_entrypoint_in_shadow_runner():
    code = (ROOT / "scripts/production_prompt_shadow.py").read_text()
    assert "generate._run_assignment_editor(packet)" in code
    assert "generate._run_assignment_writer(" in code
    assert "generate.main(" not in code
    assert "archive.json" not in code



def test_actual_result_shape_generates_complete_blind_review_and_flags_failure():
    """Regression for paid run 40257576336: results rows have source_inputs, not packet."""
    rows = [
        {"category_key": "indian_river", "category_label": "Indian River County",
         "source_inputs": [{"source_index": 1, "title": "Frozen evidence",
                            "source_url": "https://example.com/real-original",
                            "published": "Thu, 03 Sep 2026 12:00:00 GMT",
                            "article_text": "Evidence first, no later additions."}],
         "fixed_writer_assignment": {"source_index": 1, "angle": "Lead verified facts"},
         "production_reference": {"hero_source_index": 1},
         "variants": {
             "A": {"status": "complete", "editor_plan": {"hero": {"source_index": 1}},
                   "writer_fixed_source": {"headline": "Draft A", "body": "Body A"}},
             "B": {"status": "complete", "editor_plan": {"hero": {"source_index": 1}},
                   "writer_fixed_source": {"headline": "Draft B", "body": "Body B"}},
         }},
        {"category_key": "st_lucie", "category_label": "St. Lucie County",
         "source_inputs": [],
         "fixed_writer_assignment": {"source_index": 1, "angle": "Local news"},
         "production_reference": {"hero_source_index": 1},
         "variants": {
             "A": {"status": "writer_failed", "editor_plan": {"hero": {"source_index": 1}},
                   "error": "CopyDeskIntegrityError: chained_and"},
             "B": {"status": "writer_failed", "editor_plan": {"hero": {"source_index": 1}},
                   "error": "CopyDeskIntegrityError: chained_and"},
         }},
    ]
    review = MOD.render_blind_review(rows)
    assert "Source #1: Frozen evidence" in review
    assert "Draft A" in review and "Draft B" in review
    assert "CopyDeskIntegrityError: chained_and" in review
    assert "No publishable writer result was returned" in review
    assert "A model's copy-desk validation failure" in review
    assert "provider" not in review.lower()
    summary = MOD.summarize_shadow_results(rows, {
        "estimated_usd": .128012, "calls": [{} for _ in range(10)]})
    assert summary["result"] == "partial"
    assert summary["complete_writing_and_editor_pairs"] == 1
    assert summary["complete_assignment_editor_pairs"] == 2
    assert summary["provider_api_calls"] == 10
    assert len(summary["failed_variants"]) == 2


def test_recover_existing_paid_artifact_never_calls_model(tmp_path):
    rows = [
        {"category_key": "indian_river", "category_label": "Indian River County",
         "source_inputs": [{"source_index": 1, "title": "Archived source",
                            "source_url": "https://example.com/news/evidence",
                            "article_text": "Original facts."}],
         "fixed_writer_assignment": {"source_index": 1},
         "production_reference": {"hero_source_index": 1},
         "variants": {key: {
             "status": "complete",
             "editor_plan": {"hero": {"source_index": 1}},
             "writer_fixed_source": {"headline": "Story", "body": "Text"}}
             for key in ("A", "B")}},
    ]
    (tmp_path / "results.json").write_text(json.dumps(rows))
    (tmp_path / "usage.json").write_text(json.dumps({
        "estimated_usd": 0.03, "calls": [{}, {}]}))
    before = (tmp_path / "results.json").read_bytes()
    summary = MOD.recover_existing_results(tmp_path)
    assert summary["result"] == "complete"
    assert summary["complete_writing_and_editor_pairs"] == 1
    assert (tmp_path / "results.json").read_bytes() == before
    review = (tmp_path / "blind-review.md").read_text()
    assert "Archived source" in review
    assert "Variant A" in review and "Variant B" in review
    assert "Story" in review
    assert json.loads((tmp_path / "summary.json").read_text()) == summary



def test_inspect_unpublished_writer_attempts_without_changing_guard():
    raw_initial = json.dumps({
        "headline": "Deputies investigate",
        "teaser": "Initial report",
        "body": "Detectives continue reviewing video and phones and search warrants.",
        "urgency_score": 7,
    })
    raw_repaired = json.dumps({
        "headline": "Deputies investigate",
        "teaser": "Revised report",
        "body": "Deputies reviewed footage and phones and searched vehicles.",
        "urgency_score": 7,
    })
    attempts = [
        {"mode": "editor", "sequence": 1,
         "raw_response": '{"hero":{"source_index":1}}'},
        {"mode": "writer", "sequence": 2, "raw_response": raw_initial,
         "prompt_sha256": "a1", "response_state": "end_turn"},
        {"mode": "writer", "sequence": 3, "raw_response": raw_repaired,
         "prompt_sha256": "a2", "response_state": "end_turn"},
    ]
    called = []
    def unchanged_detector(value):
        called.append(value)
        return [{"code": "chained_and", "snippet": value[:200]}] if (
            " and " in value and value.count(" and ") >= 2) else []
    evidence = MOD.copydesk_attempt_diagnostics(attempts, unchanged_detector)
    assert len(evidence) == 2
    assert [a["sequence"] for a in evidence] == [2, 3]
    assert evidence[0]["draft"]["body"] == json.loads(raw_initial)["body"]
    assert evidence[1]["draft"]["body"] == json.loads(raw_repaired)["body"]
    assert evidence[0]["copydesk_issues"][0]["code"] == "chained_and"
    assert evidence[0]["copydesk_issues"][0]["snippet"] == json.loads(raw_initial)["body"]
    assert evidence[1]["copydesk_issues"][0]["code"] == "chained_and"
    assert all(x["mode"] == "writer" for x in evidence)
    assert called
    # Detection annotates bad drafts; it never edits the original evidence.
    assert attempts[1]["raw_response"] == raw_initial
    assert attempts[2]["raw_response"] == raw_repaired


def test_raw_api_response_saved_even_when_json_parse_fails():
    class MockOpenAI:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(create=self.create)
        def create(self, **kwargs):
            return SimpleNamespace(
                output_text='{"headline":',
                usage=SimpleNamespace(input_tokens=321, output_tokens=19),
                status="completed")
    adapter = MOD.Adapter("openai", MOD.Budget(1), False)
    adapter.mode = "writer"
    with patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=MockOpenAI)}):
        try:
            adapter.create(messages=[{"role": "user", "content": "NEWSROOM INPUT"}])
            assert False, "expected JSON parsing to reject partial response"
        except json.JSONDecodeError:
            pass
    assert len(adapter.attempts) == 1
    assert adapter.attempts[0]["raw_response"] == '{"headline":'
    assert adapter.attempts[0]["input_tokens"] == 321
    assert adapter.budget.estimated_usd > 0


def test_paid_shadow_retains_assignment_when_both_copydesks_reject(tmp_path):
    from types import ModuleType
    fake = ModuleType("scripts.generate")
    fake.client = None
    calls = []
    def editor(packet):
        return {"hero": {"source_index": 1}, "cards": []}, {
            "source_mapping_valid": True}, "test-model", 0.01
    def writer(packet, assignment, role):
        calls.append(("writer", role))
        if packet["category_key"] == "st_lucie":
            fake.client.attempts.extend([
                {"mode": "writer", "sequence": 1,
                 "raw_response": json.dumps({"headline": "First rejected attempt",
                     "teaser": "One", "body": "Officers searched video and phones and cars."})},
                {"mode": "writer", "sequence": 2,
                 "raw_response": json.dumps({"headline": "Second rejected repair",
                     "teaser": "Two", "body": "Officers reviewed footage and phones and vehicles."})},
            ])
            raise ValueError("CopyDeskIntegrityError: chained_and")
        return {"headline": "Real output", "teaser": "Verified",
                "body": "Actual draft"}, "test-model", 0.01
    fake._run_assignment_editor = editor
    fake._run_assignment_writer = writer
    class FakeAdapter:
        def __init__(self, provider, budget, require_fit):
            self.mode = "editor"
            self.prompts = []
            self.attempts = []
    cases = [{
        "key": k, "label": k,
        "packet": {"category_key": k,
                   "source_inputs": [{"source_index": 1, "title": "Source",
                                     "source_url": "https://example.com/local/source",
                                     "article_text": "Evidence"}]},
        "fixed_writer_assignment": {"source_index": 1, "angle": "News"},
        "production_reference": {"hero_source_index": 1},
    } for k in ("indian_river", "st_lucie")]
    import scripts
    with patch.dict(sys.modules, {"scripts.generate": fake}):
        # In the full test suite, scripts.generate is already an attribute of
        # the imported scripts package. Patching sys.modules alone is insufficient.
        with patch.object(scripts, "generate", fake, create=True):
            with patch.object(MOD, "Adapter", FakeAdapter):
                MOD.produce(cases, 1.0, 1234, tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["result"] == "partial"
    assert summary["complete_writing_and_editor_pairs"] == 1
    assert summary["complete_assignment_editor_pairs"] == 2
    assert len(summary["failed_variants"]) == 2
    assert len(calls) == 4
    report = json.loads((tmp_path / "results.json").read_text())
    for v in report[1]["variants"].values():
        assert v["status"] == "writer_failed"
        assert v["editor_plan"]["hero"]["source_index"] == 1
    review = (tmp_path / "blind-review.md").read_text()
    assert "CopyDeskIntegrityError: chained_and" in review
    assert "Original source evidence" in review
    assert "First rejected attempt" in review
    assert "Second rejected repair" in review
    assert "Unpublished writer attempts" in review
    for v in report[1]["variants"].values():
        assert len(v["writer_attempts"]) == 2
        assert v["rejected_writer_attempts_captured"] is True
