import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SLUG = (
    "2026-07-29-martin-county-commissioners-move-to-rewrite-shark-fishing-"
    "rules-after-public-bea"
)
INVALID_SHARK_VIDEO_URL = (
    "https://www.wpbf.com/article/florida-sharks-caught-on-video-off-shore"
    "martin-county-jupiter/73324831"
)
VALID_WPTV_UPDATE_URL = (
    "https://www.wptv.com/news/treasure-coast/region-martin-county/"
    "martin-county-considers-changes-to-shark-fishing-rules-on-beaches-"
    "after-state-directive"
)


def _archive_row():
    archive = json.loads((ROOT / "archive.json").read_text(encoding="utf-8"))
    return next(row for row in archive if row.get("slug") == CANONICAL_SLUG)


def test_canonical_shark_policy_archive_provenance_is_clean():
    row = _archive_row()

    assert row["category_keys"] == ["local_gov", "martin"]
    assert row["county_keys"] == ["martin"]
    assert row["editorial_event_key"] == "unknown-event-ceefb9fd4f"
    assert row["latest_source_url"] == VALID_WPTV_UPDATE_URL
    assert "incident_anchor_key" not in row

    history_urls = [entry.get("source_url") for entry in row["source_history"]]
    assert INVALID_SHARK_VIDEO_URL not in history_urls
    assert VALID_WPTV_UPDATE_URL in history_urls
    assert len(history_urls) == 2

    novel_facts = " ".join(row.get("semantic_material_update_novel_facts") or [])
    assert "Normandy Beach" not in novel_facts
    assert "hammerhead" not in novel_facts.lower()
    assert "St. Lucie" not in novel_facts


def test_canonical_shark_policy_page_contains_only_policy_update_context():
    page = (
        ROOT / "articles" / f"{CANONICAL_SLUG}.html"
    ).read_text(encoding="utf-8")

    assert INVALID_SHARK_VIDEO_URL not in page
    assert "Normandy Beach" not in page
    assert "12-foot shark" not in page
    assert "hammerhead shark" not in page.lower()
    assert "Photo: WPTV" in page
    assert page.count('<div class="article-body">') == 1
    article_body = page.split('<div class="article-body">', 1)[1].split("</div>", 1)[0]
    assert article_body.count("<p>") == 3


def test_shark_sighting_story_remains_separate_in_registry():
    registry = json.loads(
        (ROOT / "data" / "editorial_story_registry.json").read_text(
            encoding="utf-8"
        )
    )

    policy_source = "https://www.wpbf.com/article/martin-county-florida-shark-fishing-beach-rules/73288368"
    sighting_source = "https://www.wpbf.com/article/florida-sharks-caught-on-video-off-shoremartin-county-jupiter/73324831"

    def story_for_source(source_url):
        matches = [
            (story_id, story)
            for story_id, story in registry["stories"].items()
            if any(
                str(entry.get("url") or entry.get("source") or "") == source_url
                for entry in story.get("timeline", ())
            )
        ]
        assert len(matches) == 1, (source_url, [story_id for story_id, _ in matches])
        return matches[0]

    policy_id, policy_story = story_for_source(policy_source)
    sighting_id, _ = story_for_source(sighting_source)
    assert policy_id != sighting_id
    assert all(
        "sharks caught on video" not in title.lower()
        for title in policy_story.get("titles", [])
    )


def test_generation_cache_has_no_shark_video_to_policy_rewrite():
    cache = json.loads(
        (ROOT / "data" / "generation-cache.json").read_text(encoding="utf-8")
    )

    for entry in cache.get("categories", {}).values():
        hero = (((entry or {}).get("value") or {}).get("data") or {}).get("hero") or {}
        source_url = str(hero.get("source_url") or hero.get("link") or "")
        if source_url != INVALID_SHARK_VIDEO_URL:
            continue
        generated_headline = str(hero.get("headline") or "").lower()
        assert "ordinance" not in generated_headline
        assert "commissioners" not in generated_headline
        assert "state order" not in generated_headline
        assert "state directive" not in generated_headline
