from __future__ import annotations

import importlib
import json
import os
import sys
import types
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path


def _load_generate_module():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser

    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(
                        RuntimeError("unexpected model call")
                    )
                )

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic

    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    return importlib.import_module("scripts.generate")


class _Response:
    def __init__(self, text: str):
        self.content = [types.SimpleNamespace(text=text)]


class _Messages:
    def __init__(self, text: str):
        self.text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.text)


class _Client:
    def __init__(self, text: str):
        self.messages = _Messages(text)


def _headline():
    return {
        "title": "Vero Beach council reviews waterfront project",
        "summary": "Vero Beach council members reviewed a waterfront project with local funding and construction details. " * 4,
        "article_text": "Vero Beach council members reviewed a waterfront project with local funding and construction details. " * 20,
        "published": format_datetime(datetime.now(timezone.utc)),
        "source_quality": "full",
        "source_type": "full_source",
        "hero_eligible": "yes",
        "category_match_score": 95,
        "link": "https://example.com/story",
        "image_url": "https://example.com/image.jpg",
    }


def test_null_hero_response_is_contained_without_attribute_error(monkeypatch):
    generate = _load_generate_module()
    fake = _Client('{"hero": null, "cards": []}')
    monkeypatch.setattr(generate, "client", fake)
    monkeypatch.setattr(generate, "load_archive", lambda *args, **kwargs: [])

    data = generate.generate_category_content(
        "indian_river",
        "Indian River County",
        [_headline()],
        request_timeout_seconds=7,
    )

    assert data["hero"] == {}
    assert data["cards"] == []
    assert data["_drop_category"] is True
    assert fake.messages.calls[0]["timeout"] == 7.0


def test_budgeted_generation_retries_and_returns_structured_failure(monkeypatch):
    generate = _load_generate_module()
    calls = []

    def fake_generate(*args, **kwargs):
        calls.append(kwargs["request_timeout_seconds"])
        if len(calls) == 1:
            raise ValueError("Model returned no JSON object")
        return {"hero": None, "cards": []}

    monkeypatch.setattr(generate, "generate_category_content", fake_generate)
    monkeypatch.setattr(generate, "CATEGORY_GENERATION_BUDGET_SECONDS", 30.0)
    monkeypatch.setattr(generate, "CATEGORY_MODEL_CALL_TIMEOUT_SECONDS", 20.0)
    monkeypatch.setattr(generate, "CATEGORY_GENERATION_MIN_RETRY_SECONDS", 1.0)

    data, diagnostics = generate._run_category_generation_with_budget(
        "indian_river", "Indian River County", [_headline()]
    )

    assert data is None
    assert diagnostics["status"] == "failed"
    assert diagnostics["attempt_count"] == 2
    assert diagnostics["attempts"][0]["result"] == "invalid_json"
    assert diagnostics["attempts"][1]["result"] == "missing_or_null_hero"
    assert diagnostics["failure_code"] == "missing_or_null_hero"
    assert calls[0] <= 20.0
    assert calls[1] <= 20.0


def test_budgeted_generation_succeeds_on_second_attempt(monkeypatch):
    generate = _load_generate_module()
    calls = []

    def fake_generate(*args, **kwargs):
        calls.append(kwargs["request_timeout_seconds"])
        if len(calls) == 1:
            raise ValueError("invalid JSON")
        return {"hero": {"headline": "Valid local story"}, "cards": []}

    monkeypatch.setattr(generate, "generate_category_content", fake_generate)
    monkeypatch.setattr(generate, "CATEGORY_GENERATION_BUDGET_SECONDS", 30.0)
    monkeypatch.setattr(generate, "CATEGORY_MODEL_CALL_TIMEOUT_SECONDS", 20.0)
    monkeypatch.setattr(generate, "CATEGORY_GENERATION_MIN_RETRY_SECONDS", 1.0)

    data, diagnostics = generate._run_category_generation_with_budget(
        "martin", "Martin County", [_headline()]
    )

    assert data["hero"]["headline"] == "Valid local story"
    assert diagnostics["status"] == "success"
    assert diagnostics["attempt_count"] == 2
    assert diagnostics["attempts"][1]["result"] == "success"


def test_category_generation_report_records_recovery_and_policy(tmp_path: Path):
    generate = _load_generate_module()
    records = [
        {
            "category_key": "business",
            "category_label": "Business & Development",
            "status": "generated_live",
            "attempt_count": 1,
            "model_elapsed_seconds": 12.5,
            "archive_recovery_requested": False,
            "failure_code": "",
        },
        {
            "category_key": "indian_river",
            "category_label": "Indian River County",
            "status": "generation_failed_archive_recovery",
            "attempt_count": 2,
            "model_elapsed_seconds": 30.0,
            "archive_recovery_requested": True,
            "failure_code": "missing_or_null_hero",
        },
    ]
    output = tmp_path / "category-generation-report.json"

    report = generate._write_category_generation_report(records, output)
    persisted = json.loads(output.read_text(encoding="utf-8"))

    assert report["summary"]["model_attempt_count"] == 3
    assert report["summary"]["archive_recovery_requested_count"] == 1
    assert report["summary"]["failures"]["missing_or_null_hero"] == 1
    assert "https://www.wptv.com/feeds/rss/news" in report["policy"]["removed_dead_feeds"]
    assert persisted == report


def test_dead_wptv_content_bank_feeds_are_removed():
    generate = _load_generate_module()

    assert "https://www.wptv.com/feeds/rss/news" not in generate.CONTENT_BANK_FEEDS
    assert "https://www.wptv.com/feeds/rss/local" not in generate.CONTENT_BANK_FEEDS


def test_editorial_observability_embeds_category_generation_report(tmp_path: Path, monkeypatch):
    generate = _load_generate_module()
    output = tmp_path / "editorial_observability.json"
    monkeypatch.setattr(generate, "EDITORIAL_OBSERVABILITY_PATH", output)

    base_report = {
        "engine": {"version": "test", "release": "test"},
        "stories": {"total": 0, "importance_levels": {}, "average_importance": 0},
        "audit": {"candidates_processed": 0, "rejected_count": 0},
        "relationships": {"counts": {}},
        "follow_up_detection": {"retrospective": {}},
    }

    def fake_writer(*args, **kwargs):
        output.write_text(json.dumps(base_report), encoding="utf-8")
        return dict(base_report)

    monkeypatch.setattr(generate, "write_editorial_observability", fake_writer)
    category_report = {
        "summary": {"model_attempt_count": 2, "archive_recovery_requested_count": 1},
        "categories": [],
    }

    generate._write_editorial_observability(
        object(), [], None, category_generation=category_report
    )

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["category_generation"] == category_report


def test_category_request_disables_hidden_sdk_retries(monkeypatch):
    generate = _load_generate_module()

    class _OptionsClient:
        def __init__(self):
            self.option_calls = []
            self.messages = _Messages('{"hero": null, "cards": []}')

        def with_options(self, **kwargs):
            self.option_calls.append(kwargs)
            return self

    fake = _OptionsClient()
    monkeypatch.setattr(generate, "client", fake)
    monkeypatch.setattr(generate, "load_archive", lambda *args, **kwargs: [])

    generate.generate_category_content(
        "indian_river",
        "Indian River County",
        [_headline()],
        request_timeout_seconds=11,
    )

    assert fake.option_calls == [{"timeout": 11.0, "max_retries": 0}]
    assert "timeout" not in fake.messages.calls[0]
