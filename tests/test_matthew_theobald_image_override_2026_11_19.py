"""Ensure Matthew Theobald's editor-selected photo remains on all public surfaces."""
import json
import re
from pathlib import Path

from scripts.sync_editorial_image_archive import sync_archive
from scripts.reconcile_editorial_image_surfaces import _fix_rss_social_image_authority

ROOT = Path(__file__).resolve().parents[1]
SLUG = "2026-11-19-martin-county-school-board-reinstates-matthew-theobald-awards-back-pay"
IMAGE = "https://treasurecoast.today/images/matthew-theobald.webp"
OLD = "https://images.treasurecoast.today/articles/1e/1e46a71a069e3ce64e45b94c178bf867a2fdb21a1d0d8033dd9d5b9d79b79f81.jpg"
HEADLINE = "Martin County School Board reinstates Matthew Theobald, awards back pay"


def test_editorial_override_is_pinned_to_exact_story():
    overrides = json.loads((ROOT / "data/article-image-overrides.json").read_text())["overrides"]
    assert overrides[SLUG]["image_url"] == IMAGE


def test_article_main_open_graph_twitter_and_structured_images():
    page = (ROOT / "articles" / (SLUG + ".html")).read_text(encoding="utf-8")
    assert OLD not in page
    assert f'<figure class="article-hero-image"><img src="{IMAGE}"' in page
    assert f'<meta property="og:image" content="{IMAGE}">' in page
    assert f'<meta name="twitter:image" content="{IMAGE}">' in page
    assert f'"image":["{IMAGE}"]' in page
    assert '<meta property="og:image:width" content="800">' in page
    assert '<meta property="og:image:height" content="450">' in page


def test_homepage_feed_and_social_image_authority():
    home = (ROOT / "index.html").read_text(encoding="utf-8")
    links = re.findall(
        r'<a\b[^>]*href="[^"]*/articles/' + re.escape(SLUG)
        + r'\.html"[^>]*>.*?</a>', home, re.I | re.S,
    )
    # Homepage cards rotate away after newer stories arrive.
    assert all(IMAGE in link for link in links if "<img " in link)
    feed = (ROOT / "feed.xml").read_text(encoding="utf-8")
    items = [
        item.group(0)
        for item in re.finditer(r"<item\b[^>]*>.*?</item>", feed, re.I | re.S)
        if f"/articles/{SLUG}.html" in item.group(0)
    ]
    # RSS is a finite feed; enforce the photo only while the item remains.
    assert all(f'<media:content url="{IMAGE}"' in item for item in items)
    authority = json.loads((ROOT / "data/rss-social-image-authority.json").read_text())
    matching = [row for row in authority["items"] if row["slug"] == SLUG]
    # This audit stores only the most recent articles, not a permanent index.
    assert len(matching) <= 1
    assert all(row["image_url"] == IMAGE for row in matching)


def test_homepage_json_and_app_archive_sync(tmp_path):
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))

    def collect(node):
        if isinstance(node, dict):
            here = [node] if node.get("headline") == HEADLINE else []
            return here + [item for value in node.values() for item in collect(value)]
        if isinstance(node, list):
            return [item for value in node for item in collect(value)]
        return []

    rows = collect(data)
    # data.json contains only the current homepage selection and can rotate.
    assert all(row["image_url"] == IMAGE for row in rows)

    (tmp_path / "data").mkdir()
    (tmp_path / "data/article-image-overrides.json").write_text(
        json.dumps({"overrides": {SLUG: {"image_url": IMAGE}}}), encoding="utf-8"
    )
    (tmp_path / "archive.json").write_text(
        json.dumps([{"slug": SLUG, "image_url": OLD},
                    {"slug": "different-story", "image_url": OLD}]), encoding="utf-8"
    )
    assert sync_archive(tmp_path) == (1, 1)
    updated = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert updated[0]["image_url"] == IMAGE
    assert updated[0]["rss_social_image_url"] == IMAGE
    assert updated[1]["image_url"] == OLD


def test_generated_rss_authority_is_reconciled_without_touching_other_articles(tmp_path):
    authority_path = tmp_path / "rss-social-image-authority.json"
    unrelated = {
        "slug": "different-story",
        "image_url": OLD,
        "image_kind": "source",
        "origin": "verified_live_article_source",
    }
    authority = {
        "schema_version": 1,
        "items": [
            {"slug": SLUG, "image_url": OLD, "image_kind": "source",
             "origin": "verified_live_article_source"},
            dict(unrelated),
        ],
    }
    authority_path.write_text(json.dumps(authority, indent=2) + "\n", encoding="utf-8")

    assert _fix_rss_social_image_authority(authority_path, SLUG, IMAGE) is True
    updated = json.loads(authority_path.read_text(encoding="utf-8"))
    assert updated["items"][0]["image_url"] == IMAGE
    assert updated["items"][0]["slug"] == SLUG
    assert updated["items"][1] == unrelated
    assert _fix_rss_social_image_authority(authority_path, SLUG, IMAGE) is False
    assert _fix_rss_social_image_authority(authority_path, "rotated-out-story", IMAGE) is False
