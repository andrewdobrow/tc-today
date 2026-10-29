"""Regression: a confirmed FDLE county with zero cases must not fail forever.

The real Oct. 29 incident was a zero/uncertain Indian River response after a
previously verified one-person result.  Never treat a blank or broken page as
an empty county; require official source form + positive QR control + repeat.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location(
        "fdle_confirmed_empty_oct29", ROOT / "scripts/update_missing_persons.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ZERO = """<html><head><title>MEPIC :: Search Results</title></head>
<body><h1>Search Results</h1><p>No matching records.</p></body></html>"""
MARTIN = """<html><head><title>MEPIC :: Search Results</title></head><body>
<p>You Searched For: County: 'Martin' Category: 'All Categories'</p>
<p>Displaying 1 to 2 of 2 record(s).</p></body></html>"""
FORM = """<html><head><title>MEPIC :: Search</title></head><body>
<form method="POST" action="Results.asp">
<select name="cou"><option value="31">Indian River</option>
<option value="43">Martin</option></select>
<select name="cat"><option value="0">Select</option><option value="99">All Categories</option></select>
<input type="image" name="Search" src="search.gif">
</form></body></html>"""


class Response:
    status_code = 200

    def __init__(self, url, html):
        self.url = url
        self.text = html


def prepare(monkeypatch, m, *, zero=ZERO, form=FORM, control=MARTIN, repeat=None):
    calls = []
    independent = object()
    monkeypatch.setattr(m, "_session", lambda: independent)

    def request(session, method, url, **kwargs):
        calls.append((session, method, url, kwargs))
        if url == m.SOURCE_HOME:
            return Response(url, form)
        if method == "POST":
            return Response(m.MEPIC_ORIGIN + "/Results.asp", "<title>MEPIC :: Search Results</title>Unverified")
        parsed = urlparse(url)
        if parsed.path.endswith("/Results.asp"):
            county = parse_qs(parsed.query).get("cou", [""])[0]
            if county == "Indian River":
                if session is independent and repeat is not None:
                    return Response(url, repeat)
                return Response(url, zero)
            if county == "Martin":
                return Response(url, control)
            if county == "Saint Lucie":
                return Response(url, "<title>MEPIC :: Search Results</title>Bad control")
        raise AssertionError((method, url))

    monkeypatch.setattr(m, "_request_response", request)
    return calls


def test_confirmed_empty_indian_river_is_a_complete_success(monkeypatch):
    m = load()
    calls = prepare(monkeypatch, m)
    people, status = m.scrape_county(object(), "Indian River")
    assert people == []
    assert status["status"] == "fresh"
    assert status["expected_records"] == 0
    assert status["records"] == 0
    assert status["search_mode"] == "fdle_qr_confirmed_empty"
    assert status["category"] == "All Categories"
    indian_calls = [entry for entry in calls if "cou=Indian+River" in entry[2]]
    assert len(indian_calls) == 3  # initial, independent confirmation, re-establish
    assert any(entry[0] is not indian_calls[0][0] for entry in indian_calls)


def test_unverified_zero_remains_rejected_by_normal_county_verifier():
    m = load()
    assert m._verified_county_result(ZERO, "Indian River")[0] is False
    assert m._explicit_empty_fdle_result(ZERO, "Indian River")
    assert not m._explicit_empty_fdle_result("<title>MEPIC :: Search Results</title>", "Indian River")


@pytest.mark.parametrize(
    "page",
    [
        "<html><title>MEPIC :: Search</title>No matching records</html>",
        "<html><title>MEPIC :: Search Results</title>Search Results</html>",
        """<html><title>MEPIC :: Search Results</title>
           You Searched For: County: 'Martin' No matching records</html>""",
        """<html><title>MEPIC :: Search Results</title>
           You Searched For: County: 'Indian River' Category: 'Missing Person'
           No matching records</html>""",
        """<html><title>MEPIC :: Search Results</title>
           Displaying 1 to 2 of 2 record(s)</html>""",
    ],
)
def test_blank_wrong_county_wrong_category_and_positive_pages_are_not_zeros(page):
    m = load()
    assert not m._explicit_empty_fdle_result(page, "Indian River")


def test_no_positive_control_keeps_last_known_good_and_fails_closed(monkeypatch):
    m = load()
    prepare(monkeypatch, m, control="<title>MEPIC :: Search Results</title>Search Results")
    with pytest.raises(RuntimeError, match="FDLE county search failed for Indian River"):
        m._start_county_search(object(), "Indian River")


def test_independent_zero_check_must_agree(monkeypatch):
    m = load()
    prepare(monkeypatch, m, repeat="<title>MEPIC :: Search Results</title>Search Results")
    with pytest.raises(RuntimeError, match="FDLE county search failed for Indian River"):
        m._start_county_search(object(), "Indian River")


def test_live_fdle_form_must_recognize_requested_county(monkeypatch):
    m = load()
    bad_form = FORM.replace('<option value="31">Indian River</option>', "")
    prepare(monkeypatch, m, form=bad_form)
    with pytest.raises(RuntimeError, match="FDLE county search failed for Indian River"):
        m._start_county_search(object(), "Indian River")


def test_other_counties_positive_results_still_use_strict_county_verification(monkeypatch):
    m = load()
    prepare(monkeypatch, m)
    html, url, spec = m._start_county_search(object(), "Martin")
    assert spec["search_mode"] == "fdle_qr_county"
    assert spec["selected_total"] == 2
    assert "County: 'Martin'" in html
    assert "cou=Martin" in url
