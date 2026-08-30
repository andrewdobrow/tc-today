from pathlib import Path


def test_generator_writes_v1370_observe_only_homepage_editorial_ranking_reports():
    text = Path("scripts/generate.py").read_text(encoding="utf-8")
    assert 'homepage-ranking-recommendations.json' in text
    assert 'homepage-ranking-review.md' in text
    assert 'Homepage editorial ranking shadow' in text
    assert 'observe-only' in text
    assert 'write_homepage_ranking_recommendations(' in text
    assert 'current_deck_count=_top_stories_report.get("selected_count", len(topnews))' in text
