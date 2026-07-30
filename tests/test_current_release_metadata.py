from pathlib import Path


def test_current_release_metadata_is_synchronized():
    import tct_engine.observability as observability

    assert observability.ENGINE_VERSION == "1.11.9.1"
    assert observability.ENGINE_RELEASE == "persistent-incident-anchor-dedup"
    assert observability.OBSERVABILITY_SCHEMA_VERSION == 17


def test_current_release_artifacts_are_present():
    root = Path(__file__).resolve().parents[1]
    assert (root / "PATCH_NOTES_v1.11.9.1.md").exists()
    assert (root / "PERSISTENT_INCIDENT_ANCHOR_REVIEW_GUIDE_v1.11.9.1.md").exists()
