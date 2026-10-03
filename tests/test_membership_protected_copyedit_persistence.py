import importlib.util
import json
from pathlib import Path

from tct_engine.membership_paywall import FULL_BODY_MARKER, paywall_html, split_article_body


ROOT = Path(__file__).resolve().parents[1]
SLUG = "2026-10-02-two-miami-women-charged-after-tow-yard-shooting-near-stuart-sparks-school-lockou"
OLD_FRAGMENT = "video and phone and vehicle search warrants"
NEW_FRAGMENT = "video and search warrants involving phones and vehicles"


def _load_prepare_module():
    script_path = ROOT / "scripts/prepare_membership_paywall.py"
    spec = importlib.util.spec_from_file_location("prepare_membership_copyedit_persistence", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _full_body() -> str:
    return (
        "<p>Two Miami women face charges after a shooting near Stuart led deputies to pursue a vehicle and prompted a school lockout.</p>"
        "<p>The Martin County Sheriff's Office says detectives continued gathering evidence after the arrests and reviewing the circumstances surrounding the shooting.</p>"
        "<p>The Martin County Sheriff's Office says additional charges against Rondon are likely as detectives continue reviewing "
        + OLD_FRAGMENT
        + ".</p>"
        "<p>The investigation remains active, and authorities said additional information will be released when it is available.</p>"
    )


def test_protected_snapshot_cannot_resurrect_copyedit_repaired_wording(tmp_path, monkeypatch, capsys):
    prepare = _load_prepare_module()
    root = tmp_path / "repo"
    articles = root / "articles"
    data = root / "data"
    articles.mkdir(parents=True)
    data.mkdir()

    body = _full_body()
    split = split_article_body(body)
    assert split is not None

    # Simulate the live paywalled HTML after the generator has already corrected
    # the public surface. The protected snapshot still contains the older full body.
    corrected_preview = split.preview_html.replace(OLD_FRAGMENT, NEW_FRAGMENT)
    page = (
        '<html><head><script type="application/ld+json">{"@type":"NewsArticle","isAccessibleForFree":false}</script></head><body>'
        '<h1 class="article-headline">Two Miami women charged after tow yard shooting</h1>'
        '<div class="article-body tct-member-preview">'
        + corrected_preview
        + '</div><div class="tct-member-only">'
        + paywall_html(SLUG)
        + '</div><div class="article-share">share</div></body></html>'
    )
    (articles / f"{SLUG}.html").write_text(page, encoding="utf-8")

    (data / "article-content-overrides.json").write_text(json.dumps({
        "version": 1,
        "overrides": {
            SLUG: {
                "body_replacements": [{"from": OLD_FRAGMENT, "to": NEW_FRAGMENT}],
                "mark_meaningful_update": False,
                "update_status": "copyedit_correction",
            }
        },
    }), encoding="utf-8")
    (root / "archive.json").write_text(json.dumps([{
        "slug": SLUG,
        "source_url": "https://example.com/story",
        "headline": "Two Miami women charged after tow yard shooting",
    }]), encoding="utf-8")

    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({"articles": [{
        "slug": SLUG,
        "protected_body": FULL_BODY_MARKER + body,
    }]}), encoding="utf-8")
    export = tmp_path / "protected-export.json"

    monkeypatch.setattr(prepare, "ROOT", root)
    monkeypatch.setattr(prepare, "ARTICLES", articles)
    monkeypatch.setenv("TCT_MEMBERSHIP_UI_ENABLED", "true")
    monkeypatch.setenv("TCT_PROTECTED_EXPORT_PATH", str(export))
    monkeypatch.setenv("TCT_PROTECTED_SNAPSHOT_PATH", str(snapshot))

    prepare.main()

    public_html = (articles / f"{SLUG}.html").read_text(encoding="utf-8")
    protected_payload = json.loads(export.read_text(encoding="utf-8"))
    protected_body = protected_payload["articles"][0]["protected_body"]

    assert OLD_FRAGMENT not in public_html
    assert OLD_FRAGMENT not in protected_body
    assert NEW_FRAGMENT in protected_body
    assert protected_body.startswith(FULL_BODY_MARKER)
    assert "article-update" not in public_html
    assert "Original report:" not in public_html
    assert "1 protected copy-edit replacement(s) applied" in capsys.readouterr().out


def test_copyedit_replacement_is_idempotent_and_accepts_html_escaped_text():
    prepare = _load_prepare_module()
    replacements = [{
        "from": "Sheriff's Office and phone and vehicle records",
        "to": "Sheriff's Office records involving phones and vehicles",
    }]
    body = "<p>Sheriff&#x27;s Office and phone and vehicle records</p>"
    repaired, changed = prepare._apply_article_body_replacements(body, replacements)
    assert changed == 1
    assert "Sheriff&#x27;s Office records involving phones and vehicles" in repaired
    repaired_again, changed_again = prepare._apply_article_body_replacements(repaired, replacements)
    assert repaired_again == repaired
    assert changed_again == 0
