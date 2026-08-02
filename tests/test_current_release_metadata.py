from pathlib import Path


def test_current_release_metadata_is_synchronized():
    import tct_engine.observability as observability

    assert observability.ENGINE_VERSION == "1.13.0.1"
    assert observability.ENGINE_RELEASE == "semantic-material-update-transaction-integrity"
    assert observability.OBSERVABILITY_SCHEMA_VERSION == 38


def test_current_release_artifacts_are_present():
    root = Path(__file__).resolve().parents[1]
    assert (root / "PATCH_NOTES_v1.13.0.1.md").exists()
    assert (
        root
        / "SEMANTIC_MATERIAL_UPDATE_TRANSACTION_INTEGRITY_REVIEW_GUIDE_v1.13.0.1.md"
    ).exists()
