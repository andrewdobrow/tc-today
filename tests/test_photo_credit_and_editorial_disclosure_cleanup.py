"""Photo-credit removal and editorial-policy copy stay stable across publishing."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "clean_public_image_attributions.py"
spec = importlib.util.spec_from_file_location("clean_tct_public_photo_credits", MODULE)
cleaner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cleaner)


def test_remove_photo_credits_preserves_descriptive_captions_and_citations():
    html = (
        '<figure class="article-hero-image"><img src="/image.jpg">'
        '<figcaption class="img-credit">Photo: CBS12</figcaption></figure>'
        '<figure class="hero-image-wrap"><img src="/other.jpg">'
        '<figcaption class="photo-credit extra">TCT illustrative image</figcaption></figure>'
        '<figure class="article-contributor-portrait"><img src="/portrait.jpg">'
        '<figcaption><span>Guest contributor: example</span>'
        '<small>Photo: Guest studio</small></figcaption></figure>'
        '<div class="article-carousel-caption">Photo: Source media</div>'
        '<div class="article-carousel-caption">View of the river from the bridge</div>'
        '<p>According to city records, the meeting is Friday.</p>'
    )
    revised = cleaner.remove_photo_credits(html)
    assert "Photo: CBS12" not in revised
    assert "TCT illustrative image" not in revised
    assert "Photo: Guest studio" not in revised
    assert "Photo: Source media" not in revised
    assert "Guest contributor: example" in revised
    assert "View of the river from the bridge" in revised
    assert "According to city records" in revised
    assert cleaner.remove_photo_credits(revised) == revised


def test_cleanup_covers_legacy_article_and_homepage_without_rewriting_other_files(tmp_path):
    (tmp_path / "articles").mkdir()
    (tmp_path / "tests").mkdir()
    homepage = tmp_path / "index.html"
    article = tmp_path / "articles" / "sample.html"
    fixture = tmp_path / "tests" / "fixture.html"
    source = '<figure><img src="/x.jpg"><figcaption class="img-credit">Photo: News outlet</figcaption></figure>'
    for p in (homepage, article, fixture):
        p.write_text(source, encoding="utf-8")
    with pytest.raises(SystemExit, match="2 HTML page"):
        cleaner.clean(tmp_path, check=True)
    seen, changed = cleaner.clean(tmp_path)
    assert seen == 2
    assert changed == 2
    assert cleaner.clean(tmp_path, check=True) == (2, 0)
    assert "img-credit" in fixture.read_text(encoding="utf-8")
    assert "img-credit" not in article.read_text(encoding="utf-8")
    assert "img-credit" not in homepage.read_text(encoding="utf-8")


def test_automated_editorial_disclosures_removed_from_public_pages_and_generator():
    standards = (ROOT / "editorial-standards.html").read_text(encoding="utf-8")
    privacy = (ROOT / "privacy.html").read_text(encoding="utf-8")
    generator = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    for html in (standards, privacy, generator):
        assert "uses automated tools" not in html
        assert "We use technology to help us cover more local news more quickly" not in html
    assert "<h2>Editorial responsibility</h2>" in standards
    assert "Publisher Andrew Dobrow is responsible" in standards
    assert "Editorial responsibility</h2>" in generator
    assert "News content and sources</h2>" not in privacy
    # Image-source metadata is preserved internally, but no visible credit is rendered.
    assert "credit_html = \"\"" in generator
    assert "credit = \"\"" in generator
    assert "restore the publisher credit too" not in generator
