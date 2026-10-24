"""Content regressions for the retired Oct. 24–25 weekend roundup fixture."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEEKEND_FIXTURE = ROOT / "tests" / "fixtures" / "weekend_top_five_oct_24_25_2026.json"
TARGET_ID = "treasure-coast-top-five-weekend-2026-10-24-25"


def target():
    """Test the historical guide independently of the current editorial queue."""
    article = json.loads(WEEKEND_FIXTURE.read_text(encoding="utf-8"))
    assert article.get("custom_id") == TARGET_ID
    return article


def test_historical_roundup_has_correct_identity_and_metadata():
    a = target()
    assert a["slug"] == "2026-10-21-treasure-coast-weekend-events-oct-24-25"
    assert a["publish_on"] == "2026-10-21"
    assert a["category"] == "things_to_do"
    assert not a["force_hero"] and not a["is_breaking"]
    assert a["expires"] == "2026-10-26"


def test_five_unique_sourced_events_spread_across_both_days():
    body = target()["body"]
    assert len(re.findall(r"(?m)^## [1-5]\. ", body)) == 5
    assert body.count("**When:** Saturday, Oct. 24") == 3
    assert body.count("**When:** Sunday, Oct. 25") == 2
    for title in (
        "Indian River Lagoon Science Festival", "Hobgoblins on Main Street",
        "IL Merchato Fall-O-Ween Market", "Sunday Jazz in the Park",
        "Going Batty Full Moon Hike",
    ):
        assert title in body
    for url in (
        "https://visitstlucie.com/event/2026-indian-river-lagoon-science-festival/",
        "https://stuartmainstreet.org/events/hobgoblins-on-main/",
        "https://traditionfl.com/events/il-merchato-fall-o-ween-market/",
        "https://www.eventbrite.com/e/sunday-jazz-in-the-park-tickets-2003268022582",
        "https://visitstlucie.com/event/going-batty-full-moon-hike/",
    ):
        assert url in body


def test_science_festival_venue_hike_age_and_honest_pricing():
    body = target()["body"]
    assert "Museum Pointe Park" in body
    assert "**Important location change:**" in body
    assert "ages 8 and older" in body
    assert "Check the organizer for registration and participation details" in body


def test_historical_roundup_not_required_in_active_editor_queue():
    # A new custom submission replaces the queue. Old editions are tested
    # through fixtures, not kept in custom_articles.json to satisfy tests.
    queued = json.loads((ROOT / "custom_articles.json").read_text(encoding="utf-8"))
    assert isinstance(queued, list)
    ids = [x.get("custom_id") for x in queued]
    assert len(ids) == len(set(ids))
    assert TARGET_ID not in ids
