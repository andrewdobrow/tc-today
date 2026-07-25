from pathlib import Path


def test_generator_writes_observe_only_homepage_ranking_report():
    text = Path("scripts/generate.py").read_text(encoding="utf-8")
    assert 'homepage-ranking-recommendations.json' in text
    assert 'observe-only' in text
    assert 'write_homepage_ranking_recommendations(' in text
