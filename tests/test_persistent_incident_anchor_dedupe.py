import importlib.util
import os
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
            self.messages = types.SimpleNamespace(create=lambda *a, **k: None)
    anthropic.Anthropic = _Anthropic
    sys.modules["anthropic"] = anthropic
if "json_repair" not in sys.modules:
    json_repair = types.ModuleType("json_repair")
    json_repair.repair_json = lambda value, **kwargs: value
    sys.modules["json_repair"] = json_repair
os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")


def _load_generate():
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_incident_anchor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_infant_death_headline_variants_share_persistent_event_key():
    g = _load_generate()
    variants = [
        "3 arrested in death of 3-month-old in St. Lucie County from dehydration and malnutrition",
        "Three arrested after 3-month-old dies from dehydration and malnutrition in Fort Pierce",
        "Three arrested after 3-month-old dies from severe dehydration and malnutrition in Fort Pierce",
    ]
    keys = {g._known_event_key(value) for value in variants}
    assert keys == {"2025-08-fort-pierce-infant-death-arrests"}


def test_martin_fire_tax_variants_share_persistent_event_key():
    g = _load_generate()
    variants = [
        "Martin County Fire Rescue faces $16.5M loss, 116 job cuts if property tax reform passes",
        "Property tax reform on November ballot could force closure of Martin County fire stations",
    ]
    keys = {g._known_event_key(value) for value in variants}
    assert keys == {"2026-07-martin-fire-rescue-property-tax-impact"}


def test_incident_anchor_resolves_existing_archive_before_new_slug():
    g = _load_generate()
    archive = [{
        "slug": g.INFANT_DEATH_CANONICAL_SLUG,
        "headline": "3 arrested in death of 3-month-old in St. Lucie County from dehydration and malnutrition",
        "teaser": "Three caregivers face charges after an infant died from dehydration and malnutrition.",
    }]
    match = g.find_matching_entry(
        "Three arrested after 3-month-old dies from severe dehydration and malnutrition in Fort Pierce",
        archive,
    )
    assert match["slug"] == g.INFANT_DEATH_CANONICAL_SLUG


def test_unrelated_infant_or_fire_stories_do_not_share_keys():
    g = _load_generate()
    assert g._known_event_key("Infant hospitalized after crash in Martin County") == ""
    assert g._known_event_key("Martin County firefighters rescue dog from canal") == ""
