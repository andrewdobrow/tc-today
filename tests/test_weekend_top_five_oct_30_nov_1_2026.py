"""Independent regression for TCT's October 30–November 1, 2026 weekend guide.

Keep the historical fixture separate from the rotating custom_articles.json queue.
The queue must be allowed to move on to the next custom scoop or roundup.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "custom_articles.json"
FIXTURE = ROOT / "tests/fixtures/weekend_top_five_oct_30_nov_1_2026.json"
CUSTOM_ID = "treasure-coast-top-five-weekend-2026-10-30-11-01"
SLUG = "2026-10-28-treasure-coast-weekend-events-oct-30-nov-1"
IMAGE = "https://treasurecoast.today/images/fall-fun-fest.jpg"


def guide():
    item = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert item["custom_id"] == CUSTOM_ID
    return item


def test_guide_identity_date_expiration_and_editor_selected_image():
    item = guide()
    assert item["slug"] == SLUG
    assert item["image_url"] == IMAGE
    assert item["publish_on"] == "2026-10-28"
    assert item["expires"] == "2026-11-02"
    assert item["category"] == "things_to_do"
    assert item["is_breaking"] is False
    assert item["force_hero"] is False
    assert item["pin_position"] is None


def test_five_distinct_events_cover_friday_saturday_and_sunday():
    body = guide()["body"]
    headings = re.findall(r"(?m)^## ([1-5])\. (.+)$", body)
    assert [number for number, _ in headings] == ["1", "2", "3", "4", "5"]
    assert body.count("**When:** Friday, Oct. 30") == 2
    assert body.count("**When:** Saturday, Oct. 31") == 2
    assert body.count("**When:** Sunday, Nov. 1") == 1
    for name in (
        "Fall Fun Fest", "Creepy Creature Feature", "Jake and Elwood Blues Revue",
        "Hot Sauce Moon", "Cars of Our Lives Show",
    ):
        assert name in body
    for locality in ("Port St. Lucie", "Hobe Sound", "Fort Pierce", "Vero Beach", "Stuart"):
        assert locality in body


def test_event_sources_are_real_distinct_organizer_links():
    body = guide()["body"]
    required = (
        "https://www.midfloridaeventcenter.com/List-of-Events",
        "https://discovermartin.com/event/creepy-creature-feature/",
        "https://visitstlucie.com/event/the-jake-and-elwood-blues-revue-soul-show-plus-blues-brothers-look-alike-contest-at-3pm-for-halloween/",
        "https://www.riversidetheatre.com/loop-music-calendar/2026/2/19/hot-sauce-moon-473x6",
        "https://discovermartin.com/event/cars-of-our-lives-show-2026/",
    )
    for link in required:
        assert f"]({link})" in body
    assert len(set(required)) == 5
    assert "**Admission:** Free" in body
    assert "**Admission:** $18.50" in body
    assert "**Admission:** Not specified" in body


def test_this_guide_matches_active_queue_if_it_is_still_queued():
    """Check active release accuracy without blocking future custom articles."""
    if not QUEUE.exists():
        return
    rows = json.loads(QUEUE.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    matches = [row for row in rows if row.get("custom_id") == CUSTOM_ID]
    if matches:
        assert len(matches) == 1
        assert matches[0] == guide()
        assert matches[0]["image_url"] == IMAGE
    # When the queue rotates, the historical fixture keeps these tests useful.
