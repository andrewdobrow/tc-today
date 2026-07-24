from pathlib import Path


def test_production_workflow_exposes_activation_controls():
    text = Path(".github/workflows/update.yml").read_text(encoding="utf-8")
    assert "TCT_ENGINE_MODE" in text
    assert "TCT_ENGINE_MAX_ACTIONS" in text
    assert "TCT_ENGINE_KILL_SWITCH" in text
    assert "vars.TCT_ENGINE_MODE || 'shadow'" in text


def test_editorial_ci_runs_when_production_workflow_changes():
    text = Path(".github/workflows/test-editorial-engine.yml").read_text(encoding="utf-8")
    assert '".github/workflows/update.yml"' in text
