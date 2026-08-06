from pathlib import Path


def test_current_release_metadata_is_synchronized():
    import tct_engine.observability as observability

    assert observability.ENGINE_VERSION == "1.13.1.3"
    assert observability.ENGINE_RELEASE == "ascii-permalink-integrity"
    assert observability.OBSERVABILITY_SCHEMA_VERSION == 43


def test_current_release_artifacts_are_present():
    root = Path(__file__).resolve().parents[1]
    assert (root / "PATCH_NOTES_v1.13.1.3.md").exists()
    assert (root / "ASCII_PERMALINK_INTEGRITY_REVIEW_GUIDE_v1.13.1.3.md").exists()
