from pathlib import Path


def test_generator_does_not_run_full_registry_repair_after_generation():
    """Emergency performance guard: fixed-point repair belongs to workflow preflight.

    Running the registry normalizer after the generator has completed can require
    repeated production-sized repair passes and make runtime effectively unbounded.
    Snapshot reuse must never add a second full-registry normalization stage here.
    """
    root = Path(__file__).resolve().parents[1]
    generator = (root / "scripts" / "generate.py").read_text(encoding="utf-8")
    assert "_stabilize_editorial_registry_before_snapshot" not in generator
    assert "stabilize_registry_for_snapshot" not in generator


def test_registry_preflight_keeps_bounded_fixed_point_normalization():
    root = Path(__file__).resolve().parents[1]
    preflight = (root / "scripts" / "repair_editorial_story_registry.py").read_text(
        encoding="utf-8"
    )
    assert "max_passes = 16" in preflight
    assert "repair_registry_payload(payload)" in preflight
    assert "if not report.changed" in preflight


def test_production_workflow_runs_registry_preflight_before_tests_and_generator():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "update.yml").read_text(
        encoding="utf-8"
    )
    preflight_at = workflow.index("Normalize persistent story registry")
    pytest_at = workflow.index("python -m pytest tests -v")
    generate_at = workflow.index("python -u scripts/generate.py")
    assert preflight_at < pytest_at < generate_at
