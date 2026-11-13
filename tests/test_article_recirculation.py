"""TCT recirculation must help readers without disturbing Mediavine ads."""
from pathlib import Path

from scripts import build_audience_features as features


ROOT = Path(__file__).resolve().parents[1]


def _story(slug, headline, *, county="st_lucie", event_key="", date="2026-11-11"):
    return {
        "slug": slug,
        "headline": headline,
        "teaser": headline,
        "date": date,
        "category_key": "local_gov",
        "category_label": "Local Government",
        "county_keys": [county],
        "editorial_event_key": event_key,
        "image_url": "https://images.treasurecoast.today/story.jpg",
    }


def test_subject_matching_outranks_geography_and_avoids_random_crime():
    current = _story("safety", "Family seeks road safety improvements after teen killed")
    nearby_but_unrelated = _story(
        "crime", "St Lucie County man arrested following police chase"
    )
    relevant = _story(
        "walking", "Family questions walking safety after teen death"
    )
    title, matches = features._related_entries(
        current, [nearby_but_unrelated, relevant]
    )
    assert title == "Related Coverage"
    assert [row["slug"] for row in matches] == ["walking"]


def test_sponsored_stories_are_not_presented_as_editorial_read_next():
    current = _story("safety", "Family seeks road safety improvements after teen killed")
    sponsored = _story("ad", "Family seeks new road safety improvements after teen killed")
    sponsored["sponsored"] = True
    _, matches = features._related_entries(current, [sponsored])
    assert not matches


def test_explicit_story_identity_allows_followups_without_keyword_overlap():
    current = _story("first", "City examines roadway improvements", event_key="case123")
    update = _story("second", "Commission approves transportation funding", event_key="case123")
    _, matches = features._related_entries(current, [update])
    assert [row["slug"] for row in matches] == ["second"]


def test_cross_county_subject_matches_but_geographic_nearby_does_not():
    current = _story("storm", "Flood recovery starts as families return home")
    other_county = _story(
        "water", "Families face flood recovery costs after returning home",
        county="martin"
    )
    same_county_unrelated = _story(
        "restaurant", "New restaurant opening announced by local officials"
    )
    _, matches = features._related_entries(current, [same_county_unrelated, other_county])
    assert [row["slug"] for row in matches] == ["water"]


def test_read_next_is_semantic_mobile_ready_and_links_are_measurable():
    stories = [
        _story("s1", "Family questions walking safety after teen death"),
        _story("s2", "Residents seek sidewalk fixes along major road"),
        _story("s3", "City promises road safety improvements by spring"),
        _story("s4", "New crosswalks planned at school"),
        _story("s5", "Extra story should not be in Read Next"),
    ]
    output = features._render_article_recirculation(stories)
    assert output.count(features.RECIRCULATION_START) == 1
    assert output.count('data-tct-recirculation-link="inline"') == 0
    assert output.count('data-tct-recirculation-link="read_next"') == 3
    assert "Read Next" in output
    assert "Extra story" not in output
    assert 'loading="lazy"' in output
    assert 'class="tct-read-next-grid"' in output


def test_ad_safe_recommendations_are_outside_body_and_do_not_move_ad_slots():
    body = '<div class="article-body"><p>First.</p><p>Second.</p></div>'
    ad = '<div class="mv-leader" data-ad-slot="original"></div>'
    donation = '<!-- TCT_ARTICLE_READER_SUPPORT_START -->'
    page = '<main><div class="article-main-column">' + body + ad + donation + '</div></main>'
    stories = [_story("a", "Relevant local reporting"), _story("b", "More local reporting")]
    result = features._insert_article_recirculation(page, stories)
    # The body remains byte-for-byte unchanged and all ad markup retains order.
    assert body in result
    assert ad in result
    assert result.index("</div>") < result.index(features.RECIRCULATION_START)
    assert result.index(features.RECIRCULATION_END) < result.index(ad)
    assert result.index(ad) < result.index(donation)
    assert 'data-tct-recirculation-link="inline"' not in result
    assert features._insert_article_recirculation(result, stories) == result


def _long_body(n=9):
    return '<div class="article-body">' + ''.join(
        f'<p>Paragraph {i}. Local residents have raised detailed concerns '
        'about pedestrian safety, road improvements and neighborhood access '
        'following several community meetings.</p>'
        for i in range(1, n + 1)
    ) + '</div>'


def test_long_article_has_one_midstory_link_and_distinct_end_cards():
    body = _long_body(9)
    ad = '<div class="mv-leader" data-ad-slot="existing"></div>'
    donation = '<!-- TCT_ARTICLE_READER_SUPPORT_START -->'
    page = body + '\n' + ad + '\n' + donation
    stories = [_story(f"story-{i}", f"Road safety update number {i}") for i in range(5)]
    output = features._insert_article_recirculation(page, stories)
    assert output.count(features.RECIRCULATION_INLINE_START) == 1
    assert output.count(features.RECIRCULATION_INLINE_END) == 1
    assert output.count('data-tct-recirculation-link="inline"') == 1
    assert output.count('data-tct-recirculation-link="read_next"') == 3
    assert output.index('Paragraph 4.') < output.index(features.RECIRCULATION_INLINE_START)
    assert output.index(features.RECIRCULATION_INLINE_END) < output.index('Paragraph 5.')
    assert output.index(features.RECIRCULATION_END) < output.index(ad)
    assert output.index(ad) < output.index(donation)
    assert output.count('href="/articles/story-0.html"') == 1
    assert output.count('href="/articles/story-1.html"') == 1
    assert output.count("<p>Paragraph ") == 9
    # Removing just our injected note leaves every original paragraph intact.
    import re
    restored = re.sub(
        r'\n?' + re.escape(features.RECIRCULATION_INLINE_START)
        + r'.*?' + re.escape(features.RECIRCULATION_INLINE_END) + r'\n?',
        '', output, flags=re.S,
    )
    assert body in restored
    assert features._insert_article_recirculation(output, stories) == output


def test_brief_and_low_substance_articles_never_receive_midstory_link():
    stories = [_story("a", "Relevant local story"), _story("b", "Another local story")]
    for body in (
        _long_body(6),
        '<div class="article-body">' + '<p>Brief update.</p>' * 10 + '</div>',
    ):
        output = features._insert_article_recirculation(body, stories)
        assert body in output
        assert features.RECIRCULATION_INLINE_START not in output
        assert output.count('data-tct-recirculation-link="read_next"') == 2


def test_sponsored_articles_do_not_get_intrusive_midstory_recommendations():
    output = features._insert_article_recirculation(
        _long_body(9), [_story("a", "Relevant local story")], allow_inline=False,
    )
    assert features.RECIRCULATION_INLINE_START not in output
    assert 'data-tct-recirculation-link="read_next"' in output


def test_existing_midstory_link_reconciles_and_is_not_duplicated():
    stories = [_story("a", "Road safety update"), _story("b", "More road safety news")]
    original = _long_body(9)
    once = features._insert_article_recirculation(original, stories)
    assert features._insert_article_recirculation(once, stories) == once
    # An earlier post-body ALSO READ link is removed when the module is rebuilt.
    old = (
        features.RECIRCULATION_START
        + '<p class="tct-related-inline" data-tct-recirculation="inline">OLD</p>'
        + features.RECIRCULATION_END
    )
    migrated = features._insert_article_recirculation(original + old, stories)
    assert "OLD" not in migrated
    assert migrated.count(features.RECIRCULATION_INLINE_START) == 1


def test_malformed_nested_body_is_left_untouched_to_protect_ads():
    page = (
        '<div class="article-body"><p>First</p>'
        '<div class="mv-leader"></div><p>Second</p></div>'
    )
    assert features._insert_article_recirculation(
        page, [_story("a", "Relevant local story")]
    ) == page


def test_empty_matches_never_create_placeholder_read_next():
    source = '<div class="article-body"><p>Article content.</p></div>'
    assert features._insert_article_recirculation(source, []) == source


def test_read_next_css_and_tracking_are_built_into_shared_assets():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    js = (ROOT / "main.js").read_text(encoding="utf-8")
    assert ".tct-read-next-grid" in css
    assert ".tct-read-next-card" in css
    assert "@media (max-width: 740px)" in css
    assert 'data-tct-recirculation-link' in js
    assert 'article_recirculation_click' in js
    assert 'article_second_view' in js
    assert 'tct_article_paths_in_session' in js
    assert 'transport_type: "beacon"' in js
    assert 'ASSET_VERSION = "1.13.9.127"' in (
        ROOT / "scripts" / "build_audience_features.py"
    ).read_text(encoding="utf-8")
