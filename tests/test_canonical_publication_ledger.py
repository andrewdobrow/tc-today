from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tct_engine.incident_identity import incident_anchor_key


TRAFFIC_CANONICAL = (
    "2026-07-29-flashing-traffic-light-at-glades-cut-off-road-still-not-operational-after-6-mont"
)
TRAFFIC_DUPLICATE = (
    "2026-07-30-flashing-traffic-light-at-glades-cut-off-road-still-not-working-six-months-after"
)
TRAFFIC_ANCHOR = (
    "infrastructure-condition:traffic-signal:glades-cut-off-road:nonoperational"
)


def _load_generate(tmp_path=None):
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = ROOT / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_publication_ledger", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    if tmp_path is not None:
        module.OUTPUT_DIR = Path(tmp_path)
    return module


class _IdentityIndex:
    safe_story_ids = frozenset({"story_001294"})
    all_story_ids = frozenset({"story_001294"})

    def resolve(self, item):
        return str(item.get("editorial_story_id") or "")


def _traffic_rows():
    return [
        {
            "slug": TRAFFIC_CANONICAL,
            "headline": (
                "Flashing traffic light at Glades Cut Off Road still not operational "
                "after 6 months"
            ),
            "teaser": (
                "A traffic signal at Glades Cut Off Road remains in flashing mode "
                "six months after installation."
            ),
            "date": "2026-07-29",
            "first_published": "Wed, 29 Jul 2026 17:00:00 -0400",
            "category_key": "st_lucie",
            "editorial_story_id": "story_001294",
            "source_url": (
                "https://www.wptv.com/traffic/traffic-news/"
                "flashing-traffic-light-at-glades-cut-off-road-still-not-fully-operational-after-6-months"
            ),
            "legacy_identity_status": "identified",
            "ranking_eligible": True,
        },
        {
            "slug": TRAFFIC_DUPLICATE,
            "headline": (
                "Flashing traffic light at Glades Cut Off Road still not working "
                "six months after installation"
            ),
            "teaser": (
                "The same Glades Cut Off Road traffic signal remains nonoperational."
            ),
            "date": "2026-07-30",
            "first_published": "Thu, 30 Jul 2026 00:10:00 -0400",
            "category_key": "st_lucie",
            "editorial_story_id": "story_001294",
            "source_url": (
                "https://www.wflx.com/2026/07/29/"
                "flashing-traffic-light-glades-cut-off-road-st-lucie-county-still-not-fully-operational-after-6-months/"
            ),
            "legacy_identity_status": "identified",
            "ranking_eligible": True,
        },
    ]


def test_glades_cut_off_headline_rewrites_share_structured_identity():
    keys = {
        incident_anchor_key(titles=(row["headline"], row["teaser"]))
        for row in _traffic_rows()
    }
    assert keys == {TRAFFIC_ANCHOR}


def test_same_road_crash_does_not_share_infrastructure_condition_identity():
    assert incident_anchor_key(
        titles=("Crash closes Glades Cut Off Road after two vehicles collide",)
    ) == ""


def test_ledger_reconciliation_collapses_traffic_light_urls(tmp_path):
    g = _load_generate(tmp_path)
    rows = _traffic_rows()
    cleaned, redirects, ledger, report = g._reconcile_canonical_publication_ledger(
        rows, _IdentityIndex(), tmp_path
    )

    assert [row["slug"] for row in cleaned] == [TRAFFIC_CANONICAL]
    assert redirects[0]["source_slug"] == TRAFFIC_DUPLICATE
    assert redirects[0]["target_slug"] == TRAFFIC_CANONICAL
    assert report["passed"] is True
    assert report["groups_collapsed"] == 1
    assert ledger["key_to_slug"][f"incident:{TRAFFIC_ANCHOR}"] == TRAFFIC_CANONICAL
    assert ledger["key_to_slug"]["story:story_001294"] == TRAFFIC_CANONICAL


def test_false_headline_slug_quarantine_cannot_force_second_permalink(tmp_path):
    g = _load_generate(tmp_path)
    canonical = _traffic_rows()[0]
    canonical.update({
        "headline": "Flashing traffic light at Glades Cut Off Road still not working",
        "exclude_from_live_recovery": True,
        "ranking_eligible": False,
        "identity_quarantine_reason": "prospective_headline_slug_event_drift",
    })
    cleaned, redirects, ledger, report = g._reconcile_canonical_publication_ledger(
        [canonical], _IdentityIndex(), tmp_path
    )

    assert redirects == []
    assert cleaned[0].get("exclude_from_live_recovery") is None
    assert cleaned[0].get("identity_quarantine_reason") is None
    assert cleaned[0]["ranking_eligible"] is True
    assert report["false_quarantines_repaired"] == 1
    incoming = {
        "headline": "Flashing traffic light at Glades Cut Off Road still not operational",
        "teaser": "The signal remains out of service.",
        "editorial_story_id": "story_001294",
        "_editorial_route": "skip",
    }
    target, basis, keys = g._canonical_publication_ledger_target(
        incoming, ledger, _IdentityIndex()
    )
    assert target["slug"] == TRAFFIC_CANONICAL
    assert "story:story_001294" in keys
    assert basis in {"trusted_persistent_story_id", "exact_structured_incident_key"}


def test_same_persistent_story_update_ignores_cosmetic_permalink_drift():
    g = _load_generate()
    existing = _traffic_rows()[0]
    incoming = {
        "headline": "Flashing traffic light at Glades Cut Off Road still not working",
        "teaser": existing["teaser"],
        "editorial_story_id": "story_001294",
        "_editorial_route": "update_existing",
    }
    passed, reason = g._forward_publication_target_valid(
        incoming, existing, "story_001294", "persistent_story_id"
    )
    assert passed is True
    assert reason == "persistent_story_id"


def test_authoritative_route_marks_update_for_contextual_lead_contract():
    g = _load_generate()
    assert g._source_story_form({
        "headline": "A differently worded headline",
        "_editorial_route": "update_existing",
    }) == "update"


def test_contextless_update_is_rejected_even_when_headline_is_rewritten():
    g = _load_generate()
    item = {
        "headline": "Traffic signal remains offline after six months",
        "story_form": "update",
        "body": (
            "County officials said additional equipment should arrive soon.\n\n"
            "The traffic light at Glades Cut Off Road has remained in flashing mode."
        ),
    }
    source = {
        "title": (
            "Flashing traffic light at Glades Cut Off Road still not working "
            "six months after installation"
        ),
        "article_text": (
            "The traffic light at Glades Cut Off Road has not been fully operational "
            "for six months. County officials now expect new equipment."
        ),
        "_editorial_route": "update_existing",
    }
    diagnostics = g._article_framing_diagnostics(item, source)
    assert diagnostics["passed"] is False
    assert "original_event_context_missing" in diagnostics["missing"]


def test_writer_contains_hard_barrier_before_slug_creation():
    source = (ROOT / "scripts" / "generate.py").read_text(encoding="utf-8")
    barrier = source.index("Recheck immediately before the only slug-creation branch")
    create = source.index("# New story — create new page")
    assert barrier < create
    assert "_canonical_publication_ledger_target" in source[barrier:create]


def test_ledger_report_is_valid_json(tmp_path):
    g = _load_generate(tmp_path)
    g._reconcile_canonical_publication_ledger(
        _traffic_rows(), _IdentityIndex(), tmp_path
    )
    payload = json.loads(
        (tmp_path / "data" / "canonical-publication-ledger.json").read_text()
    )
    assert payload["version"] == "1.1"
    assert payload["passed"] is True


def test_generic_same_event_fallback_blocks_fragmented_story_ids():
    g = _load_generate()
    existing = {
        "slug": "2026-07-20-st-lucie-school-board-approves-new-attendance-zones",
        "headline": "St. Lucie School Board approves new attendance zones for 2026-27 school year",
        "teaser": "The St. Lucie County School Board approved new attendance zones for the 2026-27 school year Tuesday.",
        "date": "2026-07-20",
        "editorial_story_id": "story-old-fragment",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    incoming = {
        "headline": "New St. Lucie County school attendance zones approved for 2026-27",
        "teaser": "School Board members voted Tuesday to approve the new St. Lucie County attendance zones for 2026-27.",
        "date": "2026-07-21",
        "editorial_story_id": "story-new-fragment",
        "_editorial_route": "generate_new",
    }
    identity_index = types.SimpleNamespace(
        safe_story_ids={"story-old-fragment", "story-new-fragment"}
    )
    ledger = g._build_canonical_publication_ledger([existing], identity_index)

    target, basis, _keys = g._canonical_publication_ledger_target(
        incoming, ledger, identity_index
    )

    assert target["slug"] == existing["slug"]
    assert basis == "event-identity-authority:governing_body_plus_policy_subject"


def test_generic_same_event_fallback_rejects_same_board_different_decision():
    g = _load_generate()
    attendance = {
        "headline": "St. Lucie School Board approves new attendance zones for 2026-27 school year",
        "teaser": "The St. Lucie County School Board approved new attendance zones for the 2026-27 school year Tuesday.",
        "date": "2026-07-20",
    }
    raises = {
        "headline": "St. Lucie School Board approves teacher raises for 2026-27 school year",
        "teaser": "The board approved teacher salary increases for the next school year.",
        "date": "2026-07-21",
    }

    assert g._generic_same_event_publication_match(attendance, raises) is False


def test_historical_generic_same_event_reconciliation_collapses_fragmented_ids(tmp_path):
    g = _load_generate()
    old = {
        "slug": "2026-07-20-st-lucie-school-board-approves-new-attendance-zones",
        "headline": "St. Lucie School Board approves new attendance zones for 2026-27 school year",
        "teaser": "The St. Lucie County School Board approved new attendance zones for the 2026-27 school year Tuesday.",
        "date": "2026-07-20",
        "editorial_story_id": "story-old-fragment",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    duplicate = {
        "slug": "2026-07-21-new-st-lucie-county-school-attendance-zones-approved",
        "headline": "New St. Lucie County school attendance zones approved for 2026-27",
        "teaser": "School Board members voted Tuesday to approve the new St. Lucie County attendance zones for 2026-27.",
        "date": "2026-07-21",
        "editorial_story_id": "story-new-fragment",
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
    }
    identity_index = types.SimpleNamespace(
        safe_story_ids={"story-old-fragment", "story-new-fragment"}
    )

    cleaned, redirects, _ledger, report = g._reconcile_canonical_publication_ledger(
        [old, duplicate], identity_index, tmp_path
    )

    assert [row["slug"] for row in cleaned] == [old["slug"]]
    assert redirects[0]["source_slug"] == duplicate["slug"]
    assert redirects[0]["target_slug"] == old["slug"]
    assert report["generic_same_event_edges"] == 1
