#!/usr/bin/env python3
"""Run TCT generation while aborting immediately on confirmed exhausted AI credits.

Production previously spent another 15+ minutes generating archive fallbacks
after its first credit_balance_exhausted response, then failed the end-of-run
billing guard. Preserve the same log for that guard, but fail fast as soon as
an explicit billing/quota marker appears in live generator output.

Ordinary HTTP 429 throttling is NOT a credit-exhaustion signal.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys

# Support both "python scripts/run_generator_fail_fast.py" and test imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.check_editorial_api_credits import has_exhausted_credits


EXIT_CREDITS_EXHAUSTED = 78


def _stop_process_group(process: subprocess.Popen) -> None:
    """Stop generator and its subprocesses, not only its top-level PID."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def run_generator(command: list[str], log_path: Path) -> int:
    if not command:
        raise ValueError("No generator command specified")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as logfile:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            start_new_session=True,
        )
        try:
            assert process.stdout is not None
            for line in process.stdout:
                logfile.write(line)
                logfile.flush()
                print(line, end="", flush=True)
                if has_exhausted_credits(line):
                    warning = (
                        "Confirmed editorial AI API credit exhaustion; stopping "
                        "generator immediately. Existing published site is unchanged. "
                        "Restore provider credits before re-running Update."
                    )
                    print(
                        "::error title=TCT editorial credits exhausted::" + warning,
                        flush=True,
                    )
                    _stop_process_group(process)
                    return EXIT_CREDITS_EXHAUSTED
            return process.wait()
        except BaseException:
            _stop_process_group(process)
            raise
        finally:
            if process.stdout is not None:
                process.stdout.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command[:1] == ["--"]:
        command.pop(0)
    if not command:
        command = [sys.executable, "-u", "scripts/generate.py"]
    try:
        return run_generator(command, args.log)
    except (OSError, ValueError) as exc:
        print(
            f"::error title=TCT generator launch failed::{exc}",
            flush=True,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
