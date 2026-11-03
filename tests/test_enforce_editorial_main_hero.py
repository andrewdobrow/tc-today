"""Regression coverage for general news hero / sponsored story separation."""
import json

import pytest

from scripts.enforce_editorial_main_hero import ensure_editorial_main_hero

SPONSOR = "sponsored-roof-column"
FLOOD = "flooding-school-closures"
SECOND = "flooded-roads"


def _section(category, slug, label=""):
    heading = f'<div class="county-section-label"><h2>{label}</h2></div>' if label else ""
    return (
        f'<section class="hero hero-v3" data-cat-hero="{category}">'
        f'{heading}<a class="hero-v3-link" href="https://treasurecoast.today/articles/{slug}.html">'
        f'<div class="hero-v3-media"><img src="https://treasurecoast.today/images/{slug}.jpg"></div>'
        f'<div class="hero-v3-content"><h1>{slug}</h1></div></a></section>'
    )


def _set_up(root, top_slug=SPONSOR, selected=None, queue=None):
    (root / "articles").mkdir()
    (root / "data").mkdir()
    (root / "articles" / f"{SPONSOR}.html").write_text("<p>This article was produced in partnership with a sponsor</p>")
    (root / "articles" / f"{FLOOD}.html").write_text("<p>Closures after severe flooding</p>")
    (root / "articles" / f"{SECOND}.html").write_text("<p>Flooded roads</p>")
    home = _section("all", top_slug) + _section("indian_river", FLOOD, "County News") + _section("st_lucie", SECOND, "County News")
    (root / "index.html").write_text(home)
    (root / "custom_articles.json").write_text(json.dumps(queue or []))
    (root / "data" / "top-stories-ranking-report.json").write_text(
        json.dumps({"selected": selected if selected is not None else [
            {"slug": FLOOD, "primary_eligible": True, "rank": 1},
            {"slug": SECOND, "primary_eligible": True, "rank": 2},
        ]})
    )
    return home


def test_sponsored_hero_is_replaced_by_top_ranked_editorial_flooding_story(tmp_path):
    before = _set_up(tmp_path)
    assert ensure_editorial_main_hero(tmp_path) is True
    after = (tmp_path / "index.html").read_text()
    assert 'data-cat-hero="all"><a class="hero-v3-link" href="https://treasurecoast.today/articles/' + FLOOD + '.html"' in after
    assert "county-section-label" in after
    assert before.split('data-cat-hero="indian_river"')[1] == after.split('data-cat-hero="indian_river"')[1]
    assert ensure_editorial_main_hero(tmp_path) is False


def test_existing_editorial_hero_is_never_reordered(tmp_path):
    before = _set_up(tmp_path, top_slug=SECOND)
    assert ensure_editorial_main_hero(tmp_path) is False
    assert (tmp_path / "index.html").read_text() == before


def test_sponsored_candidate_is_skipped_when_ranked_higher(tmp_path):
    _set_up(tmp_path, selected=[{"slug": SPONSOR, "primary_eligible": True}, {"slug": FLOOD, "primary_eligible": True}])
    assert ensure_editorial_main_hero(tmp_path) is True
    assert f'articles/{FLOOD}.html' in (tmp_path / "index.html").read_text().split('data-cat-hero="all"')[1].split('</section>')[0]


def test_missing_editorial_replacement_fails_closed(tmp_path):
    before = _set_up(tmp_path, selected=[{"slug": SPONSOR, "primary_eligible": True}])
    with pytest.raises(RuntimeError, match="no eligible ranked editorial"):
        ensure_editorial_main_hero(tmp_path)
    assert (tmp_path / "index.html").read_text() == before


def test_approved_sponsored_queue_is_respected(tmp_path):
    _set_up(tmp_path, queue=[{"slug": SPONSOR, "sponsored": True}])
    assert ensure_editorial_main_hero(tmp_path) is True
