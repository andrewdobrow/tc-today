from pathlib import Path


def test_current_release_metadata_is_synchronized():
    import tct_engine.observability as observability

    assert observability.ENGINE_VERSION == "1.12.2.7"
    assert observability.ENGINE_RELEASE == "rss-social-image-authority"
    assert observability.OBSERVABILITY_SCHEMA_VERSION == 34


def test_current_release_artifacts_are_present():
    root = Path(__file__).resolve().parents[1]
    assert (root / "PATCH_NOTES_v1.12.2.7.md").exists()
    assert (
        root
        / "RSS_SOCIAL_IMAGE_AUTHORITY_REVIEW_GUIDE_v1.12.2.7.md"
    ).exists()
