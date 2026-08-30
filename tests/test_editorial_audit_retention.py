from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.compact_editorial_audit import compact_editorial_audit_log


def _write_rows(path: Path, count: int, payload_chars: int = 120) -> list[bytes]:
    rows = []
    with path.open("wb") as handle:
        for index in range(count):
            row = (
                json.dumps(
                    {
                        "timestamp": f"2026-08-29T12:{index % 60:02d}:00Z",
                        "index": index,
                        "diagnostic": "x" * payload_chars,
                    },
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            rows.append(row)
            handle.write(row)
    return rows


def test_editorial_audit_retention_keeps_newest_complete_rows_byte_for_byte(tmp_path: Path) -> None:
    path = tmp_path / "editorial_audit.jsonl"
    rows = _write_rows(path, 80, payload_chars=120)
    report = compact_editorial_audit_log(path, trigger_bytes=5000, target_bytes=3000)

    assert report["compacted"] is True
    assert report["bytes_before"] > 5000
    assert report["bytes_after"] <= 3000
    assert report["bytes_reclaimed"] > 0

    retained = path.read_bytes().splitlines(keepends=True)
    assert retained
    assert retained == rows[-len(retained):]
    assert report["retained_rows"] == len(retained)
    for line in retained:
        json.loads(line)


def test_editorial_audit_retention_is_noop_below_trigger(tmp_path: Path) -> None:
    path = tmp_path / "editorial_audit.jsonl"
    original = b''.join(_write_rows(path, 3, payload_chars=20))

    report = compact_editorial_audit_log(path, trigger_bytes=5000, target_bytes=3000)

    assert report["compacted"] is False
    assert report["reason"] == "below_trigger"
    assert path.read_bytes() == original


def test_editorial_audit_retention_rejects_invalid_hysteresis(tmp_path: Path) -> None:
    path = tmp_path / "editorial_audit.jsonl"
    _write_rows(path, 2)

    with pytest.raises(ValueError):
        compact_editorial_audit_log(path, trigger_bytes=1000, target_bytes=1000)


def test_generator_applies_retention_after_appending_audit_rows() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "scripts" / "generate.py").read_text(encoding="utf-8")
    save_start = source.index("def _save_editorial_engine_audit")
    save_end = source.index("\ndef _prepare_editorial_activation", save_start)
    save_block = source[save_start:save_end]

    assert 'open("a", encoding="utf-8")' in save_block
    assert "compact_editorial_audit_log(EDITORIAL_AUDIT_LOG_PATH)" in save_block


def test_production_workflow_compacts_audit_before_tests_and_keeps_large_file_guard() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")

    compact_pos = workflow.index("Bound persistent editorial audit history")
    test_pos = workflow.index("Run editorial engine tests")
    guard_pos = workflow.index("Guard generated repository size")
    assert compact_pos < test_pos < guard_pos
    assert "python scripts/compact_editorial_audit.py" in workflow
    assert "-size +90M" in workflow
