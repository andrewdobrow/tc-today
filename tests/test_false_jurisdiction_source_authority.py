from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import os
import types

ROOT = Path(__file__).resolve().parents[1]
BAD_SLUG = "2026-08-06-indian-river-county-sheriffs-deputies-shoot-kill-18-year-old-attacking-father-wi"

def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")
        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)
        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    spec = importlib.util.spec_from_file_location("tct_generate_false_jurisdiction_test", ROOT / "scripts" / "generate.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

def test_palm_beach_source_cannot_authorize_indian_river_copy():
    generate = _load_generate()
    item = {
        "category_key": "indian_river",
        "headline": "Indian River County deputies shoot, kill 18-year-old attacking father",
        "body": "Indian River County deputies shot an 18-year-old during an attack.",
    }
    source = {
        "category_key": "indian_river",
        "title": "Deputy shoots teen attacking father in Palm Beach County",
        "article_text": "Palm Beach County Sheriff's Office deputies responded near West Palm Beach.",
        "link": "https://example.com/palm-beach-county/deputy-shooting",
    }
    diag = generate._source_jurisdiction_diagnostics(item, source)
    assert diag["passed"] is False
    assert "generated_jurisdiction_not_supported_by_source" in diag["missing"]
    assert "source_jurisdiction_conflicts_with_generated_county" in diag["missing"]

def test_vero_beach_source_can_authorize_indian_river_copy():
    generate = _load_generate()
    item = {"category_key": "indian_river", "headline": "Deputies investigate Vero Beach incident", "body": "Deputies responded in Vero Beach."}
    source = {"category_key": "indian_river", "title": "Deputies investigate Vero Beach incident", "article_text": "Indian River County deputies responded in Vero Beach."}
    diag = generate._source_jurisdiction_diagnostics(item, source)
    assert diag["passed"] is True
    assert diag["local_source_hits"]

def test_county_zero_candidate_uses_archive_recovery():
    generate = _load_generate()
    sources = [{
        "title": "Palm Beach County deputies investigate shooting west of Boca Raton",
        "summary": "The Palm Beach County Sheriff's Office responded near Boca Raton.",
        "article_text": "Palm Beach County deputies responded west of Boca Raton.",
        "source_quality": "full",
    }]
    assert generate._county_zero_candidate_fast_recovery("indian_river", sources) is True

def test_exact_bad_publication_is_retired_from_every_surface(tmp_path):
    article_dir = tmp_path / "articles"; article_dir.mkdir()
    bad_path = article_dir / f"{BAD_SLUG}.html"
    bad_path.write_text("<html><body>bad</body></html>", encoding="utf-8")
    (tmp_path / "archive.json").write_text(json.dumps([{"slug": BAD_SLUG}, {"slug": "safe"}]), encoding="utf-8")
    (tmp_path / "data.json").write_text(json.dumps({"hero": {"slug": BAD_SLUG}, "cards": [{"slug": "safe"}]}), encoding="utf-8")
    (tmp_path / "feed.xml").write_text(
        f"<rss><channel><item><link>https://treasurecoast.today/articles/safe-before.html</link></item>"
        f"<item><link>https://treasurecoast.today/articles/{BAD_SLUG}.html</link></item>"
        f"<item><link>https://treasurecoast.today/articles/safe-after.html</link></item></channel></rss>",
        encoding="utf-8",
    )
    sitemap = (
        f"<urlset><url><loc>https://treasurecoast.today/articles/safe-before.html</loc></url>"
        f"<url><loc>https://treasurecoast.today/articles/{BAD_SLUG}.html</loc></url>"
        f"<url><loc>https://treasurecoast.today/articles/safe-after.html</loc></url></urlset>"
    )
    (tmp_path / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (tmp_path / "news-sitemap.xml").write_text(sitemap, encoding="utf-8")
    (tmp_path / "index.html").write_text(
        f'<main><section class="hero hero-v3" data-cat-hero="all"><a href="/articles/{BAD_SLUG}.html">bad</a></section>'
        '<section class="hero hero-v3" data-cat-hero="crime" style="display:none"><a href="/articles/safe-before.html">safe before</a></section>'
        '<a class="latest-item" href="/articles/safe-after.html">safe after</a></main>',
        encoding="utf-8",
    )
    subprocess.run([sys.executable, str(ROOT / "scripts" / "repair_false_jurisdiction_publication.py"), str(tmp_path)], check=True)
    assert "noindex" in bad_path.read_text(encoding="utf-8")
    for name in ("archive.json", "data.json", "feed.xml", "sitemap.xml", "news-sitemap.xml", "index.html"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert BAD_SLUG not in text
        if name in {"feed.xml", "sitemap.xml", "news-sitemap.xml", "index.html"}:
            assert "safe-before" in text
            assert "safe-after" in text
    assert 'data-cat-hero="all"' in (tmp_path / "index.html").read_text(encoding="utf-8")

def test_workflows_patch_and_repair_before_tests_and_generation():
    for name in ("test-editorial-engine.yml", "update.yml"):
        text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert text.index("Apply false-jurisdiction source guard") < text.index("Run editorial engine tests")
        assert text.index("Retire false-jurisdiction publication") < text.index("Run editorial engine tests")
    production = (ROOT / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
    assert production.index("Retire false-jurisdiction publication") < production.index("Generate news")
