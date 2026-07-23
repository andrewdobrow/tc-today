import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest


class _DummyMessages:
    def create(self, *args, **kwargs):
        raise RuntimeError("AI calls are disabled in offline regression tests")


class _DummyAnthropicClient:
    def __init__(self, *args, **kwargs):
        self.messages = _DummyMessages()


def _install_dependency_stubs():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser

    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")
        anthropic.Anthropic = _DummyAnthropicClient
        sys.modules["anthropic"] = anthropic


@pytest.fixture(scope="session")
def engine():
    _install_dependency_stubs()
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = Path(__file__).resolve().parents[1] / "engine.py"
    spec = importlib.util.spec_from_file_location("tct_engine", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module
