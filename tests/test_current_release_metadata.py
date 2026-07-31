from pathlib import Path


def test_current_release_metadata_is_synchronized():
    import tct_engine.observability as observability

    assert observability.ENGINE_VERSION == "1.12.0.6.1"
    assert observability.ENGINE_RELEASE == "cross-source-update-identity-performance-hotfix"
    assert observability.OBSERVABILITY_SCHEMA_VERSION == 20


def test_current_release_artifacts_are_present():
    root = Path(__file__).resolve().parents[1]
    assert (root / "PATCH_NOTES_v1.12.0.6.1.md").exists()
    assert (
        root
        / "CROSS_SOURCE_UPDATE_IDENTITY_HOTFIX_REVIEW_GUIDE_v1.12.0.6.1.md"
    ).exists()
