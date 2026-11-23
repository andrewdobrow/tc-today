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
from tct_engine.article_prose_policy import _split_sentences


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


TRAIN_SLUG = "2026-11-22-pedestrian-killed-in-fort-pierce-train-incident-seaway-drive-crossing-blocked"
MISSING_ST = "with assistance from the Lucie County Sheriff’s Office."
CORRECT_ST = "with assistance from the St. Lucie County Sheriff’s Office."


def test_train_sheriff_copyedit_is_source_scoped_and_preserves_date():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "data" / "article-content-overrides.json").read_text())
    override = payload["overrides"][TRAIN_SLUG]
    assert override["mark_meaningful_update"] is False
    assert {"from": MISSING_ST, "to": CORRECT_ST} in override["body_replacements"]
    page = (root / "articles" / f"{TRAIN_SLUG}.html").read_text()
    assert CORRECT_ST in page
    assert MISSING_ST not in page
    assert "Published November 22, 2026" in page


def test_train_sheriff_copyedit_survives_full_generation_overrides(tmp_path):
    root = tmp_path
    articles = root / "articles"
    data_dir = root / "data"
    articles.mkdir()
    data_dir.mkdir()
    override = {
        "version": 1,
        "overrides": {
            TRAIN_SLUG: {
                "body_replacements": [{"from": MISSING_ST, "to": CORRECT_ST}],
                "mark_meaningful_update": False,
                "update_status": "copyedit_correction",
            }
        },
    }
    (data_dir / "article-content-overrides.json").write_text(json.dumps(override))
    (root / "archive.json").write_text(json.dumps([{
        "slug": TRAIN_SLUG, "headline": "Fort Pierce train incident",
        "body": f"Fort Pierce police are investigating, {MISSING_ST}",
        "published": "Sun, 22 Nov 2026 11:47:51 -0500",
    }]))
    article = articles / f"{TRAIN_SLUG}.html"
    article.write_text(
        '<html><head><title>Fort Pierce train incident</title></head><body>'
        '<div class="article-body"><p>Fort Pierce police are investigating, '
        + MISSING_ST + '</p></div><div class="article-share"></div></body></html>'
    )
    assert generate._apply_article_content_overrides_to_outputs(root) == 1
    after = article.read_text()
    assert CORRECT_ST in after
    assert MISSING_ST not in after
    row = json.loads((root / "archive.json").read_text())[0]
    assert CORRECT_ST in row["body"]
    assert row["published"] == "Sun, 22 Nov 2026 11:47:51 -0500"
    assert row.get("meaningful_update_validated") is not True


def test_publisher_source_extraction_does_not_drop_st_from_sheriff_agency():
    original = (
        "The incident was reported at about 7:16 a.m. Nov. 22. "
        "The St. Lucie County Sheriff’s Office said it was assisting the "
        "Fort Pierce Police Department, the lead agency investigating."
    )
    sentences = _split_sentences(original)
    assert len(sentences) == 2
    assert sentences[0].endswith("7:16 a.m. Nov. 22.")
    assert sentences[1].startswith("The St. Lucie County Sheriff’s Office")
    assert "The St." not in sentences
    cleaned = " ".join(s for s in sentences if len(s.strip()) > 25)
    assert "The St. Lucie County Sheriff’s Office said" in cleaned


def test_publisher_sentence_split_still_separates_genuine_sentences():
    raw = (
        "Police closed the crossing after a train struck a pedestrian. "
        "The St. Lucie County Sheriff’s Office assisted investigators. "
        "Traffic was diverted to another bridge."
    )
    sentences = _split_sentences(raw)
    assert len(sentences) == 3
    assert sentences[1].startswith("The St. Lucie County")
