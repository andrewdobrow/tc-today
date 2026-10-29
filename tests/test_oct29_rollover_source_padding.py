"""Real Oct. 29 source-chrome and redundant-prose regressions."""
import json
from pathlib import Path

from scripts import generate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "martin_rollover_padded_oct29_2026.json").read_text(
        encoding="utf-8"
    )
)


def test_sinclair_recommendations_do_not_inflate_short_breaking_source():
    source = {
        "title": FIXTURE["source_title"],
        "source_url": FIXTURE["source_url"],
    }
    focused = generate._focus_extracted_source_text(FIXTURE["source"], source)
    assert focused != FIXTURE["source"]
    assert "single-vehicle rollover" in focused
    assert "SW Martin Highway" in focused
    assert "expect delays" in focused
    assert "Florida attorney general" not in focused
    assert "Sheriff: Armed Army" not in focused
    assert "NEWS IN PHOTOS" not in focused
    assert 50 <= generate._word_count(focused) <= 110


def test_without_verified_sinclair_template_normal_articles_remain_unchanged():
    text = FIXTURE["source"]
    original = generate._focus_extracted_source_text(
        text, {"title": FIXTURE["source_title"].replace("cw34.com", "news-site.example")}
    )
    assert original == text
    no_marker = text.replace("NEWS IN PHOTOS:", "OTHER CONTENT:")
    assert generate._focus_extracted_source_text(
        no_marker, {"title": FIXTURE["source_title"]}
    ) == no_marker


def test_oct29_padded_model_draft_fails_live_copydesk_gate():
    body = FIXTURE["original_generated_body"]
    issue = generate._article_padding_issue(body)
    assert issue and issue["code"] == "low_information_repetition"
    diagnostics = generate._article_copydesk_diagnostics({
        "headline": "One hospitalized after rollover on SW Martin Highway in Martin County",
        "body": body,
        "teaser": "One person was hospitalized after a crash.",
    })
    assert diagnostics["passed"] is False
    assert "low_information_repetition" in {v["code"] for v in diagnostics["issues"]}


def test_short_verified_breaking_brief_is_not_rejected_as_padding():
    body = (
        "One person was hospitalized after a rollover Thursday on SW Martin Highway "
        "in Martin County. The crash occurred near Fox Brown Road.\n\n"
        "Emergency crews and deputies responded. The Sheriff's Office said "
        "drivers should expect delays while the scene was cleared."
    )
    assert generate._article_padding_issue(body) is None
    assert generate._article_copydesk_diagnostics({"headline": "Rollover on highway", "body": body})["passed"]


def test_lengthy_but_information_rich_reporting_passes_redundancy_test():
    paragraphs = [
        "The county commission adopted a two-year road construction plan in a unanimous vote Tuesday, establishing public funding and resurfacing priorities for rural neighborhoods.",
        "Engineers will survey stormwater culverts in the western district beginning in January, with preliminary field reports scheduled for a spring presentation.",
        "The school board approved a separate safety crossing near the elementary campus, allocating $2.4 million for signals, ramps and pedestrian lighting improvements.",
        "Public transit officials said the new commuter service will start with three electric buses operating hourly between the station and the health center.",
        "Residents may submit comments on the proposed environmental assessment through December 12; the county will publish written responses in February.",
        "The final budget also increases firefighter equipment funding, purchasing protective helmets, emergency radios and new training materials for coastal volunteer stations.",
    ]
    body = "\n\n".join(paragraphs)
    assert generate._word_count(body) >= 125
    # Duplication checks must not replace the article's fact checking.
    assert generate._article_padding_issue(body) is None


def test_custom_articles_remain_exempt_from_automated_repetition_gate():
    item = {
        "headline": "Custom report",
        "body": FIXTURE["original_generated_body"],
        "is_custom": True,
    }
    assert generate._article_copydesk_diagnostics(item)["required"] is False


def test_source_constrained_breaking_target_is_still_60_to_160_words():
    item = {"source_quality": "summary", "source_type": "full_source",
            "source_word_count": 65, "urgency_score": 8,
            "published_raw": generate.datetime.now(generate.timezone.utc).isoformat()}
    assert generate._source_constrained_breaking_brief(item)
    assert generate._article_depth_requirements(item)[0] <= 80
