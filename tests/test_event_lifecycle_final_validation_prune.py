"""Prevent slow GitHub Actions runs from crossing event-retention cutoff after build."""

import json
from pathlib import Path

import pytest

from scripts import build_audience_features as features


END_AT = "2026-09-21T15:00:00-04:00"
BLOOD_DRIVE = "/events/406c44c8f9af846b22-blood-drive-with-oneblood.html"


def _make_root(tmp_path, monkeypatch, *, events=None, retained_paths=None):
    (tmp_path / "data").mkdir()
    (tmp_path / "events").mkdir()
    (tmp_path / "articles").mkdir()
    (tmp_path / "data" / "events.json").write_text(
        json.dumps({"schema_version": 1, "events": events if events is not None else []}),
        encoding="utf-8",
    )
    (tmp_path / "data" / "events-retention.json").write_text(
        json.dumps({"schema_version": 1, "retain_ids": [], "retain_paths": retained_paths or []}),
        encoding="utf-8",
    )
    (tmp_path / "sitemap.xml").write_text(
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        '<url><loc>https://treasurecoast.today/events.html</loc></url>'
        '</urlset>', encoding="utf-8",
    )
    monkeypatch.setattr(features, "ROOT", tmp_path)


def _event_page(root, detail, *, end=END_AT, known=True, ended=True):
    path = root / detail.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = '<html><head>'
    if known:
        text += f'<meta name="tct-event-lifecycle-end" content="{end}">'
    if ended:
        text += '<meta name="robots" content="noindex,follow">'
    text += '</head><body>'
    if ended:
        text += '<p data-tct-event-ended>This event has ended.</p>'
    text += '</body></html>'
    path.write_text(text, encoding="utf-8")
    return path


def test_oct21_blood_drive_crosses_30_day_cutoff_between_build_and_validation(tmp_path, monkeypatch):
    _make_root(tmp_path, monkeypatch)
    old = _event_page(tmp_path, BLOOD_DRIVE)
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-10-21T14:59:59-04:00")
    assert features.prune_expired_event_detail_pages()["removed"] == 0
    assert old.exists()
    features.validate_event_detail_lifecycle()

    # Long running update crosses the deadline between initial build and final
    # SEO validation. Validation must still detect the violation before pruning.
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-10-21T15:00:01-04:00")
    with pytest.raises(RuntimeError, match="expired event page still exists after grace period"):
        features.validate_event_detail_lifecycle()

    report = features.prune_expired_event_detail_pages()
    assert report["removed"] == 1
    assert not old.exists()
    features.validate_event_detail_lifecycle()
    assert features.prune_expired_event_detail_pages()["removed"] == 0


def test_final_pass_never_deletes_active_retained_legacy_or_recently_ended(tmp_path, monkeypatch):
    active = "/events/active.html"
    retained = "/events/retained.html"
    legacy = "/events/legacy.html"
    recent = "/events/recent.html"
    future = "/events/future.html"
    _make_root(tmp_path, monkeypatch, events=[{"detail_url": active}], retained_paths=[retained])
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-10-21T15:32:00-04:00")
    paths = [
        _event_page(tmp_path, active),
        _event_page(tmp_path, retained),
        _event_page(tmp_path, legacy, known=False),
        _event_page(tmp_path, recent, end="2026-10-01T15:00:00-04:00"),
        _event_page(tmp_path, future, end="2026-11-01T15:00:00-04:00", ended=False),
    ]
    article = tmp_path / "articles" / "unrelated-story.html"
    article.write_text("<html>do not touch</html>", encoding="utf-8")
    before = {p: p.read_bytes() for p in paths}
    result = features.prune_expired_event_detail_pages()
    assert result["removed"] == 0
    for p in paths:
        assert p.read_bytes() == before[p]
    assert article.read_text() == "<html>do not touch</html>"


def test_final_pass_removes_stale_sitemap_event_url_without_touching_normal_urls(tmp_path, monkeypatch):
    _make_root(tmp_path, monkeypatch)
    _event_page(tmp_path, BLOOD_DRIVE)
    sitemap = tmp_path / "sitemap.xml"
    text = sitemap.read_text()
    sitemap.write_text(text.replace(
        "</urlset>",
        f'<url><loc>https://treasurecoast.today{BLOOD_DRIVE}</loc></url>'
        '<url><loc>https://treasurecoast.today/articles/unrelated-story.html</loc></url></urlset>'
    ), encoding="utf-8")
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-10-21T15:32:00-04:00")
    assert features.prune_expired_event_detail_pages()["removed"] == 1
    result = sitemap.read_text()
    assert f"https://treasurecoast.today{BLOOD_DRIVE}" not in result
    assert "https://treasurecoast.today/articles/unrelated-story.html" in result
    assert "https://treasurecoast.today/events.html" in result
    features.validate_event_detail_lifecycle()


def test_final_pass_refuses_to_prune_when_event_feed_missing_or_malformed(tmp_path, monkeypatch):
    _make_root(tmp_path, monkeypatch)
    page = _event_page(tmp_path, BLOOD_DRIVE)
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-10-21T15:32:00-04:00")
    (tmp_path / "data" / "events.json").write_text('{}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="requires a valid events.json"):
        features.prune_expired_event_detail_pages()
    assert page.exists()


def test_update_workflow_prunes_just_before_final_seo_and_lifecycle_validation():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "update.yml").read_text()
    final = workflow.split("- name: Validate final SEO and audience contracts", 1)[1]
    pos_cleanup = final.index("python scripts/build_audience_features.py --prune-expired-events")
    pos_seo = final.index("python scripts/validate_seo_contracts.py")
    pos_lifecycle = final.index("python scripts/build_audience_features.py --validate-only")
    assert pos_cleanup < pos_seo < pos_lifecycle


def test_independent_event_workflow_prunes_before_both_lifecycle_checks():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "update-events.yml").read_text()
    parts = workflow.split("python scripts/build_audience_features.py --prune-expired-events")
    assert len(parts) == 3
    for following in parts[1:]:
        assert following.lstrip().startswith("python scripts/build_audience_features.py --validate-events-only")


def test_explicit_retained_event_id_survives_expired_sweep(tmp_path, monkeypatch):
    _make_root(tmp_path, monkeypatch)
    detail = BLOOD_DRIVE
    page = _event_page(tmp_path, detail)
    text = page.read_text()
    text = text.replace('</head>', '<meta name="tct-event-id" content="406c44c8f9af846b22"></head>')
    page.write_text(text)
    (tmp_path / "data" / "events-retention.json").write_text(
        json.dumps({"schema_version": 1, "retain_ids": ["406c44c8f9af846b22"], "retain_paths": []}),
        encoding="utf-8",
    )
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-10-21T15:32:00-04:00")
    assert features.prune_expired_event_detail_pages()["removed"] == 0
    assert page.exists()


def test_prune_expired_events_cli_runs_without_rebuilding_pages(tmp_path, monkeypatch, capsys):
    _make_root(tmp_path, monkeypatch)
    expired = _event_page(tmp_path, BLOOD_DRIVE)
    monkeypatch.setenv("TCT_EVENTS_NOW", "2026-10-21T15:32:00-04:00")
    assert features.main(["--prune-expired-events"]) == 0
    assert not expired.exists()
    output = capsys.readouterr().out
    assert '"removed": 1' in output
