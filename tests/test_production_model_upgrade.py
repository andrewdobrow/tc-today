import ast
from pathlib import Path


def _literal_assignments(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                values[node.targets[0].id] = node.value.value
    return values


def test_production_article_and_selection_models_use_sonnet_5():
    source = Path("scripts/generate.py")
    values = _literal_assignments(source)
    assert values["MODEL_ARTICLES"] == "claude-sonnet-5"
    assert values["MODEL_SELECTION"] == "claude-sonnet-5"


def test_production_generator_has_no_sonnet_4_5_literal():
    source = Path("scripts/generate.py").read_text(encoding="utf-8")
    assert "claude-sonnet-4-5" not in source
