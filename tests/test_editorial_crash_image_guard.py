"""A human-rejected competitor photo must not return during generation."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/enforce_editorial_crash_image.py"
spec = importlib.util.spec_from_file_location("tct_crash_image_guard", SCRIPT)
guard = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(guard)


def test_image_guard_rewrites_article_home_rss_and_archive(tmp_path):
    approved = "https://treasurecoast.today/images/editorial/cities/vero-beach/vero-beach-city-sign.webp"
    old = guard.REJECTED_IMAGE
    slug = guard.SLUG
    (tmp_path / "articles").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / guard.OVERRIDE_LEDGER).write_text(
        json.dumps({"overrides": {slug: {"image_url": approved}}}), encoding="utf-8"
    )
    page = tmp_path / "articles" / (slug + ".html")
    page.write_text(
        f'<meta property="og:image" content="{old}"><meta name="twitter:image" '
        f'content="{old}"><figure class="article-hero-image"><img src="{old}">'
        '<figcaption class="img-credit">Photo: CBS12</figcaption></figure>',
        encoding="utf-8",
    )
    other = "https://example.com/unrelated.jpg"
    (tmp_path / "index.html").write_text(
        f'<a href="/articles/{slug}.html"><img src="{old}">'
        '<figcaption class="img-credit">Photo: CBS12</figcaption></a>'
        f'<a href="/articles/different.html"><img src="{other}"></a>',
        encoding="utf-8",
    )
    (tmp_path / "feed.xml").write_text(
        f'<rss><item><link>/articles/{slug}.html</link><media:content url="{old}"/></item>'
        f'<item><link>/articles/unrelated.html</link><media:content url="{other}"/></item></rss>',
        encoding="utf-8",
    )
    (tmp_path / "archive.json").write_text(json.dumps([
        {"slug": slug, "image_url": old},
        {"slug": "other-story", "image_url": other},
    ]), encoding="utf-8")
    (tmp_path / "data.json").write_text(json.dumps([
        {"slug": slug, "image_url": old},
    ]), encoding="utf-8")

    changed = guard.apply(tmp_path)
    assert {"index.html", "feed.xml", "archive.json", "data.json",
            f"articles/{slug}.html"} <= set(changed)
    assert old not in page.read_text(encoding="utf-8")
    assert approved in page.read_text(encoding="utf-8")
    assert "Photo: CBS12" not in page.read_text(encoding="utf-8")
    assert other in (tmp_path / "index.html").read_text(encoding="utf-8")
    assert other in (tmp_path / "feed.xml").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "archive.json").read_text())[0]["image_url"] == approved
    assert guard.apply(tmp_path) == []


def test_real_article_and_override_agree():
    approved = guard.approved_url(ROOT)
    article = (ROOT / "articles" / (guard.SLUG + ".html")).read_text(encoding="utf-8")
    assert guard.REJECTED_IMAGE not in article
    assert f'<meta property="og:image" content="{approved}">' in article
    assert f'<meta name="twitter:image" content="{approved}">' in article
    assert f'<img src="{approved}"' in article
