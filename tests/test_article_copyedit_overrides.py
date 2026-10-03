import json
import sys
import types
from pathlib import Path

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


SLUG = "2026-10-02-two-miami-women-charged-after-tow-yard-shooting-near-stuart-sparks-school-lockou"
OLD = (
    "The Martin County Sheriff's Office says additional charges against Rondon are likely "
    "as detectives continue reviewing video and phone and vehicle search warrants."
)
NEW = (
    "The Martin County Sheriff's Office says additional charges against Rondon are likely "
    "as detectives continue reviewing video and search warrants involving phones and vehicles."
)


def _override_payload():
    return {
        "version": 1,
        "overrides": {
            SLUG: {
                "body_replacements": [{
                    "from": "video and phone and vehicle search warrants",
                    "to": "video and search warrants involving phones and vehicles",
                }],
                "mark_meaningful_update": False,
                "update_status": "copyedit_correction",
            }
        },
    }


def test_current_rondon_copyedit_is_durable_and_non_substantive():
    payload = json.loads((Path(__file__).resolve().parents[1] / "data" / "article-content-overrides.json").read_text())
    row = payload["overrides"][SLUG]
    assert row["mark_meaningful_update"] is False
    assert any(
        edit.get("from") == "video and phone and vehicle search warrants"
        and edit.get("to") == "video and search warrants involving phones and vehicles"
        for edit in row["body_replacements"]
    )


def test_copyedit_override_repairs_archive_data_and_rendered_html_without_update_semantics(tmp_path):
    root = tmp_path / "site"
    (root / "data").mkdir(parents=True)
    (root / "articles").mkdir()
    (root / "data" / "article-content-overrides.json").write_text(json.dumps(_override_payload()))
    (root / "archive.json").write_text(json.dumps([{
        "slug": SLUG,
        "headline": "Two Miami women charged after tow yard shooting near Stuart sparks school lockout",
        "body": f"Opening paragraph.\n\n{OLD}\n\nClosing paragraph.",
        "published": "Fri, 02 Oct 2026 22:00:00 -0400",
    }]))
    (root / "data.json").write_text(json.dumps({
        "items": [{
            "slug": SLUG,
            "body": f"Opening paragraph.\n\n{OLD}\n\nClosing paragraph.",
        }]
    }))
    html_old = OLD.replace("'", "&#x27;")
    page = root / "articles" / f"{SLUG}.html"
    page.write_text(
        '<html><head><title>Story | Treasure Coast Today</title></head><body>'
        '<h1 class="article-headline">Story</h1>'
        f'<div class="article-body"><p>Opening paragraph.</p><p>{html_old}</p><p>Closing paragraph.</p></div>'
        '<div class="article-share">share</div></body></html>'
    )

    assert generate._apply_article_content_overrides_to_outputs(root) == 1

    archive = json.loads((root / "archive.json").read_text())[0]
    assert NEW in archive["body"]
    assert OLD not in archive["body"]
    assert "is_meaningful_update" not in archive
    assert archive["published"] == "Fri, 02 Oct 2026 22:00:00 -0400"

    data = json.loads((root / "data.json").read_text())
    assert NEW in data["items"][0]["body"]
    assert "is_meaningful_update" not in data["items"][0]

    rendered = page.read_text()
    assert "video and phone and vehicle search warrants" not in rendered
    assert "video and search warrants involving phones and vehicles" in rendered
    assert "article-update" not in rendered
    assert "Original report:" not in rendered

    first = rendered
    assert generate._apply_article_content_overrides_to_outputs(root) == 1
    assert page.read_text() == first


def test_copyedit_override_repairs_live_body_without_marking_meaningful_update():
    item = {
        "slug": SLUG,
        "headline": "Two Miami women charged after tow yard shooting near Stuart sparks school lockout",
        "body": f"Opening paragraph.\n\n{OLD}",
    }
    categories = [{"category_key": "crime", "hero": item, "cards": []}]
    overrides = _override_payload()["overrides"]

    assert generate._apply_article_content_overrides_to_categories(categories, overrides=overrides) == 1
    assert NEW in item["body"]
    assert OLD not in item["body"]
    assert "is_meaningful_update" not in item
    assert "update_status" not in item
