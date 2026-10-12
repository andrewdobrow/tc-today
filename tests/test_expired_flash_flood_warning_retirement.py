"""Editorial correction: Oct. 11 NWS warning expired before TCT publication."""
import importlib
import json
import os
import sys
import types
from pathlib import Path

TARGET = "2026-10-11-flash-flood-warning-hits-stuart-hobe-sound-palm-city-and-coastal-martin-county"

def _generate():
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
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")

def _fixture_root(tmp_path):
    source = Path(__file__).resolve().parents[1] / "data/source-retirement-editor-overrides.json"
    dest = tmp_path / "data/source-retirement-editor-overrides.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(source.read_bytes())
    return tmp_path

def test_exact_slug_is_retired_and_prior_editor_policies_remain():
    generate = _generate()
    # Other editorial tests may temporarily repoint the generator output directory.
    # The policy contract must read from the repository, not leaked test state.
    repo_root = Path(__file__).resolve().parents[1]
    policies = generate._source_retirement_policy_by_slug(output_root=repo_root)
    assert policies[TARGET]["action"] == "retire"
    assert policies[TARGET]["target_path"] == "/archive.html"
    assert not policies[TARGET].get("source_domain")  # no accidental domain-wide exclusion
    assert "2026-10-08-vero-beach-mermaid-brandee-anthony-turns-diving-skills-into-magical-underwater-e" in policies

def test_retirement_policy_lookup_ignores_leaked_output_dir(tmp_path, monkeypatch):
    """Regression: earlier tests can repoint OUTPUT_DIR without restoring it."""
    generate = _generate()
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)
    repo_root = Path(__file__).resolve().parents[1]
    policies = generate._source_retirement_policy_by_slug(output_root=repo_root)
    assert policies[TARGET]["action"] == "retire"

def test_archive_retirement_removes_only_expired_warning_and_preserves_other_articles(tmp_path):
    generate = _generate()
    root = _fixture_root(tmp_path)
    unaffected = "2026-10-11-valid-martin-county-story"
    archive = [
        {"slug":TARGET,"headline":"Flash Flood Warning Hits Stuart, Hobe Sound, Palm City and Coastal Martin County","category_key":"martin"},
        {"slug":unaffected,"headline":"Unrelated legitimate news","category_key":"martin"},
    ]
    kept, redirects, report = generate.apply_source_retirement_cleanup_to_archive(
        archive, root / "articles", output_root=root
    )
    assert [e["slug"] for e in kept] == [unaffected]
    assert redirects == []
    assert report["retired_count"] == 1
    page = (root / "articles" / f"{TARGET}.html").read_text(encoding="utf8")
    assert 'name="robots" content="noindex,nofollow"' in page
    assert 'This article has been retired' in page
    assert 'https://treasurecoast.today/archive.html' in page
    assert unaffected not in page

def test_live_cards_and_hero_remove_only_expired_slug(tmp_path):
    generate = _generate()
    root = _fixture_root(tmp_path)
    good = {"slug":"2026-10-11-valid-martin-county-story","headline":"Valid local story"}
    gone = {"link":f"https://treasurecoast.today/articles/{TARGET}.html","headline":"Expired warning"}
    cats = [{"category_key":"martin","hero":gone,"cards":[good,dict(gone)]}]
    removed = generate.apply_source_retirements_to_live(cats,output_root=root)
    assert removed == 2
    assert cats[0]["hero"] == good
    assert cats[0]["cards"] == []

def test_recovery_and_feed_archive_views_filter_exact_slug(tmp_path):
    generate = _generate()
    root = _fixture_root(tmp_path)
    rows = [{"slug":TARGET},{"slug":"2026-10-11-other-story"}]
    assert generate._filter_source_retirement_archive_view(rows,root)==[rows[1]]


def test_repeated_expired_warning_blocked_under_a_new_daily_slug(tmp_path):
    generate = _generate()
    root = _fixture_root(tmp_path)
    policies = generate._source_retirement_policy_by_slug(output_root=root)
    oct12 = TARGET.replace("2026-10-11", "2026-10-12")
    oct13 = TARGET.replace("2026-10-11", "2026-10-13")
    oct25 = TARGET.replace("2026-10-11", "2026-10-25")
    oct26 = TARGET.replace("2026-10-11", "2026-10-26")
    assert generate._source_retirement_policy_for_slug(TARGET, policies)
    assert generate._source_retirement_policy_for_slug(oct12, policies)
    assert generate._source_retirement_policy_for_slug(oct13, policies)
    assert generate._source_retirement_policy_for_slug(oct25, policies)
    assert generate._source_retirement_policy_for_slug(oct26, policies) is None
    assert generate._source_retirement_policy_for_slug(
        "2026-10-12-flooding-damages-homes-after-martin-county-storm", policies
    ) is None
    assert generate._source_retirement_policy_for_slug(
        "2026-10-12-new-flash-flood-warning-issued-for-saint-lucie-county", policies
    ) is None

    entry = {"slug": oct12, "headline": "Flash Flood Warning Hits Stuart, Hobe Sound, Palm City and Coastal Martin County"}
    new_entry = {"slug": "2026-10-12-martin-county-recovery-efforts-after-flooding", "headline": "Cleanup continues"}
    kept, redirects, report = generate.apply_source_retirement_cleanup_to_archive(
        [entry, new_entry], root / "articles", output_root=root
    )
    assert kept == [new_entry]
    assert redirects == []
    assert report["retired_count"] == 1
    assert 'name="robots" content="noindex,nofollow"' in (root / "articles" / (oct12 + ".html")).read_text()
    assert generate._filter_source_retirement_archive_view([entry,new_entry],root) == [new_entry]


def test_repeated_warning_removed_from_live_cards_even_without_slug(tmp_path):
    generate = _generate()
    root = _fixture_root(tmp_path)
    oct13 = TARGET.replace("2026-10-11", "2026-10-13")
    old = {"headline":"Expired warning", "link":f"https://treasurecoast.today/articles/{oct13}.html"}
    followup = {"headline":"Legitimate flood follow-up", "slug":"2026-10-13-evacuation-centers-update"}
    categories=[{"category_key":"martin", "hero":old, "cards":[followup,dict(old)]}]
    assert generate.apply_source_retirements_to_live(categories,output_root=root)==2
    assert categories[0]["hero"] == followup
    assert categories[0]["cards"] == []
