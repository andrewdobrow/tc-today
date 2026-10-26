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
    assert "REAL TCT WRITER PROMPT" in captured["input"]
    assert captured["text"]["format"]["strict"] is True
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

