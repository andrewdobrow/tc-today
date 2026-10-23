"""Behavior-oriented regressions for attributed suspect identities in source text.

All examples are synthetic.  These cases do not assert a particular current
headline, article ID, or individual in production editorial content.
"""
import ast
import json
from pathlib import Path

from tct_engine.critical_source_facts import (
    as_named_suspect_facts,
    facts_instruction,
    missing_named_suspects,
    named_suspect_facts,
)


def test_explicit_attributed_named_arrests_survive_source_extraction():
    examples = [
        "Police arrested 60-year-old Eric Saint Aude Friday in connection with the hit-and-run.",
        "Investigators said they have arrested Eric Saint Aude after reviewing surveillance video.",
        "The suspect, Eric Saint Aude, was arrested following the investigation.",
        "Eric Saint Aude, 60, was arrested after the crash.",
        "Police identified Eric Saint Aude as the suspect.",
        "Police identified the suspect as Eric Saint Aude.",
    ]
    for report in examples:
        assert [fact.name for fact in named_suspect_facts(report)] == ["Eric Saint Aude"]


def test_unidentified_or_unconfirmed_person_is_not_inferred():
    examples = [
        "Police say the suspect has not been identified.",
        "Police said they have not arrested Eric Saint Aude.",
        "The photo shows a man wearing a jacket, but the source names no one.",
        "Police are seeking a driver after a collision on Northwest University Boulevard.",
        "Investigators said a name might be released later.",
    ]
    for report in examples:
        assert not named_suspect_facts(report)


def test_writer_omission_of_verified_arrest_name_is_blocked():
    facts = named_suspect_facts(
        "Police arrested Eric Saint Aude after investigators reviewed video of the crash."
    )
    assert len(facts) == 1
    assert [x.name for x in missing_named_suspects("Police made an arrest after reviewing video.", facts)] == ["Eric Saint Aude"]
    assert not missing_named_suspects("Police say Eric Saint Aude was arrested after the crash.", facts)


def test_names_are_exact_entities_not_partial_or_generic_mentions():
    facts = named_suspect_facts("Eric Saint Aude was arrested after the collision.")
    assert [x.name for x in missing_named_suspects("Police arrested Eric Saint on Friday.", facts)] == ["Eric Saint Aude"]
    assert not missing_named_suspects("Police arrested ERIC SAINT-AUDE after the crash.", [])


def test_provenance_json_safe_and_instructions_preserve_evidence():
    facts = named_suspect_facts("Police identified the suspect as Eric Saint Aude.")
    rows = [{"name": x.name, "evidence": x.evidence} for x in facts]
    assert as_named_suspect_facts(json.loads(json.dumps(rows))) == facts
    assert "Police identified the suspect as Eric Saint Aude" in facts_instruction(rows)


def test_noncriminal_named_people_do_not_create_suspect_requirements():
    assert not named_suspect_facts("Police Chief Eric Saint Aude announced the traffic safety campaign.")
    assert not named_suspect_facts("Detectives said Eric Saint Aude witnessed the crash.")


def test_production_has_source_contract_at_writer_and_final_publish_gate():
    """Check integration points by behavior, not exact headlines or file versions."""
    generator = Path(__file__).resolve().parents[1] / "scripts" / "generate.py"
    tree = ast.parse(generator.read_text())
    defs = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for fn in ("_build_assignment_editor_packet", "_run_assignment_writer", "_publishable_article"):
        assert fn in defs
    def calls(fn):
        return {
            n.func.id for n in ast.walk(defs[fn])
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
    assert "named_suspect_facts" in calls("_build_assignment_editor_packet")
    assert "missing_named_suspects" in calls("_run_assignment_writer")
    assert "missing_named_suspects" in calls("_publishable_article")


def test_two_extractors_reconcile_missing_verifiable_identity_without_guesswork():
    from tct_engine.critical_source_facts import reconcile_same_article_extraction
    primary = "Police said they made an arrest after a hit-and-run crash."
    structured = "Detectives arrested 60-year-old Eric Saint Aude following the hit-and-run crash."
    combined = reconcile_same_article_extraction(primary, structured)
    assert "Eric Saint Aude" in combined
    assert "Police said they made an arrest" in combined
    assert combined == reconcile_same_article_extraction(combined, structured)


def test_source_reconciliation_does_not_make_arrest_from_photo_alone():
    from tct_engine.critical_source_facts import reconcile_same_article_extraction
    primary = "Police continued to investigate the crash."
    caption = "Photo of Eric Saint Aude outside the courthouse."
    assert reconcile_same_article_extraction(primary, caption) == primary


def _fetcher_isolated_from_generator(monkeypatch, page_html):
    """Exercise the actual generator extraction function against mocked HTML."""
    import copy
    import importlib.util
    import json
    import re
    import sys
    import threading
    import types

    from tct_engine.critical_source_facts import reconcile_same_article_extraction

    generator = Path(__file__).resolve().parents[1] / "scripts" / "generate.py"
    tree = ast.parse(generator.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "fetch_article_text")
    cache_miss = object()
    class Cache:
        def __init__(self):
            self.saved = {}
        def get(self, bucket, key, max_age_seconds=None):
            return self.saved.get(key, cache_miss)
        def put(self, bucket, key, value, ttl_seconds):
            self.saved[key] = value
    fake_tra = types.SimpleNamespace(extract=lambda html, **kw: " ".join(["Police investigated the crash and collected surveillance video."] * 35))
    monkeypatch.setitem(sys.modules, "trafilatura", fake_tra)
    ns = {
        "re": re, "json": json,
        "requests": types.SimpleNamespace(get=lambda *args, **kwargs: types.SimpleNamespace(status_code=200, text=page_html)),
        "GENERATION_CACHE": Cache(), "_CACHE_MISS": cache_miss,
        "_source_text_cache_key": lambda *args: "the-page",
        "_temporal_source_refresh_interval": lambda source: None,
        "_source_fetch_lock": lambda key: threading.Lock(),
        "_normalize_cache_url": lambda u: u.rstrip("/"),
        "reconcile_same_article_extraction": reconcile_same_article_extraction,
    }
    exec(compile(ast.Module(body=[copy.deepcopy(node)], type_ignores=[]), str(generator), "exec"), ns)
    return ns["fetch_article_text"]


def test_current_same_article_json_ld_arrest_fact_survives_other_extractor(monkeypatch):
    import json
    same_url = "https://local.example/news/developing-crash"
    headline = "Police Arrest Suspect in Developing Crash"
    data = {
        "@type": "NewsArticle", "headline": headline, "url": same_url,
        "articleBody": " ".join(["Detectives reviewed video following the collision."] * 30)
        + " Police arrested Eric Saint Aude after reviewing the video."
    }
    html = '<article><p>Detectives continued the investigation.</p></article>' \
        + '<script type="application/ld+json">' + json.dumps(data) + '</script>'
    fetched = _fetcher_isolated_from_generator(monkeypatch, html)(
        same_url, source={"title": headline}
    )
    assert "Eric Saint Aude" in fetched
    assert "collected surveillance video" in fetched


def test_unrelated_json_ld_article_cannot_inject_a_named_suspect(monkeypatch):
    import json
    url = "https://local.example/news/developing-crash"
    related = {
        "@type": "NewsArticle", "headline": "Different Armed Robbery in Another City",
        "url": "https://local.example/news/unrelated-robbery",
        "articleBody": " ".join(["Officers responded to an unrelated reported robbery."] * 30)
        + " Police arrested Eric Saint Aude in that robbery investigation."
    }
    html = '<article><p>Police still seek witnesses to the developing crash.</p></article>' \
        + '<script type="application/ld+json">' + json.dumps(related) + '</script>'
    fetched = _fetcher_isolated_from_generator(monkeypatch, html)(
        url, source={"title": "Police Seek Driver After Crash on University Boulevard"}
    )
    assert "Eric Saint Aude" not in fetched
