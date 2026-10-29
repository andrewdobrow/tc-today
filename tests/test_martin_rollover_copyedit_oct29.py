"""Regression: source-limited crash briefs must not repeat the same facts seven times."""
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "articles" / "2026-10-29-one-hospitalized-after-rollover-on-sw-martin-highway-in-martin-county.html"

def test_martin_rollover_copyedit_is_concise():
    soup = BeautifulSoup(PAGE.read_text(encoding="utf-8"), "html.parser")
    body = soup.select_one(".article-body")
    assert body is not None
    paragraphs = [p.get_text(" ", strip=True) for p in body.select("p") if p.get_text(" ", strip=True)]
    assert len(paragraphs) == 2
    text = " ".join(paragraphs)
    assert "SW Martin Highway" in text
    assert "Fox Brown Road" in text
    assert "hospital" in text.lower()
    assert "delays" in text.lower()
    assert "The traffic message centered" not in text
