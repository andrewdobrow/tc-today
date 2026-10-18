"""A quiet news day must never repromote a week-old, highly ranked story."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import pytest


def _load_generate():
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_recent_fallback_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _item(title, now, age_hours, urgency=6, *, forced=False, updated=False):
    published = (now - timedelta(hours=age_hours)).isoformat()
    result = {
        "headline": title,
        "teaser": f"{title}. Reporting for Port St. Lucie residents.",
        "body": f"{title}. Reporting for Port St. Lucie residents. " * 45,
        "canonical_slug": title.lower().replace(" ", "-"),
        "canonical_first_published_at": published,
        "ranking_eligible": True,
        "urgency_score": urgency,
        "force_hero": forced,
    }
    if updated:
        result.update({
            "canonical_first_published_at": (now - timedelta(days=19)).isoformat(),
            "canonical_last_material_update_at": published,
            "meaningful_update_validated": True,
        })
    return result


def _category(key, item):
    return {"category_key": key, "category_label": key, "hero": item, "cards": []}


def _clock(monkeypatch, module, when):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return when.astimezone(tz) if tz else when.replace(tzinfo=None)
    monkeypatch.setattr(module, "datetime", FixedDatetime)


def test_newer_story_beats_seven_day_old_custom_hero_on_quiet_sunday(monkeypatch):
    g = _load_generate()
    now = datetime(2026, 10, 18, 18, 38, tzinfo=timezone.utc)
    _clock(monkeypatch, g, now)
    week_old = _item("EPA controversy follow up", now, 7 * 24, urgency=10, updated=True)
    week_old["is_custom"] = True
    yesterday = _item("Fort Pierce standoff resolved", now, 22, urgency=6)
    categories = [_category("business", week_old), _category("st_lucie", yesterday)]
    chosen = g.select_front_page_hero(categories, deterministic_only=True)
    assert chosen["hero"]["headline"] == "Fort Pierce standoff resolved"
    assert g.FRONT_PAGE_HERO_AUDIT["selection_reason"] == "recent_canonical_fallback_48h"


def test_expired_force_hero_cannot_jump_ahead_of_new_story(monkeypatch):
    g = _load_generate()
    now = datetime(2026, 10, 18, 18, 38, tzinfo=timezone.utc)
    _clock(monkeypatch, g, now)
    week_old = _item("Last weekend guide", now, 9 * 24, urgency=10, forced=True)
    latest = _item("Port St. Lucie traffic update", now, 2, urgency=4)
    chosen = g.select_front_page_hero([_category("things_to_do", week_old), _category("st_lucie", latest)], deterministic_only=True)
    assert chosen["hero"]["headline"] == "Port St. Lucie traffic update"


def test_previous_day_always_beats_two_days_ago_in_recent_fallback(monkeypatch):
    g = _load_generate()
    now = datetime(2026, 10, 18, 18, 38, tzinfo=timezone.utc)
    _clock(monkeypatch, g, now)
    old = _item("Port St. Lucie big project", now, 44, urgency=10)
    newer = _item("Martin County police update", now, 25, urgency=3)
    chosen = g.select_front_page_hero([_category("business", old), _category("martin", newer)], deterministic_only=True)
    assert chosen["hero"]["headline"] == "Martin County police update"


def test_all_old_category_stories_wait_for_post_archive_recovery(monkeypatch):
    g = _load_generate()
    now = datetime(2026, 10, 18, 18, 38, tzinfo=timezone.utc)
    _clock(monkeypatch, g, now)
    week_old = _item("EPA controversy follow up", now, 7 * 24, urgency=10)
    four_days_old = _item("Local council story", now, 4 * 24, urgency=8)
    chosen = g.select_front_page_hero(
        [_category("business", week_old), _category("st_lucie", four_days_old)],
        deterministic_only=True,
    )
    assert chosen is not None
    assert g.FRONT_PAGE_HERO_AUDIT["selection_reason"] == (
        "provisional_pending_full_archive_freshness_recovery"
    )
    # This provisional selection is never enough to publish: after write_archives
    # the final 72h gate still checks the full archive and refuses a stale hero.


def test_final_barrier_checks_post_binding_age(monkeypatch, tmp_path):
    g = _load_generate()
    now = datetime(2026, 10, 18, 18, 38, tzinfo=timezone.utc)
    _clock(monkeypatch, g, now)
    g.CANONICAL_HERO_FRESHNESS_REPORT_PATH = tmp_path / 'contract.json'
    old = _item('EPA controversy follow up', now, 7 * 24, urgency=10, updated=True)
    new = _item('Fort Pierce standoff resolved', now, 22, urgency=6)
    categories = [_category('business',old),_category('st_lucie',new)]
    selected = g.enforce_final_canonical_hero_freshness(categories, categories[0], tmp_path)
    assert selected['hero']['headline'] == 'Fort Pierce standoff resolved'
    assert 'passed' in (tmp_path/'contract.json').read_text()
