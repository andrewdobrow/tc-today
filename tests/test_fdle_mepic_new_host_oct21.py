"""FDLE October 2026 migrated MEPIC endpoints; retain fail-closed county checks."""
from __future__ import annotations
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]

def module():
    spec = importlib.util.spec_from_file_location('new_mepic_endpoints', ROOT / 'scripts/update_missing_persons.py')
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def test_source_home_points_to_current_official_mepic_search():
    m = module()
    assert m.SOURCE_HOME == 'https://mepic.fdle.state.fl.us/Search.asp'
    assert 'fdle.state.fl.us' in m.SOURCE_HOME

def test_qr_county_result_uses_current_domain_but_keeps_county_aliases():
    m = module()
    assert m._qr_county_url('Martin') == 'https://mepic.fdle.state.fl.us/Results.asp?From=QR&cou=Martin'
    assert 'cou=Saint+Lucie' in m._qr_county_url('St. Lucie','Saint Lucie')
    assert 'cou=Indian+River' in m._qr_county_url('Indian River')

def test_flyer_candidates_use_new_official_host():
    m = module()
    urls = m._candidate_flyers('4099')
    assert len(urls) == 4
    assert all(u.startswith('https://mepic.fdle.state.fl.us/Flyers/') for u in urls)

def test_search_form_submission_uses_new_host_and_all_categories():
    m = module()
    markup = '''<form action="Results.asp" method="POST"><select name="cou"><option value="57">Martin</option></select>
      <select name="cat"><option value="0">Select</option><option value="99">All Categories</option></select></form>'''
    spec = m._search_form_submission(markup, m.SOURCE_HOME, 'Martin')
    assert spec['action'] == 'https://mepic.fdle.state.fl.us/Results.asp'
    assert spec['data']['cou'] == '57' and spec['data']['cat'] == '99'

def test_new_host_result_requires_proof_of_county_category_and_total():
    m=module()
    assert m._verified_county_result("You Searched For: County: 'Martin' Category: 'All Categories' Displaying 1 to 2 of 2 record(s).", 'Martin') == (True, '', 2)
    assert not m._verified_county_result("You Searched For: County: 'Indian River' Category: 'All Categories' Displaying 1 to 2 of 2 record(s).", 'Martin')[0]
    assert not m._verified_county_result('No matching records', 'Martin')[0]
    assert not m._verified_county_result('MEPIC :: Search', 'Martin')[0]

def test_new_host_404s_never_bypass_fdle_fail_closed(monkeypatch):
    m = module()
    class Response:
        def __init__(self, url, page): self.url=url; self.text=page; self.status_code=200
    def fake_request(_session, method, url, **kw):
        if '/Results.asp' in url and method=='GET': raise RuntimeError('HTTP 404')
        if url == m.SOURCE_HOME:
            return Response(url, '<form action="Results.asp" method="POST"><select name="cou"><option>Martin</option></select><select name="cat"><option>All Categories</option></select></form>')
        return Response(url, '<html><title>MEPIC :: Search</title>Search</html>')
    monkeypatch.setattr(m, '_request_response', fake_request)
    with pytest.raises(RuntimeError, match='result page did not report the searched county'):
        m._start_county_search(object(), 'Martin')

def test_current_host_qr_county_success_even_if_form_returns_search_page(monkeypatch):
    m=module()
    class Response:
        status_code=200
        def __init__(self, url, text): self.url=url; self.text=text
    result="You Searched For: County: 'Martin' Category: 'All Categories' Displaying 1 to 2 of 2 record(s)."
    search='''<form method="post" action="Results.asp"><select name="cou"><option value="1">Martin</option></select><select name="cat"><option value="99">All Categories</option></select></form>'''
    calls=[]
    def fake_request(_session, method, url, **kwargs):
        calls.append((method,url))
        if url == m._qr_county_url('Martin'): return Response(url, result)
        if url == m.SOURCE_HOME: return Response(url, search)
        return Response(url, '<title>MEPIC :: Search</title>')
    monkeypatch.setattr(m,'_request_response',fake_request)
    html, url, spec=m._start_county_search(object(),'Martin')
    assert html == result
    assert url == m._qr_county_url('Martin')
    assert spec['search_mode'] == 'fdle_qr_county'
    assert spec['selected_total'] == 2
    assert [call[1] for call in calls].count(m._qr_county_url('Martin')) == 2
    assert spec['search_warnings']  # still record why alternate form failed
