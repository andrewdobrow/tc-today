import os
import sys
import types
from datetime import datetime, timezone


if "feedparser" not in sys.modules:
    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
    sys.modules["feedparser"] = feedparser

if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class _Anthropic:
        def __init__(self, *args, **kwargs):
            self.messages = types.SimpleNamespace(
                create=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline test"))
            )

    anthropic.Anthropic = _Anthropic
    sys.modules["anthropic"] = anthropic

os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")

from scripts import generate


RUN_DATE = datetime(2026, 7, 28, 12, tzinfo=timezone.utc)
SERIES_PREVIEW_HEADLINE = "Mets back at Clover Park for series vs. Fort Myers"
GENERATED_PREVIEW_HEADLINE = (
    "St. Lucie Mets host Fort Myers for seven-game series at Clover Park starting Tuesday"
)
SERIES_PREVIEW_BODY = (
    "PORT ST. LUCIE, Fla. (July 21, 2026) — The St. Lucie Mets return to Clover "
    "Park from Tuesday-Sunday for a six-day, "
    "seven-game series against the Fort Myers Mighty Mussels. First pitch is "
    "scheduled for 6:05 p.m. Tuesday."
)


def _item(headline=SERIES_PREVIEW_HEADLINE, body=SERIES_PREVIEW_BODY, **updates):
    item = {
        "title": headline,
        "headline": GENERATED_PREVIEW_HEADLINE if headline == SERIES_PREVIEW_HEADLINE else headline,
        "source_title": headline,
        "summary": body,
        "article_text": body,
        "body": body,
        "published": "Tue, 21 Jul 2026 14:00:00 GMT",
        "source_quality": "full",
        "source_word_count": 160,
        "feed_url": "https://news.google.com/rss/search?q=st+lucie+mets",
        "link": "https://www.oursportscentral.com/services/releases/mets-back-at-clover-park/n-6390598",
    }
    item.update(updates)
    return item


def test_exact_fort_myers_series_preview_expires_after_complete_event_window():
    assessment = generate._sports_event_window_assessment(_item(), RUN_DATE)
    assert assessment["is_preview"] is True
    assert assessment["expired"] is True
    assert assessment["reason"] == "sports_event_window_expired"
    assert assessment["event_dates"] == ["2026-07-21", "2026-07-26"]
    assert assessment["event_end_date"] == "2026-07-26"


def test_same_series_preview_remains_eligible_before_final_game():
    assessment = generate._sports_event_window_assessment(
        _item(), datetime(2026, 7, 25, 12, tzinfo=timezone.utc)
    )
    assert assessment["expired"] is False
    assert assessment["reason"] == "event_window_open"



def test_generic_weekday_range_uses_source_publication_date_as_anchor():
    preview = _item(
        headline="Jensen Beach volleyball hosts preseason tournament",
        body=(
            "The Falcons host the tournament from Thursday-Saturday at the school gym."
        ),
        published="Thu, 06 Aug 2026 14:00:00 GMT",
    )
    assessment = generate._sports_event_window_assessment(
        preview, datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
    )
    assert assessment["expired"] is True
    assert assessment["event_dates"] == ["2026-08-06", "2026-08-08"]
    assert assessment["event_end_date"] == "2026-08-08"

def test_future_sports_preview_remains_eligible():
    future = _item(
        headline="St. Lucie Mets host Dunedin for six-game series starting Tuesday",
        body=(
            "The Mets will host Dunedin at Clover Park from Tuesday, August 4 through "
            "Sunday, August 9. Tickets remain available for the homestand."
        ),
        published="Mon, 27 Jul 2026 14:00:00 GMT",
    )
    assessment = generate._sports_event_window_assessment(future, RUN_DATE)
    assert assessment["is_preview"] is True
    assert assessment["expired"] is False
    assert assessment["event_end_date"] == "2026-08-09"


def test_completed_game_recap_is_not_misclassified_by_future_schedule_sentence():
    recap = _item(
        headline="Mets erase 5-0 deficit to beat Mighty Mussels 11-8",
        body=(
            "The St. Lucie Mets rallied for an 11-8 win Sunday, July 26. Conner Ware "
            "struck out eight. They open a road series against Dunedin on Tuesday, July 28."
        ),
        published="Sun, 26 Jul 2026 20:00:00 GMT",
    )
    assessment = generate._sports_event_window_assessment(recap, RUN_DATE)
    assert assessment["is_preview"] is False
    assert assessment["expired"] is False
    assert assessment["reason"] == "not_a_sports_preview"


def test_multiday_preview_with_only_start_date_fails_open_when_end_is_unknown():
    unresolved = _item(
        headline="St. Lucie Mets begin homestand Tuesday",
        body="The St. Lucie Mets begin a seven-game series Tuesday, July 21 at Clover Park.",
    )
    assessment = generate._sports_event_window_assessment(unresolved, RUN_DATE)
    assert assessment["is_preview"] is True
    assert assessment["expired"] is False
    assert assessment["reason"] == "event_end_not_resolved"


def test_custom_sports_preview_is_exempt_from_automatic_expiry():
    assessment = generate._sports_event_window_assessment(
        _item(is_custom=True, authoritative_custom=True), RUN_DATE
    )
    assert assessment["expired"] is False
    assert assessment["reason"] == "custom_article_exempt"


def test_filter_removes_expired_preview_before_sports_fast_recovery():
    kept, rejected = generate._filter_expired_sports_previews(
        "sports", [_item()], RUN_DATE
    )
    assert kept == []
    assert len(rejected) == 1
    assert rejected[0]["headline"] == SERIES_PREVIEW_HEADLINE
    assert rejected[0]["reason"] == "sports_event_window_expired"
    assert rejected[0]["event_end_date"] == "2026-07-26"
    assert generate._sports_zero_candidate_fast_recovery("sports", kept) is True


def test_filter_preserves_valid_result_while_rejecting_expired_preview():
    recap = _item(
        headline="Mets beat Mighty Mussels 11-8 in series finale",
        body="The Mets scored eight runs in the second inning and won 11-8 on July 26.",
    )
    kept, rejected = generate._filter_expired_sports_previews(
        "sports", [_item(), recap], RUN_DATE
    )
    assert kept == [recap]
    assert len(rejected) == 1


def test_archive_recovery_does_not_revive_exact_expired_preview(monkeypatch):
    entry = {
        "slug": "2026-07-28-st-lucie-mets-host-fort-myers-for-seven-game-series",
        "headline": GENERATED_PREVIEW_HEADLINE,
        "source_title": SERIES_PREVIEW_HEADLINE,
        "teaser": "The Mets return to Clover Park for a seven-game series.",
        "category_key": "sports",
        "date": "2026-07-28",
        "first_published": "2026-07-28T04:00:00Z",
    }
    monkeypatch.setattr(
        generate,
        "_archive_article_body",
        lambda candidate: "The archived article contains no reliable source date metadata.",
    )
    assert generate._archive_sports_event_window_expired(entry, RUN_DATE) is True


def test_category_generation_report_counts_expired_sports_previews():
    report = generate._build_category_generation_report([
        {
            "status": "sports_expired_event_preview_archive_recovery",
            "failure_code": "sports_event_window_expired",
            "attempt_count": 0,
            "model_elapsed_seconds": 0,
            "archive_recovery_requested": True,
            "sports_expired_event_preview_count": 1,
        },
        {
            "status": "generated_live",
            "failure_code": "",
            "attempt_count": 1,
            "model_elapsed_seconds": 10,
            "archive_recovery_requested": False,
            "sports_expired_event_preview_count": 0,
        },
    ])
    assert report["schema_version"] == 5
    assert report["summary"]["sports_expired_event_preview_count"] == 1
    assert report["summary"]["model_attempt_count"] == 1
    assert report["summary"]["archive_recovery_requested_count"] == 1


def test_production_hometown_title_suffix_matches_permanent_event_fixture():
    production_item = _item(
        headline=(
            "Mets back at Clover Park for series vs. Fort Myers - "
            "Hometown News Treasure Coast"
        ),
        body=(
            "The St. Lucie Mets are back at Clover Park for a seven-game homestand "
            "against the Fort Myers Mighty Mussels."
        ),
        published="2026-07-28T05:21:13.289639+00:00",
        link=(
            "https://www.hometownnewstc.com/sports/"
            "mets-back-at-clover-park-for-series-vs-fort-myers/"
            "article_5fcaa9df-9494-53df-ad8d-4c96173246f8.html"
        ),
    )
    assessment = generate._sports_event_window_assessment(production_item, RUN_DATE)
    assert assessment["is_preview"] is True
    assert assessment["expired"] is True
    assert assessment["reason"] == "sports_event_window_expired"
    assert assessment["event_dates"] == ["2026-07-21", "2026-07-26"]
    assert assessment["event_end_date"] == "2026-07-26"


def test_second_generated_headline_variant_cannot_return_from_archive(monkeypatch):
    entry = {
        "slug": "2026-07-28-st-lucie-mets-return-to-clover-park-for-seven-game-homestand",
        "headline": (
            "St. Lucie Mets return to Clover Park for seven-game homestand "
            "against Fort Myers"
        ),
        "source_title": "",
        "teaser": "The Mets return to Clover Park for a seven-game homestand.",
        "category_key": "sports",
        "date": "2026-07-28",
        "first_published": "2026-07-28T05:21:13Z",
    }
    monkeypatch.setattr(
        generate,
        "_archive_article_body",
        lambda candidate: "No reliable event date remains in the archived body.",
    )
    assert generate._archive_sports_event_window_expired(entry, RUN_DATE) is True


def test_unrelated_hometown_sports_title_with_publisher_suffix_is_not_fixture_matched():
    unrelated = _item(
        headline=(
            "Mets open August series against Dunedin - Hometown News Treasure Coast"
        ),
        body=(
            "The Mets will host Dunedin from Tuesday, August 4 through Sunday, "
            "August 9 at Clover Park."
        ),
        published="Mon, 27 Jul 2026 14:00:00 GMT",
        link=(
            "https://www.hometownnewstc.com/sports/"
            "mets-open-august-series-against-dunedin/article_future.html"
        ),
    )
    assessment = generate._sports_event_window_assessment(unrelated, RUN_DATE)
    assert assessment["is_preview"] is True
    assert assessment["expired"] is False
    assert assessment["event_end_date"] == "2026-08-09"
