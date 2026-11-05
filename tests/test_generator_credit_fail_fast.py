"""Regression tests for credit-exhaustion fail-fast generation."""
from __future__ import annotations

import sys
import time

from scripts.run_generator_fail_fast import EXIT_CREDITS_EXHAUSTED, run_generator


def _fake_python(script: str) -> list[str]:
    return [sys.executable, "-u", "-c", script]


def test_successful_generation_logs_and_preserves_exit_zero(tmp_path, capsys):
    log = tmp_path / "generate.log"
    result = run_generator(_fake_python("print('generated one article')"), log)
    assert result == 0
    assert "generated one article" in log.read_text()
    assert "generated one article" in capsys.readouterr().out


def test_transient_429_does_not_trigger_credit_shutdown(tmp_path):
    log = tmp_path / "generate.log"
    code = "print('HTTP 429 rate_limit_exceeded; retrying'); print('generation complete')"
    result = run_generator(_fake_python(code), log)
    assert result == 0
    assert "generation complete" in log.read_text()


def test_first_insufficient_quota_error_stops_before_long_fallback(tmp_path):
    log = tmp_path / "generate.log"
    finished = tmp_path / "should-not-exist.txt"
    script = (
        "import time, pathlib; "
        "print(\"Error code: 429 credit_balance_exhausted; you have no credits remaining\", flush=True); "
        "time.sleep(12); "
        f"pathlib.Path({str(finished)!r}).write_text('too late')"
    )
    start = time.monotonic()
    result = run_generator(_fake_python(script), log)
    assert result == EXIT_CREDITS_EXHAUSTED
    assert time.monotonic() - start < 6
    assert not finished.exists()
    assert "credit_balance_exhausted" in log.read_text()


def test_generic_child_failure_preserves_nonzero_exit_status(tmp_path):
    log = tmp_path / "generate.log"
    result = run_generator(_fake_python("import sys; print('bad input'); sys.exit(7)"), log)
    assert result == 7
    assert "bad input" in log.read_text()


def test_insufficient_quota_marker_exits_before_next_output(tmp_path):
    log = tmp_path / "generate.log"
    code = (
        "print(\"insufficient_quota\", flush=True); "
        "print(\"this message must not occur\", flush=True)"
    )
    assert run_generator(_fake_python(code), log) == EXIT_CREDITS_EXHAUSTED
