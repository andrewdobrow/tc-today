from __future__ import annotations

import importlib.util
import os
import sys
import types
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_generate():
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
    spec = importlib.util.spec_from_file_location("generate_exact_headline_runtime", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_exact_headline_incident_evidence_executes_full_trace_without_foreign_scope_nameerror(monkeypatch):
    module = _load_generate()
    features = {
        "date": datetime(2026, 8, 14),
        "locality": frozenset({"fort pierce"}),
        "event_families": frozenset({"shooting"}),
        "incident_anchor": "",
        "people": frozenset({"jane doe"}),
        "precise_locations": frozenset(),
        "agencies": frozenset(),
        "distinctive_tokens": frozenset({"mobile", "home", "park", "investigation", "fort", "pierce"}),
    }
    monkeypatch.setattr(
        module,
        "_final_publication_identity_features",
        lambda item, include_archive_body=True: features,
    )

    left = {"headline": "Fort Pierce police identify victim in mobile home park shooting"}
    right = {"headline": "Fort Pierce police identify victim in mobile home park shooting"}

    evidence = module._exact_headline_incident_evidence(left, right)

    assert evidence["matched"] is True
    assert evidence["write_authorized"] is True
    assert any(line == "write_authorized=True" for line in evidence["decision_trace"])
    assert not any("shared_specific_topic_core" in line for line in evidence["decision_trace"])
