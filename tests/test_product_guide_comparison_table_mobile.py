from pathlib import Path


def _source():
    return (Path(__file__).resolve().parents[1] / "scripts" / "generate.py").read_text(encoding="utf-8")


def test_comparison_table_scrolls_instead_of_crushing_mobile_columns():
    source = _source()
    assert (
        ".pg-comparison {{ box-sizing:border-box; width:100%; max-width:100%; "
        "overflow-x:auto; -webkit-overflow-scrolling:touch;"
    ) in source
    assert (
        ".pg-comparison table {{ width:100%; min-width:760px; "
        "border-collapse:collapse; table-layout:auto;"
    ) in source


def test_comparison_cells_never_break_words_into_fragments():
    source = _source()
    assert "overflow-wrap:normal!important" in source
    assert "word-break:normal!important" in source
    assert "hyphens:none!important" in source
    assert (
        ".pg-comparison th:nth-child(1),.pg-comparison td:nth-child(1) {{ min-width:190px; }}"
    ) in source
    assert (
        ".pg-comparison th:nth-child(2),.pg-comparison td:nth-child(2) {{ min-width:260px; }}"
    ) in source


def test_comparison_layout_change_forces_existing_guides_to_republish():
    assert 'PRODUCT_GUIDE_TEMPLATE_VERSION = "1.6-scroll-safe-comparison-table"' in _source()
