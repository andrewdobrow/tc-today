"""Regression for the v1.12.0 production NameError at final category enforcement."""

from __future__ import annotations

import ast
from pathlib import Path


def test_main_does_not_reference_write_archives_local_publication_identity():
    root = Path(__file__).resolve().parents[1]
    source = (root / "scripts" / "generate.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )

    loaded_names = {
        node.id
        for node in ast.walk(main)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert "_publication_identity" not in loaded_names


def test_final_category_contracts_use_their_self_loading_identity_interface():
    root = Path(__file__).resolve().parents[1]
    source = (root / "scripts" / "generate.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )

    calls = {
        node.func.id: node
        for node in ast.walk(main)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in {
            "canonicalize_all_live_category_surfaces",
            "validate_live_category_canonical_uniqueness",
        }
    }
    assert set(calls) == {
        "canonicalize_all_live_category_surfaces",
        "validate_live_category_canonical_uniqueness",
    }
    for call in calls.values():
        assert all(keyword.arg != "identity_index" for keyword in call.keywords)
