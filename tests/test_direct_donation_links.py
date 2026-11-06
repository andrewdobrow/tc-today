"""Every website donation CTA links directly to the official Stripe checkout."""
from pathlib import Path

from scripts.direct_donation_links import (
    STRIPE_DONATION_URL,
    direct_donation_links,
    reconcile,
)

ROOT = Path(__file__).resolve().parents[1]


def test_rewrites_legacy_and_absolute_donation_buttons_preserving_metadata():
    old = (
        '<head><link rel="canonical" href="https://treasurecoast.today/donate.html">'
        '<meta property="og:url" content="https://treasurecoast.today/donate.html"></head>'
        '<body><a class="tct-donate-header" href="/donate.html">Support TCT</a>'
        '<a href="https://treasurecoast.today/donate.html" class="footer-subscribe-cta">Donate</a>'
        '<a href="/events.html">Events</a>'
        '<a href="https://donate.stripe.com/another-payment">A different link</a></body>'
    )
    actual = direct_donation_links(old)
    assert actual.count(f'href="{STRIPE_DONATION_URL}"') == 2
    assert 'rel="canonical" href="https://treasurecoast.today/donate.html"' in actual
    assert 'property="og:url" content="https://treasurecoast.today/donate.html"' in actual
    assert '<a href="/events.html">Events</a>' in actual
    assert direct_donation_links(actual) == actual


def test_avoids_changing_other_documents_and_does_not_double_process(tmp_path):
    (tmp_path / "articles").mkdir()
    (tmp_path / "events").mkdir()
    (tmp_path / ".github").mkdir()
    old = '<a href="/donate.html" class="support-btn">Support</a>'
    (tmp_path / "articles" / "story.html").write_text(old)
    (tmp_path / "events" / "event.html").write_text(old)
    (tmp_path / ".github" / "secret.html").write_text(old)
    assert reconcile(tmp_path) == {"scanned": 2, "updated": 2}
    assert reconcile(tmp_path) == {"scanned": 2, "updated": 0}
    assert STRIPE_DONATION_URL in (tmp_path / "articles" / "story.html").read_text()
    assert STRIPE_DONATION_URL in (tmp_path / "events" / "event.html").read_text()
    assert (tmp_path / ".github" / "secret.html").read_text() == old


def test_homepage_and_article_reader_support_source_link_directly_to_stripe():
    home = (ROOT / "index.html").read_text(encoding="utf-8")
    source = (ROOT / "scripts/sync_article_reader_support.py").read_text(encoding="utf-8")
    transition = (ROOT / "scripts/free_news_transition.py").read_text(encoding="utf-8")
    assert 'href="/donate.html"' not in home
    assert STRIPE_DONATION_URL in home
    assert STRIPE_DONATION_URL in source
    assert STRIPE_DONATION_URL in transition
    assert 'href="/donate.html"' not in source


def test_browser_side_fallback_handles_retained_and_dynamic_site_links():
    main = (ROOT / "main.js").read_text(encoding="utf-8")
    assert STRIPE_DONATION_URL in main
    assert 'document.addEventListener("DOMContentLoaded", directAllDonationLinks' in main
    assert 'document.addEventListener("click", (event) =>' in main
    assert 'link.href = STRIPE_DONATION_URL' in main


def test_update_workflow_reconciles_generated_anchors_before_commit():
    workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
    assert workflow.index("python scripts/sync_article_reader_support.py") < workflow.index(
        "python scripts/direct_donation_links.py"
    )
    assert workflow.index("python scripts/direct_donation_links.py") < workflow.index(
        "- name: Commit and push"
    )
