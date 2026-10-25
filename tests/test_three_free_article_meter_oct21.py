from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_signed_server_meter_upgrades_one_read_without_reset():
    code = (ROOT / "supabase/functions/protected-article/index.ts").read_text()
    assert "two_free_articles_per_month" in code
    assert "const FREE_ARTICLE_LIMIT = 2" in code
    assert "parsed.v === 1 ? [parsed.slug]" in code
    assert "new Set(slugs).size !== slugs.length" in code
    assert "slugs.length > MAX_RECOGNIZED_METER_SLUGS" in code
    assert "const MAX_RECOGNIZED_METER_SLUGS = 3" in code
    assert "usedSlugs.includes(slug)" in code
    assert "usedSlugs.length >= FREE_ARTICLE_LIMIT" in code
    assert "slugs: nextSlugs" in code
    assert "remaining_free_articles: Math.max(0, FREE_ARTICLE_LIMIT - nextSlugs.length)" in code
    assert "free_articles_per_period: FREE_ARTICLE_LIMIT" in code
    assert "if (await hasMembership(ctx, userId))" in code


def test_client_migrates_legacy_one_slug_and_keeps_after_read_card_at_second():
    code = (ROOT / "membership.js").read_text()
    assert "const FREE_ARTICLE_LIMIT = 2" in code
    assert "Array.isArray(state.slugs) ? state.slugs : state.slug ? [state.slug] : []" in code
    assert "slugs.length > MAX_RECOGNIZED_METER_SLUGS" in code
    assert "const MAX_RECOGNIZED_METER_SLUGS = 3" in code
    assert "!state.slugs.includes(slug) && state.slugs.length >= FREE_ARTICLE_LIMIT" in code
    assert "const usedSlugs = Array.isArray(data.used_slugs)" in code
    assert "if (usedSlugs.length >= FREE_ARTICLE_LIMIT)" in code
    assert "paywall?.remove()" in code
    assert "You've read both free articles this month." in code


def test_workflow_probes_two_free_capability_and_upgrades_live_endpoint():
    code = (ROOT / ".github/workflows/update.yml").read_text()
    assert 'payload.get("meter_policy") == "two_free_articles_per_month"' in code
    assert 'payload.get("free_articles_per_period") == 2' in code
    assert 'handle.write("needs_deploy=true\\n")' in code
    assert 'supabase functions deploy protected-article --use-api' in code
