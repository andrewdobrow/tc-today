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

from tct_engine.semantic_publication_gate import (
    ACTION_DUPLICATE,
    ACTION_HOLD,
    ACTION_UPDATE,
    adjudicate_candidates,
    headline_similarity,
    retrieve_recent_candidates,
)

CANONICAL_HEADLINE = (
    "Woman, 86, dies in Port St. Lucie crash after failing to yield at intersection"
)
INCOMING_HEADLINE = (
    "86-year-old woman dies after crash at Port St. Lucie intersection"
)
CANONICAL_SLUG = (
    "2026-07-31-woman-86-dies-in-port-st-lucie-crash-after-failing-to-yield-at-intersection"
)
DUPLICATE_SLUG = (
    "2026-08-01-86-year-old-woman-dies-after-crash-at-port-st-lucie-intersection"
)
BODY = (
    "Marie R. Martin, 86, died after her 2006 Hyundai Elantra was struck by a "
    "Honda HR-V at Southwest Savona Boulevard and Southwest Lawndale Avenue in "
    "Port St. Lucie. Port St. Lucie police said she failed to yield before the "
    "crash. The teenage Honda driver was not injured."
)


class _Response:
    def __init__(self, text: str):
        self.content = [types.SimpleNamespace(text=text)]


class _Messages:
    def __init__(self, payload: dict | None = None, error: Exception | None = None):
        self.payload = payload or {}
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return _Response(json.dumps(self.payload))


class _Client:
    def __init__(self, payload: dict | None = None, error: Exception | None = None):
        self.messages = _Messages(payload, error)


def _article(slug: str, headline: str, date: str, body: str = BODY):
    return {
        "slug": slug,
        "headline": headline,
        "source_headline": headline,
        "published_at": date,
        "date": date,
        "body": body,
        "teaser": body,
        "source_url": f"https://example.com/{slug}",
        "locality": ["port-st-lucie", "st-lucie-county"],
        "event_families": ["crash"],
        "people": ["marie-martin"],
        "precise_locations": [
            "southwest-savona-boulevard",
            "southwest-lawndale-avenue",
        ],
        "agencies": ["port-st-lucie-police"],
        "incident_anchor": "named-person-death:marie-martin",
        "known_event_key": "named-person-death:marie-martin",
    }


def _candidate_row(article: dict):
    candidates = retrieve_recent_candidates(
        _article("", INCOMING_HEADLINE, "2026-08-01"),
        [article],
        window_days=7,
        max_candidates=4,
    )
    assert len(candidates) == 1
    return candidates


def _load_generate(tmp_path: Path):
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
    spec = importlib.util.spec_from_file_location(
        "generate_semantic_final_publication_gate", path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    module.OUTPUT_DIR = tmp_path
    module.SEMANTIC_GATE_CACHE_PATH = tmp_path / "data" / "semantic-publication-gate-cache.json"
    module.SEMANTIC_GATE_REPORT_PATH = tmp_path / "data" / "semantic-publication-gate.json"
    return module


def _archive_row(slug: str, headline: str, date: str, story_id: str):
    row = _article(slug, headline, date)
    row.update({
        "first_published": f"{date}T12:00:00-04:00",
        "category_key": "crime",
        "category_label": "Crime & Safety",
        "category_keys": ["crime", "st_lucie"],
        "county_keys": ["st_lucie"],
        "editorial_story_id": story_id,
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "article_word_count": 220,
        "article_paragraph_count": 4,
        "event_identity": {
            "schema_version": "1.0",
            "incident_anchor": "named-person-death:marie-martin",
            "known_event_key": "named-person-death:marie-martin",
            "locality": ["port-st-lucie", "st-lucie-county"],
            "event_families": ["crash"],
            "people": ["marie-martin"],
            "precise_locations": [
                "southwest-savona-boulevard",
                "southwest-lawndale-avenue",
            ],
            "agencies": ["port-st-lucie-police"],
        },
    })
    return row


def _write_page(root: Path, slug: str, body: str = BODY):
    articles = root / "articles"
    articles.mkdir(parents=True, exist_ok=True)
    paragraphs = "".join(f"<p>{part.strip()}</p>" for part in body.split(". ") if part.strip())
    (articles / f"{slug}.html").write_text(
        f'<div class="article-body">{paragraphs}</div><div class="article-share">share</div>',
        encoding="utf-8",
    )


def test_fuzzy_headline_retrieval_catches_reordered_duplicate():
    metrics = headline_similarity(CANONICAL_HEADLINE, INCOMING_HEADLINE)
    assert metrics["score"] >= 0.75
    candidates = _candidate_row(
        _article(CANONICAL_SLUG, CANONICAL_HEADLINE, "2026-07-31")
    )
    assert candidates[0]["slug"] == CANONICAL_SLUG
    assert "strong_fuzzy_headline" in candidates[0]["evidence"]["reasons"]


def test_production_pair_is_retrieved_even_when_new_source_lacks_name_and_street_keys():
    incoming = _article("", INCOMING_HEADLINE, "2026-08-01")
    incoming.update({
        "people": [],
        "precise_locations": [],
        "agencies": [],
        "incident_anchor": "",
        "known_event_key": "",
    })
    candidates = retrieve_recent_candidates(
        incoming,
        [_article(CANONICAL_SLUG, CANONICAL_HEADLINE, "2026-07-31")],
        window_days=7,
        max_candidates=4,
    )

    assert [candidate["slug"] for candidate in candidates] == [CANONICAL_SLUG]
    assert candidates[0]["evidence"]["headline_similarity"]["score"] >= 0.75


def test_claude_adjudication_distinguishes_duplicate_from_material_update():
    candidates = _candidate_row(
        _article(CANONICAL_SLUG, CANONICAL_HEADLINE, "2026-07-31")
    )
    duplicate_client = _Client({
        "selected_candidate_slug": CANONICAL_SLUG,
        "same_real_world_event": True,
        "material_new_update": False,
        "confidence": 0.99,
        "shared_anchors": ["Marie Martin", "Savona and Lawndale"],
        "novel_facts": [],
        "reason": "The reports repeat the same fatal crash facts.",
        "recommended_action": ACTION_DUPLICATE,
    })
    duplicate = adjudicate_candidates(
        duplicate_client,
        model="claude-sonnet-4-5",
        incoming=_article("", INCOMING_HEADLINE, "2026-08-01"),
        candidates=candidates,
    )
    assert duplicate["action"] == ACTION_DUPLICATE

    update_client = _Client({
        "selected_candidate_slug": CANONICAL_SLUG,
        "same_real_world_event": True,
        "material_new_update": True,
        "confidence": 0.96,
        "shared_anchors": ["same victim and intersection"],
        "novel_facts": ["Police filed a new criminal charge"],
        "reason": "The charge is a consequential new development.",
        "recommended_action": ACTION_UPDATE,
    })
    update = adjudicate_candidates(
        update_client,
        model="claude-sonnet-4-5",
        incoming=_article("", INCOMING_HEADLINE, "2026-08-01"),
        candidates=candidates,
    )
    assert update["action"] == ACTION_UPDATE


def test_semantic_gate_fails_closed_when_model_errors():
    candidates = _candidate_row(
        _article(CANONICAL_SLUG, CANONICAL_HEADLINE, "2026-07-31")
    )
    result = adjudicate_candidates(
        _Client(error=RuntimeError("temporary API failure")),
        model="claude-sonnet-4-5",
        incoming=_article("", INCOMING_HEADLINE, "2026-08-01"),
        candidates=candidates,
    )
    assert result["action"] == ACTION_HOLD
    assert result["status"] == "model_error"


def test_recent_archive_repair_redirects_fuzzy_duplicate(tmp_path, monkeypatch):
    generate = _load_generate(tmp_path)
    canonical = _archive_row(
        CANONICAL_SLUG, CANONICAL_HEADLINE, "2026-07-31", "story_001557"
    )
    duplicate = _archive_row(
        DUPLICATE_SLUG, INCOMING_HEADLINE, "2026-08-01", "story_001684"
    )
    _write_page(tmp_path, CANONICAL_SLUG)
    _write_page(tmp_path, DUPLICATE_SLUG)

    fake = _Client({
        "selected_candidate_slug": CANONICAL_SLUG,
        "same_real_world_event": True,
        "material_new_update": False,
        "confidence": 0.99,
        "shared_anchors": [
            "Marie Martin, age 86",
            "Southwest Savona Boulevard and Southwest Lawndale Avenue",
            "Hyundai Elantra and Honda HR-V",
        ],
        "novel_facts": [],
        "reason": "Both articles cover the same fatal intersection crash with no new development.",
        "recommended_action": ACTION_DUPLICATE,
    })
    monkeypatch.setattr(generate, "client", fake)
    cache = generate._load_semantic_publication_gate_cache()
    report = generate._new_semantic_publication_gate_report()

    cleaned, redirects, repair = generate._repair_recent_semantic_archive_duplicates(
        [canonical, duplicate],
        tmp_path / "articles",
        tmp_path,
        cache,
        report,
    )

    assert [row["slug"] for row in cleaned] == [CANONICAL_SLUG]
    assert repair["repaired_count"] == 1
    assert redirects[0]["source_slug"] == DUPLICATE_SLUG
    assert redirects[0]["target_slug"] == CANONICAL_SLUG
    assert redirects[0]["identity_evidence"]["proof_type"] == (
        "claude_final_semantic_publication_gate"
    )
    assert fake.messages.calls


def test_semantic_gate_cache_reuses_pair_decision(tmp_path, monkeypatch):
    generate = _load_generate(tmp_path)
    canonical = _archive_row(
        CANONICAL_SLUG, CANONICAL_HEADLINE, "2026-07-31", "story_001557"
    )
    incoming = _archive_row(
        DUPLICATE_SLUG, INCOMING_HEADLINE, "2026-08-01", "story_001684"
    )
    _write_page(tmp_path, CANONICAL_SLUG)
    fake = _Client({
        "selected_candidate_slug": CANONICAL_SLUG,
        "same_real_world_event": True,
        "material_new_update": False,
        "confidence": 0.99,
        "shared_anchors": ["same victim and intersection"],
        "novel_facts": [],
        "reason": "Same event.",
        "recommended_action": ACTION_DUPLICATE,
    })
    monkeypatch.setattr(generate, "client", fake)
    cache = generate._load_semantic_publication_gate_cache()
    report = generate._new_semantic_publication_gate_report()

    first, _, _ = generate._run_semantic_publication_gate(
        incoming, [canonical], cache, report
    )
    second, _, _ = generate._run_semantic_publication_gate(
        incoming, [canonical], cache, report
    )

    assert first["action"] == ACTION_DUPLICATE
    assert second["action"] == ACTION_DUPLICATE
    assert len(fake.messages.calls) == 1
    assert report["summary"]["cache_hits"] == 1


def test_transient_model_failure_is_not_cached(tmp_path, monkeypatch):
    generate = _load_generate(tmp_path)
    canonical = _archive_row(
        CANONICAL_SLUG, CANONICAL_HEADLINE, "2026-07-31", "story_001557"
    )
    incoming = _archive_row(
        DUPLICATE_SLUG, INCOMING_HEADLINE, "2026-08-01", "story_001684"
    )
    _write_page(tmp_path, CANONICAL_SLUG)
    fake = _Client(error=RuntimeError("temporary API failure"))
    monkeypatch.setattr(generate, "client", fake)
    cache = generate._load_semantic_publication_gate_cache()
    report = generate._new_semantic_publication_gate_report()

    first, _, _ = generate._run_semantic_publication_gate(
        incoming, [canonical], cache, report
    )
    assert first["action"] == ACTION_HOLD
    assert cache["entries"] == {}

    fake.messages.error = None
    fake.messages.payload = {
        "selected_candidate_slug": CANONICAL_SLUG,
        "same_real_world_event": True,
        "material_new_update": False,
        "confidence": 0.99,
        "shared_anchors": ["same victim and intersection"],
        "novel_facts": [],
        "reason": "Same event.",
        "recommended_action": ACTION_DUPLICATE,
    }
    second, _, _ = generate._run_semantic_publication_gate(
        incoming, [canonical], cache, report
    )

    assert second["action"] == ACTION_DUPLICATE
    assert len(fake.messages.calls) == 2
    assert len(cache["entries"]) == 1
