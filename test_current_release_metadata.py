from pathlib import Path


def test_current_release_metadata_is_synchronized():
    import tct_engine.observability as observability

    assert observability.ENGINE_VERSION == "1.13.6.1"
    assert observability.ENGINE_RELEASE == "follow-up-evidence-precision"
    assert observability.OBSERVABILITY_SCHEMA_VERSION == 44


def test_current_release_artifacts_are_present():
    root = Path(__file__).resolve().parents[1]
    assert (root / "PATCH_NOTES_v1.13.6.1.md").exists()
    assert (root / "FOLLOW_UP_EVIDENCE_PRECISION_REVIEW_GUIDE_v1.13.6.1.md").exists()
