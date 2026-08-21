from pathlib import Path
from types import SimpleNamespace

from tct_engine.model_usage import ModelUsageTracker, instrument_anthropic_client


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, messages):
        self.messages = messages
        self.options = []

    def with_options(self, *args, **kwargs):
        self.options.append((args, kwargs))
        clone = FakeClient(self.messages)
        clone.options = self.options
        return clone


def _response(*, model="claude-sonnet-4-5", base=1000, output=100, cache_write=2000, cache_read=3000):
    usage = SimpleNamespace(
        input_tokens=base,
        output_tokens=output,
        cache_creation_input_tokens=cache_write,
        cache_read_input_tokens=cache_read,
    )
    return SimpleNamespace(model=model, usage=usage, content=[SimpleNamespace(text="ok")])


def test_tracker_records_tokens_cache_and_current_sonnet_list_cost(tmp_path):
    tracker = ModelUsageTracker(tmp_path / "model-usage-report.json")
    fake = FakeClient(FakeMessages(_response()))
    client = instrument_anthropic_client(fake, tracker)

    response = client.messages.create(model="claude-sonnet-4-5", max_tokens=100)
    assert response.content[0].text == "ok"

    report = tracker.build_report()
    totals = report["totals"]
    assert totals["requests"] == 1
    assert totals["base_input_tokens"] == 1000
    assert totals["cache_write_tokens"] == 2000
    assert totals["cache_read_tokens"] == 3000
    assert totals["total_input_context_tokens"] == 6000
    assert totals["output_tokens"] == 100
    # $0.003 input + $0.0075 5m cache write + $0.0009 cache read + $0.0015 output.
    assert totals["estimated_list_cost_usd"] == 0.0129
    assert report["pricing_catalog"]["claude-sonnet-4-5"]["source_date"] == "2026-06-30"


def test_with_options_remains_instrumented_and_returns_same_response(tmp_path):
    tracker = ModelUsageTracker(tmp_path / "model-usage-report.json")
    fake = FakeClient(FakeMessages(_response(base=10, output=5, cache_write=0, cache_read=0)))
    client = instrument_anthropic_client(fake, tracker)

    tuned = client.with_options(timeout=12, max_retries=0)
    response = tuned.messages.create(model="claude-sonnet-4-5", max_tokens=50)

    assert response.content[0].text == "ok"
    assert fake.options == [((), {"timeout": 12, "max_retries": 0})]
    assert tracker.build_report()["totals"]["requests"] == 1


def test_unknown_model_keeps_raw_usage_for_future_repricing(tmp_path):
    tracker = ModelUsageTracker(tmp_path / "model-usage-report.json")
    fake = FakeClient(FakeMessages(_response(model="future-model", base=50, output=7)))
    client = instrument_anthropic_client(fake, tracker)
    client.messages.create(model="future-model", max_tokens=20)

    report = tracker.build_report()
    assert report["totals"]["requests"] == 1
    assert report["totals"]["unpriced_requests"] == 1
    assert report["calls"][0]["estimated_list_cost_usd"] is None
    assert report["calls"][0]["tokens"]["total_input_context"] == 5050


def test_request_failure_is_observed_but_original_exception_is_preserved(tmp_path):
    tracker = ModelUsageTracker(tmp_path / "model-usage-report.json")
    fake = FakeClient(FakeMessages(error=RuntimeError("synthetic failure")))
    client = instrument_anthropic_client(fake, tracker)

    try:
        client.messages.create(model="claude-sonnet-4-5")
    except RuntimeError as exc:
        assert str(exc) == "synthetic failure"
    else:
        raise AssertionError("expected original RuntimeError")

    report = tracker.build_report()
    assert report["totals"]["requests"] == 0
    assert report["failed_requests_without_usage"] == 1
    assert report["failures"][0]["error_type"] == "RuntimeError"


def test_report_write_is_atomic_and_contains_no_prompt_or_response_text(tmp_path):
    path = tmp_path / "data" / "model-usage-report.json"
    tracker = ModelUsageTracker(path)
    fake = FakeClient(FakeMessages(_response()))
    client = instrument_anthropic_client(fake, tracker)
    client.messages.create(model="claude-sonnet-4-5", messages=[{"role": "user", "content": "SECRET PROMPT"}])

    tracker.write_report()
    text = path.read_text()
    assert "SECRET PROMPT" not in text
    assert '"provider": "anthropic"' in text
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_production_generator_uses_instrumented_client_and_finally_flushes_report():
    source = Path("scripts/generate.py").read_text()
    assert "instrument_anthropic_client(_raw_anthropic_client, MODEL_USAGE_TRACKER)" in source
    assert "MODEL_USAGE_TRACKER.reset()" in source
    assert "finally:\n        _finalize_model_usage_observability()" in source
    assert 'OUTPUT_DIR / "data" / "model-usage-report.json"' in source
