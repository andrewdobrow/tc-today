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
