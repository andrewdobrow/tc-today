import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

# Production installs these dependencies. Stub them for lightweight local import
# of scripts/generate.py, matching the existing article-prose regression tests.
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
from scripts import prepare_membership_paywall as prepare
from tct_engine.membership_paywall import FULL_BODY_MARKER
from tct_engine.article_prose_policy import (
    repair_multparagraph_quote_continuations,
    sanitize_article_body_html,
)


def test_two_paragraph_continuous_curly_quote_gets_continuation_opener_only():
    body = '<p>“I think this is important and residents deserve an answer.</p><p>This is the second paragraph of the same quotation.”</p>'
    repaired, changed = repair_multparagraph_quote_continuations(body)
    assert changed == 1
    assert repaired == '<p>“I think this is important and residents deserve an answer.</p><p>“This is the second paragraph of the same quotation.”</p>'
    assert 'answer.”</p>' not in repaired


def test_three_paragraph_continuous_curly_quote_opens_each_continuation_and_closes_only_final():
    body = '<p>“Paragraph one stays open.</p><p>Paragraph two also stays open.</p><p>Paragraph three closes here.”</p>'
    repaired, changed = repair_multparagraph_quote_continuations(body)
    assert changed == 2
    assert repaired == '<p>“Paragraph one stays open.</p><p>“Paragraph two also stays open.</p><p>“Paragraph three closes here.”</p>'
    assert 'one stays open.”' not in repaired
    assert 'two also stays open.”' not in repaired


def test_straight_quote_version_is_statefully_repaired():
    body = '<p>"First paragraph stays open.</p><p>Second paragraph closes here."</p>'
    repaired, changed = repair_multparagraph_quote_continuations(body)
    assert changed == 1
    assert repaired == '<p>"First paragraph stays open.</p><p>&quot;Second paragraph closes here."</p>'


def test_already_correct_continuation_paragraphs_are_idempotent():
    body = '<p>“First paragraph stays open.</p><p>“Second paragraph stays open.</p><p>“Third paragraph closes.”</p>'
    repaired, changed = repair_multparagraph_quote_continuations(body)
    assert changed == 0
    assert repaired == body


def test_normal_one_paragraph_quote_is_untouched():
    body = '<p>Officials said, “This quotation opens and closes in one paragraph.”</p><p>Ordinary prose follows.</p>'
    repaired, changed = repair_multparagraph_quote_continuations(body)
    assert changed == 0
    assert repaired == body


def test_multiple_separate_quotations_in_one_article_do_not_leak_state():
    body = '<p>“First complete quotation.”</p><p>Context between quotations.</p><p>“Second complete quotation.”</p>'
    repaired, changed = repair_multparagraph_quote_continuations(body)
    assert changed == 0
    assert repaired == body


def test_ordinary_paragraph_following_completed_quote_does_not_gain_quote_mark():
    body = '<p>“The completed quotation ends here.”</p><p>The commission voted later that evening.</p>'
    repaired, changed = repair_multparagraph_quote_continuations(body)
    assert changed == 0
    assert '<p>“The commission' not in repaired
    assert repaired == body


def test_apostrophes_and_contractions_do_not_affect_double_quote_state():
    body = "<p>It's the county's decision, and officials don't expect a delay.</p><p>Residents' comments were recorded.</p>"
    repaired, changed = repair_multparagraph_quote_continuations(body)
    assert changed == 0
    assert repaired == body


def test_quoted_phrase_that_begins_and_ends_within_one_paragraph_does_not_leak_state():
    body = '<p>The mayor called the proposal “an important step” during the meeting.</p><p>The vote followed.</p>'
    repaired, changed = repair_multparagraph_quote_continuations(body)
    assert changed == 0
    assert repaired == body


def test_donalds_jolly_style_regression_repairs_second_paragraph_without_closing_first():
    body = (
        '<p>Donalds told the audience he supports the measure. “I think voters should have a chance to vote on this.</p>'
        '<p>I think this is fundamentally about homeownership.”</p>'
    )
    repaired, changed = repair_multparagraph_quote_continuations(body)
    assert changed == 1
    assert 'vote on this.</p><p>“I think this is fundamentally about homeownership.”</p>' in repaired
    assert 'vote on this.”</p>' not in repaired


def test_final_sitewide_post_render_prose_path_repairs_retained_generated_page(tmp_path):
    root = tmp_path
    articles = root / "articles"
    articles.mkdir()
    slug = "2026-09-23-donalds-backs-amendment-3-homestead-exemption-jolly-opposes-debate-off-the-table"
    (root / "archive.json").write_text(
        json.dumps([
            {
                "slug": slug,
                "source_url": "https://www.wptv.com/example",
                "source_headline": "Candidate forum - WPTV",
                "is_custom": False,
            }
        ]),
        encoding="utf-8",
    )
    page = (
        '<html><body><div class="article-body">'
        '<p>“I think this is important and residents deserve an answer.</p>'
        '<p>This is the second paragraph of the same quotation.”</p>'
        '</div><div class="article-share"></div></body></html>'
    )
    path = articles / f"{slug}.html"
    path.write_text(page, encoding="utf-8")

    report = generate._normalize_article_prose_policy_sitewide(root)
    repaired = path.read_text(encoding="utf-8")
    assert report == {"scanned": 1, "updated": 1, "paragraphs_changed": 1}
    assert '<p>“This is the second paragraph of the same quotation.”</p>' in repaired


def test_paywalled_donalds_jolly_retained_body_is_repaired_during_membership_rehydration(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    articles = root / "articles"
    articles.mkdir(parents=True)
    slug = "2026-09-23-donalds-backs-amendment-3-homestead-exemption-jolly-opposes-debate-off-the-table"
    (root / "archive.json").write_text(
        json.dumps([{
            "slug": slug,
            "source_url": "https://www.wptv.com/example",
            "source_headline": "Candidate forum - WPTV",
            "is_custom": False,
        }]),
        encoding="utf-8",
    )
    paywalled_page = (
        '<html><head><title>Test</title></head><body>'
        '<div class="article-body tct-member-preview"><p>Existing preview text that is long enough to represent a previously paywalled article preview.</p></div>'
        '<div class="tct-member-only"><div data-tct-paywall></div><div id="tct-protected-content"></div></div>'
        '<div class="article-share"></div></body></html>'
    )
    (articles / f"{slug}.html").write_text(paywalled_page, encoding="utf-8")

    lead = (
        "Republican Byron Donalds and Democrat David Jolly presented opposing positions on the ballot measure during a public forum. "
        "The discussion covered the homestead exemption proposal and the candidates' positions before the November election. "
    )
    tail = (
        "The forum continued with discussion of taxes, housing and other issues facing Florida voters. "
        "The candidates also addressed how they would approach the issue if elected. "
    )
    full_body = (
        f"<p>{lead * 2}</p>"
        '<p>Donalds told the audience he supports the measure. “I think voters should have a chance to vote on this.</p>'
        '<p>I think this is fundamentally about homeownership.”</p>'
        f"<p>{tail * 3}</p>"
    )
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps({"articles": [{"slug": slug, "protected_body": FULL_BODY_MARKER + full_body}]}),
        encoding="utf-8",
    )
    export = tmp_path / "protected-export.json"

    monkeypatch.setattr(prepare, "ROOT", root)
    monkeypatch.setattr(prepare, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.setenv("TCT_PROTECTED_SNAPSHOT_PATH", str(snapshot))
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(export))

    prepare.main()

    protected_payload = export.read_text(encoding="utf-8")
    assert '“I think this is fundamentally about homeownership.”' in protected_payload
    assert 'vote on this.”' not in protected_payload


def test_existing_source_outlet_prose_guard_stays_intact_while_quote_repair_runs():
    body = (
        '<p>The store owner declined to talk to WPBF News 25.</p>'
        '<p>“This quotation begins here and stays open.</p>'
        '<p>This continuation closes here.”</p>'
    )
    repaired, changed = sanitize_article_body_html(
        body,
        source_url="https://www.wpbf.com/article/example/123",
        source_headline="Store update - WPBF",
    )
    assert changed == 2
    assert "WPBF" not in repaired
    assert '<p>“This continuation closes here.”</p>' in repaired


def test_sitewide_generated_prose_guard_does_not_silently_rewrite_custom_articles(tmp_path):
    root = tmp_path
    articles = root / "articles"
    articles.mkdir()
    slug = "custom-article-with-intentional-quote-formatting"
    (root / "archive.json").write_text(
        json.dumps([{"slug": slug, "is_custom": True}]),
        encoding="utf-8",
    )
    page = (
        '<html><body><div class="article-body">'
        '<p>“An intentionally open custom quote.</p><p>Custom continuation without an opener.”</p>'
        '</div><div class="article-share"></div></body></html>'
    )
    path = articles / f"{slug}.html"
    path.write_text(page, encoding="utf-8")

    report = generate._normalize_article_prose_policy_sitewide(root)
    assert report == {"scanned": 0, "updated": 0, "paragraphs_changed": 0}
    assert path.read_text(encoding="utf-8") == page


def test_assignment_writer_prompt_explicitly_requires_multparagraph_quote_typography(monkeypatch):
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(text=json.dumps({
                "headline": "Test headline",
                "teaser": "Test teaser.",
                "body": "A complete test body with enough verified detail.",
                "urgency_score": 4,
                "published": "2026-09-24T12:00:00-04:00",
                "source_index": 1,
            }))]
        )

    monkeypatch.setattr(
        generate,
        "client",
        SimpleNamespace(messages=SimpleNamespace(create=create)),
    )
    packet = {
        "category_key": "martin",
        "category_label": "Martin County",
        "source_inputs": [{
            "title": "Test source",
            "published": "2026-09-24T12:00:00-04:00",
            "story_form": "new",
            "article_text": "Verified source text with enough information to write the assigned item. " * 20,
        }],
    }
    assignment = {"source_index": 1, "angle": "Lead with the verified development", "urgency_score": 4}

    generate._run_assignment_writer(packet, assignment, role="card")
    prompt = captured["messages"][0]["content"]
    assert "every continuation paragraph must begin with a new opening quotation mark" in prompt
    assert "Do not close intermediate paragraphs; close the quotation only at the end of the final quoted paragraph." in prompt
