"""Regression for legacy subscriber ad-free rights after free-news transition.

The original site loaded Mediavine eagerly in the head, before Supabase checked
subscription entitlement. A CSS class set afterwards is not sufficient.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest
from scripts.free_news_transition import _gate_mediavine_for_paid_members, _rewrite_chrome

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ('<html><head><script type="text/javascript" async="async" '
            'data-noptimize="1" data-cfasync="false" '
            'src="//scripts.mediavine.com/tags/31bba1e2-0cf0-4381-8d83-ea54f9aa3bbf.js"></script>'
            '</head><body>Free news</body></html>')


def test_static_mediavine_loader_is_replaced_only_in_donation_mode():
    html = _gate_mediavine_for_paid_members(ORIGINAL)
    assert html.count('data-tct-mediavine-member-gate') == 1
    assert 'src="/member-ad-gate.js?v=20261029a"' in html
    assert 'data-tct-mediavine-src="//scripts.mediavine.com/tags/' in html
    assert ' src="//scripts.mediavine.com/tags/' not in html
    assert _gate_mediavine_for_paid_members(html) == html
    assert _gate_mediavine_for_paid_members('<head></head>') == '<head></head>'


def test_eager_duplicate_cannot_bypass_existing_gate():
    html = _gate_mediavine_for_paid_members(ORIGINAL)
    mixed = html.replace('</head>', ORIGINAL.split('<head>', 1)[1].split('</head>')[0] + '</head>')
    repaired = _gate_mediavine_for_paid_members(mixed)
    assert repaired.count('data-tct-mediavine-member-gate') == 1
    assert ' src="//scripts.mediavine.com/tags/' not in repaired


def test_legacy_membership_client_is_cache_busted():
    result = _rewrite_chrome(
        '<html><head></head><body><script type="module" '
        'src="/membership.js?v=1.13.9.113"></script></body></html>',
        'example.html',
    )
    assert '/membership.js?v=1.13.9.115' in result


def test_status_client_reports_all_entitlement_outcomes_to_gate():
    js = (ROOT / 'membership.js').read_text(encoding='utf-8')
    assert "resolveMemberAdGate({ authenticated:false, entitled:false })" in js
    assert "resolveMemberAdGate({ authenticated:true, entitled:false, error:error.message })" in js
    assert "resolveMemberAdGate({ authenticated:true, entitled })" in js
    assert "resolveMemberAdGate({ authenticated:true, entitled:true })" in js


NODE_HARNESS = r"""
const fs = require('node:fs')
const vm = require('node:vm')
const options = JSON.parse(process.argv[2])
const js = fs.readFileSync(process.argv[1], 'utf8')
const storage = new Map(Object.entries(options.storage || {}))
const sessions = new Map()
const tags = []
let reloads = 0
const currentScript = {
  getAttribute: key => key === 'data-tct-mediavine-src'
    ? '//scripts.mediavine.com/tags/31bba1e2-0cf0-4381-8d83-ea54f9aa3bbf.js'
    : null,
}
const makeStorage = store => ({
  get length() { return store.size },
  key: i => Array.from(store.keys())[i] || null,
  getItem: k => store.get(k) ?? null,
  setItem: (k,v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
})
const context = {
  document: {
    currentScript,
    createElement: tag => ({tag, setAttribute(k, v) { this[k] = v }}),
    head: { appendChild: element => tags.push(element) },
  },
  localStorage: makeStorage(storage),
  sessionStorage: makeStorage(sessions),
  location: {
    search: options.search || '',
    hash: options.hash || '',
    reload() { reloads += 1 },
  },
  URLSearchParams,
  window: {},
}
vm.runInNewContext(js, context)
const first = tags.length
for (const status of options.statuses || []) context.window.TCTMemberAdGate.resolve(status)
console.log(JSON.stringify({
  first, final: tags.length, reloads,
  src: tags.length ? tags[0].src : '',
}))
"""


@pytest.mark.skipif(not shutil.which('node'), reason='Node.js not available')
@pytest.mark.parametrize('scenario,expected', [
    ({'storage': {}, 'statuses': []}, {'first': 1, 'final': 1, 'reloads': 0}),
    ({'storage': {'sb-abcd123-auth-token': 'token'}, 'statuses': [
        {'authenticated': True, 'entitled': True}
    ]}, {'first': 0, 'final': 0, 'reloads': 0}),
    ({'storage': {'sb-abcd123-auth-token': 'token'}, 'statuses': [
        {'authenticated': True, 'entitled': False}
    ]}, {'first': 0, 'final': 1, 'reloads': 0}),
    ({'storage': {'sb-abcd123-auth-token': 'token'}, 'statuses': [
        {'authenticated': True, 'entitled': False, 'error': 'temporarily unavailable'}
    ]}, {'first': 0, 'final': 0, 'reloads': 0}),
    ({'storage': {'tct_member_entitled_hint': '1'}, 'statuses': [
        {'authenticated': False, 'entitled': False}
    ]}, {'first': 0, 'final': 1, 'reloads': 0}),
    ({'storage': {'sb-abcd123-auth-token': 'token'}, 'statuses': [
        {'authenticated': True, 'entitled': True},
        {'authenticated': False, 'entitled': False},
    ]}, {'first': 0, 'final': 1, 'reloads': 0}),
    ({'storage': {}, 'search': '?code=sample', 'statuses': [
        {'authenticated': True, 'entitled': True},
    ]}, {'first': 0, 'final': 0, 'reloads': 0}),
    ({'storage': {}, 'statuses': [
        {'authenticated': True, 'entitled': True}
    ]}, {'first': 1, 'final': 1, 'reloads': 1}),
])
def test_browser_gate_never_initializes_ads_for_verified_member(scenario, expected):
    result = subprocess.run(
        ['node', '-e', NODE_HARNESS, str(ROOT / 'member-ad-gate.js'), json.dumps(scenario)],
        capture_output=True, text=True, check=True,
    )
    observed = json.loads(result.stdout)
    for key, value in expected.items():
        assert observed[key] == value
    if observed['final']:
        assert 'scripts.mediavine.com/tags/' in observed['src']
