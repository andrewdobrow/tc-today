import json
import sys
import types

# Match the lightweight import setup used by the existing article prose tests.
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
if "json_repair" not in sys.modules:
    json_repair = types.ModuleType("json_repair")
    json_repair.repair_json = lambda value: value
    sys.modules["json_repair"] = json_repair

from scripts import generate
from tct_engine.article_prose_policy import repair_time_continuation_paragraph_breaks


def test_generated_body_merges_p_m_weekday_fragment_before_rendering():
    body = (
        "A St. Lucie County teen received a national honor after representing Florida and the Southeast Region. "
        "The award was presented during a ceremony in New York City. "
        "A welcome-home celebration for Enrique is planned for 7 p.m.\n\n"
        "Friday at the President Donald J. Trump International Airport.\n\n"
        "Club leaders said the student first won local and state honors before advancing to the national level."
    )
    rendered = generate.make_paragraphs(body)
    assert "7 p.m. Friday at the President Donald J. Trump International Airport." in rendered
    assert "7 p.m.</p><p>Friday" not in rendered


def test_wall_of_text_regrouper_does_not_split_p_m_from_following_weekday():
    body = (
        "The organization announced the honor Thursday afternoon after a national ceremony. "
        "The student represented Florida and the Southeast Region during the competition. "
        "A welcome-home celebration is planned for 7 p.m. Friday at the airport. "
        "Family members and club supporters are expected to attend the celebration. "
        "The student previously won local and state Youth of the Year honors. "
        "Club leaders also highlighted his work with younger members in the community. "
        "The recognition is the organization's highest honor for a club member."
    )
    assert len(body) > 320
    rendered = generate.make_paragraphs(body)
    assert "7 p.m. Friday at the airport." in rendered
    assert "7 p.m.</p><p>Friday" not in rendered


def test_existing_rendered_article_time_fragment_is_repaired():
    body_html = (
        '<p>A welcome-home celebration for Enrique is planned for 7 p.m.</p>'
        '<p>Friday at the President Donald J. Trump International Airport.</p>'
        '<p>According to club leaders, he first won local and state honors.</p>'
    )
    repaired, changed = repair_time_continuation_paragraph_breaks(body_html)
    assert changed == 1
    assert (
        '<p>A welcome-home celebration for Enrique is planned for 7 p.m. '
        'Friday at the President Donald J. Trump International Airport.</p>'
    ) in repaired
    assert "7 p.m.</p><p>Friday" not in repaired


def test_sitewide_prose_pass_repairs_already_published_generated_page(tmp_path):
    slug = "2026-10-02-st-lucie-county-teen-national-youth-of-the-year"
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "archive.json").write_text(
        json.dumps([
            {
                "slug": slug,
                "headline": "St. Lucie County teen named National Youth of the Year",
                "source_url": "https://example.com/story",
                "source_headline": "Youth of the Year",
                "is_custom": False,
            }
        ]),
        encoding="utf-8",
    )
    path = articles / f"{slug}.html"
    path.write_text(
        '<html><body><div class="article-body">'
        '<p>A welcome-home celebration for Enrique is planned for 7 p.m.</p>'
        '<p>Friday at the President Donald J. Trump International Airport.</p>'
        '<p>According to the Boys &amp; Girls Clubs, he advanced through local and state honors.</p>'
        '</div><div class="article-share"></div></body></html>',
        encoding="utf-8",
    )

    report = generate._normalize_article_prose_policy_sitewide(tmp_path)
    repaired = path.read_text(encoding="utf-8")
    assert report["updated"] == 1
    assert report["paragraphs_changed"] >= 1
    assert "7 p.m. Friday at the President Donald J. Trump International Airport." in repaired
    assert "7 p.m.</p><p>Friday" not in repaired


def test_custom_article_paragraph_boundaries_remain_immutable():
    body = (
        "Editor-written custom copy ends this paragraph at 7 p.m.\n\n"
        "Friday at the venue is intentionally a separate submitted paragraph."
    )
    rendered = generate.make_paragraphs(body, preserve_all=True)
    assert "7 p.m.</p><p>Friday" in rendered


def test_real_sentence_ending_at_p_m_is_not_joined_to_unrelated_next_sentence():
    body = (
        "The public meeting ended for the evening at 7 p.m.\n\n"
        "Police reopened the road after the meeting concluded."
    )
    rendered = generate.make_paragraphs(body)
    assert "7 p.m.</p><p>Police" in rendered


def test_coastal_flood_warning_am_thursday_stays_in_same_paragraph():
    body = (
        "A coastal flood warning remains in effect for coastal St. Lucie County until 2 a.m. Thursday "
        "as king tides are expected to produce the season's highest tides along Florida's Atlantic coast. "
        "Low-lying locations close to the water are at risk of flooding."
    )
    rendered = generate.make_paragraphs(body)
    assert "2 a.m. Thursday as king tides" in rendered
    assert not __import__("re").search(r"2 a\.m\.</p>\s*<p>Thursday", rendered)


def test_repair_orphaned_thursday_after_am():
    broken = (
        "<p>A coastal flood warning remains in effect until 2 a.m.</p>"
        "<p>Thursday as king tides are expected to produce high water.</p>"
    )
    repaired, count = repair_time_continuation_paragraph_breaks(broken)
    assert count == 1
    assert "<p>A coastal flood warning remains in effect until 2 a.m. Thursday as king tides" in repaired


def test_repair_time_continuation_misrendered_as_article_subheading():
    broken = (
        '<p>Coastal flooding remains possible until 2 a.m.</p>'
        '<h3 class="article-subhead">Thursday</h3>'
        '<p>Low-lying roads could be inundated around high tide.</p>'
    )
    repaired, changed = repair_time_continuation_paragraph_breaks(broken)
    assert changed == 1
    assert "<p>Coastal flooding remains possible until 2 a.m. Thursday</p>" in repaired
    assert '<h3 class="article-subhead">Thursday</h3>' not in repaired
    assert repair_time_continuation_paragraph_breaks(repaired) == (repaired, 0)


def test_unrelated_weekday_subheading_is_left_alone():
    original = (
        "<p>High tide can cause coastal flooding along the Treasure Coast.</p>"
        '<h3 class="article-subhead">Thursday</h3>'
        "<p>Residents should monitor local conditions.</p>"
    )
    assert repair_time_continuation_paragraph_breaks(original) == (original, 0)
