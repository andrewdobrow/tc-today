from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = ROOT / "scripts" / "update_missing_persons.py"
    spec = importlib.util.spec_from_file_location("tct_missing_persons_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _result_row(name: str, missing: str, city: str, record_id: str, fin: str) -> str:
    return f"""
    <tr>
      <td><a href=\"javascript:void(0)\" onclick=\"window.open('Flyers/FlyerCust2pic.asp?ID={record_id}')\"><img alt=\"Click to view Flyer\" src=\"GetImage.asp?FIN={fin}\"></a></td>
      <td>{missing}</td><td>{name}</td><td>Race: White Sex: Female</td>
      <td>Age: 43 yrs 4 months</td><td>10 yrs</td><td>Child</td><td>{city},FL</td>
    </tr>
    """


def test_result_parser_extracts_fdle_identity_and_primary_image():
    m = _load_module()
    html = "<table>" + _result_row("Parsons, Andrea", "7/11/1993", "Port Salerno", "4099", "30980") + "</table>"
    rows = m._parse_result_rows(html, "https://www.fdle.state.fl.us/MCICSearch/Results.asp?From=QR&cou=Martin", "Martin")
    assert len(rows) == 1
    row = rows[0]
    assert row["record_key"] == "4099"
    assert row["name"] == "Andrea Parsons"
    assert row["missing_since"] == "7/11/1993"
    assert row["missing_from"] == "Port Salerno,FL"
    assert row["county"] == "Martin"
    assert row["source_url"].endswith("/MCICSearch/Flyers/FlyerCust2pic.asp?ID=4099")
    assert row["source_images"] == ["https://www.fdle.state.fl.us/MCICSearch/GetImage.asp?FIN=30980"]


def test_flyer_parser_preserves_multiple_official_images_and_case_notes():
    m = _load_module()
    record = {
        "record_key": "4099",
        "name": "Andrea Parsons",
        "source_images": ["https://www.fdle.state.fl.us/MCICSearch/GetImage.asp?FIN=30980"],
        "race": "White",
        "sex": "Female",
    }
    html = """
    <html><body>
      <img src=\"../GetImage.asp?FIN=30980\">
      <p>NAME: Andrea Parsons Missing: 7/11/1993 AGE MISSING: 10 years AGE NOW: 43 years
      SEX: Female HAIR: Brown EYES: Hazel HEIGHT: 4'11\" WEIGHT: 080 RACE: White
      FROM: Port Salerno, FL COUNTY: Martin Child</p>
      <img src=\"../GetImage.asp?FIN=485981\">
      <p>NARRATIVE: Andrea was last seen at the Port Salerno Grocery Store. Her photo has been age-progressed.</p>
      <p>FDLE MISSING ENDANGERED PERSONS INFORMATION CLEARINGHOUSE</p>
      <p>If you have any information concerning the whereabouts of this person, please contact FDLE or the Martin County Sheriff's Office at 772-220-7000</p>
    </body></html>
    """
    out = m._parse_flyer(html, "https://www.fdle.state.fl.us/MCICSearch/Flyers/FlyerCust2pic.asp?ID=4099", record)
    assert len(out["source_images"]) == 2
    assert out["source_images"][1].endswith("GetImage.asp?FIN=485981")
    assert "Port Salerno Grocery Store" in out["narrative"]


def test_county_scrape_follows_pagination_and_requires_complete_count(monkeypatch):
    m = _load_module()
    page1 = f"""
    <html><body><p>Displaying 1 to 1 of 2 record(s).</p>
    <a href=\"results.asp?ID=abc&Page=2&Pclick=1&cou=Martin\">2</a>
    <table>{_result_row('Parsons, Andrea','7/11/1993','Port Salerno','4099','30980')}</table></body></html>
    """
    page2 = f"""
    <html><body><p>Displaying 2 to 2 of 2 record(s).</p>
    <table>{_result_row('Doe, Jane','9/1/2026','Stuart','5000','50000')}</table></body></html>
    """

    def fake_fetch(_session, url, binary=False):
        return page2 if "Page=2" in url else page1

    monkeypatch.setattr(m, "_fetch", fake_fetch)
    monkeypatch.setattr(m, "_enrich_record", lambda _session, record: record)
    people, status = m.scrape_county(object(), "Martin")
    assert len(people) == 2
    assert status["expected_records"] == 2
    assert status["pages"] >= 2

    no_pagination = page1.replace('<a href="results.asp?ID=abc&Page=2&Pclick=1&cou=Martin">2</a>', "")
    monkeypatch.setattr(m, "_fetch", lambda _session, url, binary=False: no_pagination)
    with pytest.raises(RuntimeError, match="incomplete FDLE result set"):
        m.scrape_county(object(), "Martin")


def _configure_tmp_root(m, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "DATA_PATH", tmp_path / "data" / "missing-persons.json")
    monkeypatch.setattr(m, "STATUS_PATH", tmp_path / "data" / "missing-persons-source-status.json")
    monkeypatch.setattr(m, "PAGE_PATH", tmp_path / "missing-persons.html")
    monkeypatch.setattr(m, "PROFILE_DIR", tmp_path / "missing-persons")
    monkeypatch.setattr(m, "IMAGE_DIR", tmp_path / "images" / "missing-persons")
    monkeypatch.setattr(m.audience, "ROOT", tmp_path)
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "images" / "missing-persons").mkdir(parents=True)
    (tmp_path / "about.html").write_text(
        '<html><head></head><body>'
        '<header class="site-masthead"><a href="/weather.html" class="nav-section-link">Weather</a>'
        '<a href="/weather.html" class="mobile-nav-link">Weather</a></header>'
        '<footer><a href="/weather.html">Weather</a></footer><script src="/main.js"></script>'
        '</body></html>',
        encoding="utf-8",
    )
    (tmp_path / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        '<url><loc>https://treasurecoast.today/</loc></url></urlset>',
        encoding="utf-8",
    )


def test_render_keeps_all_cards_visible_and_builds_multi_image_profiles(monkeypatch, tmp_path):
    m = _load_module()
    _configure_tmp_root(m, monkeypatch, tmp_path)
    for name in ("4099-1.jpg", "4099-2.jpg"):
        (tmp_path / "images" / "missing-persons" / name).write_bytes(b"image")
    payload = {
        "schema_version": 1,
        "updated_at": "2026-09-11T20:00:00Z",
        "people": [{
            "record_key": "4099", "name": "Andrea Parsons", "missing_since": "7/11/1993",
            "missing_from": "Port Salerno,FL", "county": "Martin", "category": "Child",
            "current_age": "43 yrs", "age_missing": "10 yrs", "sex": "Female", "race": "White",
            "detail_url": "/missing-persons/andrea-parsons-4099.html",
            "images": ["/images/missing-persons/4099-1.jpg", "/images/missing-persons/4099-2.jpg"],
            "source_url": "https://www.fdle.state.fl.us/MCICSearch/Flyers/FlyerCust2pic.asp?ID=4099",
            "narrative": "Age-progressed image available.",
        }],
    }
    m._write_json(m.DATA_PATH, payload)
    m._write_json(m.STATUS_PATH, {"counties": {"Martin": {"status": "fresh"}}})
    result = m.render()
    m.validate()

    directory = (tmp_path / "missing-persons.html").read_text(encoding="utf-8")
    profile = (tmp_path / "missing-persons" / "andrea-parsons-4099.html").read_text(encoding="utf-8")
    assert result["people"] == 1
    assert directory.count('class="missing-person-card"') == 1
    assert "View more" not in directory and "Load more" not in directory
    assert "All" in directory and "Martin" in directory and "St. Lucie" in directory and "Indian River" in directory
    assert profile.count("Additional or age-progression FDLE image") == 2  # alt + figcaption
    assert "4099-1.jpg" in profile and "4099-2.jpg" in profile
    assert "View the official FDLE record" in profile


def test_refresh_retains_last_known_good_county_on_source_failure(monkeypatch, tmp_path):
    m = _load_module()
    _configure_tmp_root(m, monkeypatch, tmp_path)
    old = {
        "record_key": "old-sl", "name": "Prior Person", "missing_since": "1/1/2026",
        "missing_from": "Port St. Lucie,FL", "county": "St. Lucie", "detail_url": "/missing-persons/prior-person-old-sl.html",
        "images": [],
    }
    m._write_json(m.DATA_PATH, {"people": [old]})
    monkeypatch.setattr(m, "_session", lambda: object())
    monkeypatch.setattr(m, "_download_person_images", lambda _session, person, previous: (previous or {}).get("images", []))

    def fake_scrape(_session, county):
        if county == "St. Lucie":
            raise RuntimeError("temporary FDLE error")
        return [], {"status": "fresh", "expected_records": 0, "records": 0, "pages": 1}

    monkeypatch.setattr(m, "scrape_county", fake_scrape)
    result = m.refresh()
    payload = json.loads(m.DATA_PATH.read_text(encoding="utf-8"))
    status = json.loads(m.STATUS_PATH.read_text(encoding="utf-8"))
    assert result["fresh_counties"] == 2
    assert [p["record_key"] for p in payload["people"]] == ["old-sl"]
    assert status["counties"]["St. Lucie"]["status"] == "stale"


def test_navigation_and_workflow_contracts_include_missing_persons():
    audience = (ROOT / "scripts" / "build_audience_features.py").read_text(encoding="utf-8")
    missing = (ROOT / "scripts" / "update_missing_persons.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "update-missing-persons.yml").read_text(encoding="utf-8")
    assert "Public-service directory" in audience
    assert "Missing Persons</a>" in missing
    assert "python -u scripts/update_missing_persons.py" in workflow
    assert "python scripts/update_missing_persons.py --validate-only" in workflow
    assert "git add -A missing-persons/ images/missing-persons/" in workflow
    assert 'group: "pages"' in workflow


def test_bootstrap_directory_exists_at_repo_root_and_is_not_a_false_zero_state():
    page = ROOT / "missing-persons.html"
    assert page.exists(), "missing-persons.html must ship in the repo root so navigation never lands on a 404"
    html = page.read_text(encoding="utf-8")
    assert "Missing Persons on the Treasure Coast" in html
    assert "Current FDLE listings" in html
    assert "Public service directory" not in html
    assert "Directory update in progress" in html
    assert "Directory initializing" in html
    assert "0 current FDLE records" not in html


def test_directory_kicker_identifies_the_live_source_instead_of_generic_public_service_copy():
    source = (ROOT / "scripts" / "update_missing_persons.py").read_text(encoding="utf-8")
    assert "Current FDLE listings" in source
    assert "Public service directory" not in source


def test_county_query_is_self_contained_and_does_not_rely_on_server_search_state():
    m = _load_module()
    entries = m._county_entry_urls("St. Lucie")
    assert len(entries) == 2
    url = m._county_results_url("St. Lucie")
    assert "From=QR" in url
    assert "Rvw=Original" in url
    assert "cou=St.+Lucie" in url
    assert "cat=" in url and "cit=" in url and "fn=" in url and "ln=" in url
    page2 = m._county_results_url("St. Lucie", 2)
    assert "Page=2" in page2 and "Pclick=1" in page2


def test_result_parser_anchors_each_fdle_thumbnail_to_its_own_record_row():
    m = _load_module()
    html = f"""
    <table><tr><td><table>
      {_result_row('Parsons, Andrea','7/11/1993','Port Salerno','4099','30980')}
      {_result_row('Andres, Jose','9/16/2021','Stuart','330579','3305790')}
    </table></td></tr></table>
    """
    rows = m._parse_result_rows(
        html,
        "https://www.fdle.state.fl.us/MCICSearch/Results.asp?From=QR&cou=Martin",
        "Martin",
    )
    assert {row["record_key"] for row in rows} == {"4099", "330579"}
    assert {row["name"] for row in rows} == {"Andrea Parsons", "Jose Andres"}


def test_first_refresh_refuses_to_publish_partial_counties_without_baseline(monkeypatch, tmp_path):
    m = _load_module()
    _configure_tmp_root(m, monkeypatch, tmp_path)
    monkeypatch.setattr(m, "_session", lambda: object())
    monkeypatch.setattr(m, "_download_person_images", lambda *_args, **_kwargs: [])

    def fake_scrape(_session, county):
        if county == "St. Lucie":
            raise RuntimeError("source parse failed")
        person = {
            "record_key": county, "name": f"{county} Person", "missing_since": "1/1/2026",
            "missing_from": f"Somewhere,FL", "county": county, "source_images": [],
        }
        return [person], {"status": "fresh", "expected_records": 1, "records": 1, "pages": 1}

    monkeypatch.setattr(m, "scrape_county", fake_scrape)
    with pytest.raises(RuntimeError, match="Refusing to publish a partial Treasure Coast directory"):
        m.refresh()
    assert not m.DATA_PATH.exists()


def test_large_count_collapse_keeps_last_known_good_county(monkeypatch, tmp_path):
    m = _load_module()
    _configure_tmp_root(m, monkeypatch, tmp_path)
    prior = []
    for idx in range(8):
        prior.append({
            "record_key": f"old-{idx}", "name": f"Prior {idx}", "missing_since": "1/1/2025",
            "missing_from": "Stuart,FL", "county": "Martin",
            "detail_url": f"/missing-persons/prior-{idx}.html", "images": [],
        })
    m._write_json(m.DATA_PATH, {"people": prior})
    monkeypatch.setattr(m, "_session", lambda: object())
    monkeypatch.setattr(m, "_download_person_images", lambda _session, person, previous: (previous or {}).get("images", []))

    def fake_scrape(_session, county):
        if county == "Martin":
            return [{
                "record_key": "new-only", "name": "New Only", "missing_since": "9/1/2026",
                "missing_from": "Stuart,FL", "county": "Martin", "source_images": [],
            }], {"status": "fresh", "expected_records": 1, "records": 1, "pages": 1}
        return [], {"status": "fresh", "expected_records": 0, "records": 0, "pages": 1}

    monkeypatch.setattr(m, "scrape_county", fake_scrape)
    result = m.refresh()
    payload = json.loads(m.DATA_PATH.read_text(encoding="utf-8"))
    status = json.loads(m.STATUS_PATH.read_text(encoding="utf-8"))
    assert result["fresh_counties"] == 2
    assert len([p for p in payload["people"] if p["county"] == "Martin"]) == 8
    assert status["counties"]["Martin"]["status"] == "stale"
    assert "suspicious FDLE record-count drop" in status["counties"]["Martin"]["error"]


def test_missing_person_profile_title_is_not_sticky_and_single_photo_is_framed():
    css = (ROOT / "style.css").read_text(encoding="utf-8")
    assert ".missing-person-profile-page > .missing-person-profile-head" in css
    profile_rule = css.split(".missing-person-profile-page > .missing-person-profile-head", 1)[1].split("}", 1)[0]
    assert "position: static" in profile_rule
    assert "top: auto" in profile_rule
    assert "background: transparent" in profile_rule
    assert "border-bottom: 0" in profile_rule
    single_rule = css.split(".missing-person-gallery figure:first-child:last-child", 1)[1].split("}", 1)[0]
    assert "width: min(100%, 390px)" in single_rule
    assert "justify-self: center" in single_rule
