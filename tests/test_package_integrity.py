"""Release-integrity tests for the tct_engine package."""

from __future__ import annotations

import importlib
import pkgutil

import tct_engine


def test_all_package_modules_import() -> None:
    failures: list[str] = []
    for module in pkgutil.walk_packages(
        tct_engine.__path__, prefix="tct_engine."
    ):
        try:
            importlib.import_module(module.name)
        except Exception as exc:
            failures.append(f"{module.name}: {type(exc).__name__}: {exc}")

    assert failures == [], "\n".join(failures)


def test_all_public_exports_exist() -> None:
    missing = [name for name in tct_engine.__all__ if not hasattr(tct_engine, name)]
    assert missing == [], f"Missing public exports: {missing}"


def test_editorial_proximity_module_is_packaged() -> None:
    module = importlib.import_module("tct_engine.editorial_proximity")
    assert hasattr(module, "calculate_editorial_priority")
