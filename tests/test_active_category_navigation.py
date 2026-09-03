from pathlib import Path
import re

SOURCE = Path("scripts/generate.py").read_text(encoding="utf-8")


def test_active_header_category_remains_a_real_link():
    """The active tab must navigate back to its listing, not become inert."""
    assert "return f'<span class=\"{cls}\">{label}</span>'" not in SOURCE
    assert "aria-current=\"page\"" in SOURCE
    assert 'f"/?cat={key}"' in SOURCE


def test_retained_article_headers_are_migrated_sitewide():
    """Old article HTML must be repaired, not only newly rendered pages."""
    assert "def _normalize_active_category_navigation_sitewide(output_root):" in SOURCE
    assert "Active category navigation contract PASSED" in SOURCE
    assert re.search(
        r"_normalize_active_category_navigation_sitewide\(OUTPUT_DIR\)",
        SOURCE,
    )
