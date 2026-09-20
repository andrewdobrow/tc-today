import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBSCRIBE_PAGE = ROOT / "subscribe.html"
PARTNER_PAGE = ROOT / "partners" / "treasure-coast-community-news.html"
GENERATOR = ROOT / "scripts" / "generate.py"


def _showcase_script(page: Path) -> str:
    text = page.read_text()
    start = text.index("const container = document.querySelector('[data-membership-top-stories]')")
    end = text.index("</script>", start)
    return text[start:end]


def test_subscription_showcases_consume_exact_top_stories_ranking_artifact():
    for page in (SUBSCRIBE_PAGE, PARTNER_PAGE):
        script = _showcase_script(page)
        assert "fetch('/data/top-stories-ranking-report.json', {cache:'no-store'})" in script
        assert "fetch('/archive.json', {cache:'no-store'})" in script
        assert "ranking.selected) ? ranking.selected.slice(0, 4) : []" in script
        assert "const slug = story.slug;" in script
        assert "MAX_RECENT_STORY_AGE_MS" not in script
        assert "storyPublishedAt" not in script
        assert ".sort((a, b)" not in script
        assert "front_page" not in script
        assert "fetch('/data.json'" not in script


def test_top_stories_ranking_artifact_is_the_final_homepage_top_stories_authority():
    source = GENERATOR.read_text()
    assert "topnews, _top_stories_report = _select_top_story_cards(" in source
    assert "_write_top_stories_ranking_report(_top_stories_report, OUTPUT_DIR)" in source
    assert "topnews_attr = ' data-topnews=\"true\"' if id(card) in topnews_ids else \"\"" in source


def test_subscription_showcases_use_archive_only_to_enrich_ranked_slugs():
    for page in (SUBSCRIBE_PAGE, PARTNER_PAGE):
        script = _showcase_script(page)
        assert "const archiveBySlug = new Map();" in script
        assert "const archived = archiveBySlug.get(story.slug) || {};" in script
        assert "return Object.assign({}, archived, story" in script
        assert "categoryLabels[story.category_key]" in script
        assert "unique.forEach((story, index) =>" in script


def test_normal_and_partner_pages_share_the_same_top_stories_algorithm():
    normal = _showcase_script(SUBSCRIBE_PAGE)
    partner = _showcase_script(PARTNER_PAGE)
    assert normal == partner


def test_subscription_showcase_copy_matches_top_stories_source():
    for page in (SUBSCRIBE_PAGE, PARTNER_PAGE):
        text = page.read_text()
        assert "Loading top stories…" in text
        assert "Loading recent stories…" not in text
        assert "See all Top Stories →" in text


def test_current_ranking_artifact_has_canonical_slugs_that_resolve_in_archive():
    ranking_path = ROOT / "data" / "top-stories-ranking-report.json"
    archive_path = ROOT / "archive.json"
    if not ranking_path.exists() or not archive_path.exists():
        return
    ranking = json.loads(ranking_path.read_text())
    archive = json.loads(archive_path.read_text())
    archive_slugs = {
        str(row.get("canonical_slug") or row.get("slug") or "")
        for row in archive
        if isinstance(row, dict)
    }
    selected = list(ranking.get("selected") or [])[:4]
    assert selected
    assert all(row.get("slug") in archive_slugs for row in selected)
