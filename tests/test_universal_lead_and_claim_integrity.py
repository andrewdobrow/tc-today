from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import pytest


def _load_generate():
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    if "json_repair" not in sys.modules:
        json_repair = types.ModuleType("json_repair")
        json_repair.repair_json = lambda value: value
        sys.modules["json_repair"] = json_repair
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = Path(__file__).parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location(
        "generate_universal_lead_claim_test", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CURRENT_HEADLINE = (
    "Port St. Lucie faces $48 million revenue loss if property tax amendment "
    "passes in November"
)
SOURCE_HEADLINE = (
    "St. Lucie County could lose $63 million in funding if property tax goes "
    "away - WPEC"
)
OLD_SLUG = (
    "2026-07-28-st-lucie-county-could-lose-63-million-if-property-tax-"
    "amendment-passes"
)
BAD_LEAD_BODY = (
    "Port St. Lucie would lose over $48 million in property taxes over the next "
    "two years if Amendment 3 passes on the November 3 ballot, City Manager Jesus "
    "Merejo told the City Council during a summer budget workshop at the Port St. "
    "Lucie Community Center on Thursday. The city is not funding 184 requested "
    "positions worth $28.3 million, including 25 new police officers."
    "\n\nThe city canceled $7.8 million in projects and froze additional hiring."
    "\n\nAmendment 3 would raise the state's homestead exemption from $50,000 to "
    "$150,000 in 2027 and to $250,000 in 2028. The constitutional amendment needs "
    "60% voter approval."
)
GOOD_LEAD_BODY = (
    "Port St. Lucie officials say the city could lose more than $48 million in "
    "property-tax revenue over two years under Amendment 3, a proposed "
    "constitutional amendment that would raise Florida's homestead exemption "
    "beginning in 2027. City leaders are withholding funding for 184 requested "
    "positions as they prepare for the possible loss."
    "\n\nThe city also canceled $7.8 million in projects and froze additional hiring."
)
MISMATCHED_HEADLINE = (
    "St. Lucie County could lose $63 million if property tax amendment passes"
)
SOURCE_TEXT = (
    "Port St. Lucie held a city budget workshop. City Manager Jesus Merejo said "
    "the city could lose more than $48 million over two years if Amendment 3 "
    "passes. Amendment 3 would raise Florida's homestead exemption to $150,000 in "
    "2027 and $250,000 in 2028. The city is withholding 184 requested positions "
    "and canceling $7.8 million in projects."
)


class _Response:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(text=text)]


class _Messages:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.text)


class _Client:
    def __init__(self, text):
        self.messages = _Messages(text)


def _source():
    return {
        "title": SOURCE_HEADLINE,
        "summary": SOURCE_TEXT,
        "article_text": SOURCE_TEXT,
        "published": format_datetime(datetime.now(timezone.utc)),
        "source_quality": "full",
        "source_type": "full_source",
        "hero_eligible": "yes",
        "category_match_score": 99,
        "link": "https://cbs12.com/news/local/property-tax-story",
        "image_url": "",
        "feed_url": "https://example.com/rss",
    }


def _payload(hero_body, hero_headline=CURRENT_HEADLINE, cards=None):
    return json.dumps(
        {
            "hero": {
                "headline": hero_headline,
                "body": hero_body,
                "urgency_score": 6,
                "published": format_datetime(datetime.now(timezone.utc)),
                "source_index": 1,
            },
            "cards": cards or [],
        }
    )


def test_exact_live_lead_fails_because_amendment_is_undefined():
    g = _load_generate()
    item = {"headline": CURRENT_HEADLINE, "body": BAD_LEAD_BODY}

    diagnostics = g._article_framing_diagnostics(item, item)

    assert diagnostics["passed"] is False
    assert "named_measure_undefined_in_lead" in diagnostics["missing"]
    assert diagnostics["lead_independence"]["undefined_references"] == ["Amendment 3"]
    assert diagnostics["claim_consistency"]["passed"] is True


def test_corrected_lead_defines_measure_and_stands_alone():
    g = _load_generate()
    item = {"headline": CURRENT_HEADLINE, "body": GOOD_LEAD_BODY}

    diagnostics = g._article_framing_diagnostics(item, item)

    assert diagnostics["passed"] is True
    assert diagnostics["missing"] == []


def test_original_generated_headline_conflicted_with_lead_amount_and_jurisdiction():
    g = _load_generate()
    item = {"headline": MISMATCHED_HEADLINE, "body": BAD_LEAD_BODY}

    diagnostics = g._headline_lead_claim_diagnostics(item)

    assert diagnostics["passed"] is False
    assert diagnostics["missing_money_claims"] == [63_000_000]
    assert diagnostics["missing_jurisdictions"] == ["st_lucie_county"]
    assert "headline_money_claim_missing_from_lead" in diagnostics["missing"]
    assert "headline_jurisdiction_missing_from_lead" in diagnostics["missing"]


def test_slug_claim_guard_detects_exact_property_tax_permalink_drift():
    g = _load_generate()
    item = {"headline": CURRENT_HEADLINE, "body": GOOD_LEAD_BODY}
    entry = {"slug": OLD_SLUG, "headline": CURRENT_HEADLINE}

    diagnostics = g._publication_slug_claim_diagnostics(item, entry)

    assert diagnostics["rebind_required"] is True
    assert diagnostics["slug_money_claims"] == [63_000_000]
    assert diagnostics["current_money_claims"] == [48_000_000]
    assert diagnostics["slug_jurisdictions"] == ["st_lucie_county"]
    assert diagnostics["current_jurisdictions"] == ["port_st_lucie"]


def test_generation_prompt_requires_definition_and_matching_claim(monkeypatch):
    g = _load_generate()
    fake = _Client(_payload(GOOD_LEAD_BODY))
    monkeypatch.setattr(g, "client", fake)
    monkeypatch.setattr(g, "load_archive", lambda *args, **kwargs: [])

    data = g.generate_category_content("st_lucie", "St. Lucie County", [_source()])

    prompt = fake.messages.calls[0]["messages"][0]["content"]
    assert "Do not use the headline as a substitute for context" in prompt
    assert "define what it would do in the FIRST paragraph" in prompt
    assert "Every specific jurisdiction and monetary amount stated in the headline" in prompt
    assert data["hero"]["headline"] == CURRENT_HEADLINE


def test_contextless_standard_hero_raises_bounded_retry_error(monkeypatch):
    g = _load_generate()
    fake = _Client(_payload(BAD_LEAD_BODY))
    monkeypatch.setattr(g, "client", fake)
    monkeypatch.setattr(g, "load_archive", lambda *args, **kwargs: [])

    with pytest.raises(g.ArticleFramingIntegrityError, match="named_measure_undefined_in_lead"):
        g.generate_category_content("st_lucie", "St. Lucie County", [_source()])


def test_invalid_standard_card_is_dropped(monkeypatch):
    g = _load_generate()
    card = {
        "headline": CURRENT_HEADLINE,
        "teaser": "City leaders are preparing for a possible revenue loss.",
        "body": BAD_LEAD_BODY,
        "urgency_score": 4,
        "published": format_datetime(datetime.now(timezone.utc)),
        "source_index": 1,
    }
    fake = _Client(_payload(GOOD_LEAD_BODY, cards=[card]))
    monkeypatch.setattr(g, "client", fake)
    monkeypatch.setattr(g, "load_archive", lambda *args, **kwargs: [])

    data = g.generate_category_content("st_lucie", "St. Lucie County", [_source()])

    assert data["cards"] == []
    assert data["_article_framing_rejections"][0]["surface"] == "card"


def test_custom_article_is_exempt_from_automated_framing_rewrite():
    g = _load_generate()
    item = {
        "headline": CURRENT_HEADLINE,
        "body": BAD_LEAD_BODY,
        "is_custom": True,
        "authoritative_custom": True,
    }

    diagnostics = g._article_framing_diagnostics(item, item)
    kept, rejected = g._filter_article_framing_live_placements([item])

    assert diagnostics["required"] is False
    assert kept == [item]
    assert rejected == []


def test_live_surface_guard_suppresses_existing_bad_standard_article():
    g = _load_generate()
    bad = {
        "headline": CURRENT_HEADLINE,
        "body": BAD_LEAD_BODY,
        "slug": OLD_SLUG,
        "category_key": "st_lucie",
    }
    good = {
        "headline": "Port St. Lucie council approves new road project",
        "body": (
            "Port St. Lucie City Council approved a $4 million road project Tuesday, "
            "authorizing construction to begin this fall. The work will add turn lanes "
            "and improve drainage near the intersection."
        ),
    }

    kept, rejected = g._filter_article_framing_live_placements([bad, good])

    assert kept == [good]
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "article_framing_integrity"


def test_budgeted_generation_retries_universal_framing_failure(monkeypatch):
    g = _load_generate()
    calls = []

    def fake_generate(*args, **kwargs):
        calls.append(kwargs["request_timeout_seconds"])
        if len(calls) == 1:
            raise g.ArticleFramingIntegrityError(
                "Article framing integrity failed: named_measure_undefined_in_lead"
            )
        return {
            "hero": {"headline": CURRENT_HEADLINE, "body": GOOD_LEAD_BODY},
            "cards": [],
            "_article_framing_rejections": [],
            "_contextual_update_lead_rejections": [],
        }

    monkeypatch.setattr(g, "generate_category_content", fake_generate)
    monkeypatch.setattr(g, "CATEGORY_GENERATION_BUDGET_SECONDS", 30.0)
    monkeypatch.setattr(g, "CATEGORY_MODEL_CALL_TIMEOUT_SECONDS", 20.0)
    monkeypatch.setattr(g, "CATEGORY_GENERATION_MIN_RETRY_SECONDS", 1.0)

    data, diagnostics = g._run_category_generation_with_budget(
        "st_lucie", "St. Lucie County", [_source()]
    )

    assert data["hero"]["headline"] == CURRENT_HEADLINE
    assert diagnostics["attempt_count"] == 2
    assert diagnostics["attempts"][0]["result"] == "article_framing_integrity"


def test_archive_lead_repair_promotes_existing_definition(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    html = (
        '<div class="article-body">'
        f"<p>{BAD_LEAD_BODY.split(chr(10)+chr(10))[0]}</p>"
        "<p>The city canceled several projects.</p>"
        "<p>Amendment 3 would raise the state's homestead exemption from $50,000 "
        "to $150,000 in 2027 and to $250,000 in 2028. Voters must approve it.</p>"
        '</div><div class="article-share">Share</div>'
    )
    (articles / f"{OLD_SLUG}.html").write_text(html, encoding="utf-8")
    entry = {
        "slug": OLD_SLUG,
        "headline": CURRENT_HEADLINE,
        "source_headline": SOURCE_HEADLINE,
    }

    archive, report = g._repair_archive_article_lead_framing(
        [entry], articles, tmp_path
    )

    assert archive[0]["lead_integrity_repaired"] is True
    assert report["repaired_count"] == 1
    repaired_body = g._archive_article_body(entry)
    assert g._article_framing_diagnostics(
        {"headline": CURRENT_HEADLINE, "body": repaired_body},
        {"headline": CURRENT_HEADLINE, "body": repaired_body},
    )["passed"] is True


def test_claim_aligned_permalink_migration_redirects_old_url(tmp_path, monkeypatch):
    g = _load_generate()
    monkeypatch.setattr(g, "OUTPUT_DIR", tmp_path)
    articles = tmp_path / "articles"
    articles.mkdir()
    (tmp_path / "data").mkdir()
    html = (
        f'<link rel="canonical" href="https://treasurecoast.today/articles/{OLD_SLUG}.html">'
        '<div class="article-body">'
        f"<p>{GOOD_LEAD_BODY.split(chr(10)+chr(10))[0]}</p>"
        "<p>The city canceled several projects.</p>"
        '</div><div class="article-share">Share</div>'
    )
    (articles / f"{OLD_SLUG}.html").write_text(html, encoding="utf-8")
    entry = {
        "slug": OLD_SLUG,
        "headline": CURRENT_HEADLINE,
        "teaser": GOOD_LEAD_BODY.split("\n\n")[0],
        "date": "2026-07-28",
        "editorial_story_id": "story-property-tax",
    }

    archive, redirects, report = g._repair_archive_claim_drifted_permalinks(
        [entry], articles, tmp_path
    )

    new_slug = archive[0]["slug"]
    assert report["repaired_count"] == 1
    assert new_slug.startswith("2026-07-28-port-st-lucie-faces-48-million")
    assert (articles / f"{new_slug}.html").exists()
    old_html = (articles / f"{OLD_SLUG}.html").read_text(encoding="utf-8")
    assert new_slug in old_html
    assert redirects[0]["target_slug"] == new_slug


def test_unrepaired_primary_claim_drift_fails_closed():
    g = _load_generate()
    item = {
        "headline": CURRENT_HEADLINE,
        "body": GOOD_LEAD_BODY,
        "source_url": "https://source.test/property-tax",
        "editorial_story_id": "story-property-tax",
    }
    entry = {
        "slug": OLD_SLUG,
        "headline": MISMATCHED_HEADLINE,
        "source_url": "https://source.test/property-tax",
        "editorial_story_id": "story-property-tax",
    }

    valid, reason = g._forward_publication_target_valid(
        item, entry, "story-property-tax", "persistent_story_id"
    )

    assert valid is False
    assert reason == "primary_claim_slug_drift_unrepaired"


def test_ordinary_same_story_headline_update_keeps_existing_permalink():
    g = _load_generate()
    item = {
        "headline": "Port St. Lucie council approves updated road construction schedule",
        "body": (
            "Port St. Lucie City Council approved an updated road construction "
            "schedule Tuesday, moving the project's start to October."
        ),
        "source_url": "https://www.wptv.com/news/local-news/road-project",
        "editorial_story_id": "story-road",
    }
    entry = {
        "slug": "2026-07-28-port-st-lucie-council-approves-road-project",
        "headline": "Port St. Lucie council approves road project",
        "source_url": "https://www.wptv.com/news/local-news/road-project",
        "editorial_story_id": "story-road",
    }

    valid, reason = g._forward_publication_target_valid(
        item, entry, "story-road", "persistent_story_id"
    )

    assert valid is True
    assert reason == "exact_source_url"


def test_release_versions_and_reports_are_bumped():
    g = _load_generate()
    import tct_engine.observability as observability

    assert g.CATEGORY_GENERATION_PROMPT_VERSION == (
        "v1.11.8.8-universal-lead-claim-integrity"
    )
    assert g.CATEGORY_GENERATION_REPORT_SCHEMA_VERSION == 6
    assert g.FORWARD_IDENTITY_VERSION == "1.7"
    version = tuple(int(part) for part in observability.ENGINE_VERSION.split("."))
    assert version >= (1, 11, 8, 8)
    assert observability.OBSERVABILITY_SCHEMA_VERSION >= 17
