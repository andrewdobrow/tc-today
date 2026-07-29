import os
import sys
import types
from copy import deepcopy


if "feedparser" not in sys.modules:
    feedparser = types.ModuleType("feedparser")
    feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
    sys.modules["feedparser"] = feedparser

if "anthropic" not in sys.modules:
    anthropic = types.ModuleType("anthropic")

    class _Anthropic:
        def __init__(self, *args, **kwargs):
            self.messages = types.SimpleNamespace(
                create=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline test"))
            )

    anthropic.Anthropic = _Anthropic
    sys.modules["anthropic"] = anthropic

os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")

from scripts import generate


def _item(headline, body="", **updates):
    item = {
        "title": headline,
        "headline": headline,
        "source_title": headline,
        "summary": body,
        "article_text": body,
        "body": body,
        "source_quality": "full",
        "source_word_count": 180,
        "feed_url": "https://www.wptv.com/news/local-news.rss",
        "link": "https://publisher.example/story",
    }
    item.update(updates)
    return item


def test_shared_contract_registry_enforces_only_local_government_increment():
    assert generate.CATEGORY_ELIGIBILITY_CONTRACTS["local_gov"]["mode"] == "enforce"
    for key in {"crime", "business", "sports", "things_to_do", "florida"}:
        assert generate.CATEGORY_ELIGIBILITY_CONTRACTS[key]["mode"] == "observe_only"
    for key in {"martin", "st_lucie", "indian_river"}:
        assert generate.CATEGORY_ELIGIBILITY_CONTRACTS[key]["mode"] == "existing_geographic_enforce"


def test_exact_port_st_lucie_police_chase_is_not_local_government():
    item = _item(
        "2 men flee Port St. Lucie police at 80 mph, one found hiding on roof of occupied home",
        "Police pursued the suspects after a traffic stop. One man was arrested after hiding on a roof.",
    )
    assessment = generate._category_eligibility_contract_assessment("local_gov", item)
    assert assessment["eligible"] is False
    assert assessment["reason"] == "competing_story_form_without_government_action"
    assert any(signal.startswith("crime_incident:") for signal in assessment["competing_signals"])
    assert generate._hero_eligible("local_gov", item) is False


def test_exact_vero_beach_charity_cyclist_is_not_local_government():
    item = _item(
        "Boston cyclist passes through Vero Beach on 2,600-mile ride honoring friend lost",
        "The cyclist stopped in Indian River County during a fundraising ride honoring a friend.",
    )
    assessment = generate._category_eligibility_contract_assessment("local_gov", item)
    assert assessment["eligible"] is False
    assert assessment["reason"] == "competing_story_form_without_government_action"
    assert any(signal.startswith("community_feature:") for signal in assessment["competing_signals"])
    assert generate._hero_eligible("local_gov", item) is False


def test_local_government_contract_accepts_real_government_decisions_and_programs():
    examples = [
        _item(
            "St. Lucie County commissioners deadlock on infrastructure sales tax referendum timing",
            "The county commission voted on when to place the sales tax referendum on the ballot.",
        ),
        _item(
            "Indiantown Council rejects second attempt to pause data center applications",
            "The Village Council rejected a proposed moratorium after a public meeting.",
        ),
        _item(
            "Martin County School District cuts 16 administrative positions",
            "The school district cut positions to reduce its administrative budget.",
        ),
        _item(
            "Port St. Lucie opens registration for free City University program",
            "The City of Port St. Lucie opens registration for its resident education program.",
        ),
    ]
    for item in examples:
        assessment = generate._category_eligibility_contract_assessment("local_gov", item)
        assert assessment["eligible"] is True, item["headline"]
        assert assessment["positive_signals"], item["headline"]
        assert generate._hero_eligible("local_gov", item) is True, item["headline"]


def test_classifier_label_cannot_bypass_enforced_local_government_contract():
    item = _item(
        "2 men flee Port St. Lucie police at 80 mph, one found hiding on roof",
        "Police arrested one suspect after a pursuit and traffic stop.",
    )
    previous = generate.STORY_CLASSIFICATION
    try:
        generate.STORY_CLASSIFICATION = {item["title"].lower(): {"local_gov"}}
        assert generate._hero_eligible("local_gov", item) is False
    finally:
        generate.STORY_CLASSIFICATION = previous


def test_source_filter_removes_contract_failures_before_article_generation():
    bad = _item(
        "Boston cyclist passes through Vero Beach on 2,600-mile ride honoring friend lost",
        "The cyclist stopped in Indian River County during a fundraising ride.",
        link="https://publisher.example/cyclist",
    )
    good = _item(
        "St. Lucie County commissioners deadlock on infrastructure sales tax referendum timing",
        "The county commission voted on the sales tax referendum.",
        link="https://publisher.example/commission",
    )
    previous = generate.STORY_CLASSIFICATION
    try:
        generate.STORY_CLASSIFICATION = {
            bad["title"].lower(): {"local_gov"},
            good["title"].lower(): {"local_gov"},
        }
        selected = generate.filter_category_headlines(
            "local_gov", [deepcopy(bad), deepcopy(good)], target=12, min_keep=6
        )
    finally:
        generate.STORY_CLASSIFICATION = previous
    assert [row["title"] for row in selected] == [good["title"]]
    assert selected[0]["_category_eligibility_contract"]["eligible"] is True


def test_archive_style_local_government_backfill_is_revalidated():
    archive_candidate = {
        "headline": "Boston cyclist passes through Vero Beach on 2,600-mile ride honoring friend lost",
        "title": "Boston cyclist passes through Vero Beach on 2,600-mile ride honoring friend lost",
        "teaser": "A cyclist stopped in Vero Beach during a fundraising ride.",
        "summary": "A cyclist stopped in Vero Beach during a fundraising ride.",
        "body": "A cyclist stopped in Vero Beach during a fundraising ride.",
        "source_quality": "full",
    }
    assert generate._hero_eligible("local_gov", archive_candidate) is False


def test_custom_article_declared_for_local_government_remains_authoritative():
    custom = _item(
        "Community profile with manually assigned category",
        "A custom TCT article whose category was selected by the editor.",
        is_custom=True,
        authoritative_custom=True,
    )
    assessment = generate._category_eligibility_contract_assessment("local_gov", custom)
    assert assessment["eligible"] is True
    assert assessment["reason"] == "custom_authority_exempt"


def test_contract_cache_invalidation_is_scoped_to_local_government(monkeypatch):
    source = _item(
        "St. Lucie County commissioners approve budget",
        "The county commission approved the county budget.",
    )
    original = generate.CATEGORY_ELIGIBILITY_CONTRACT_VERSION
    local_before = generate._category_generation_cache_key("local_gov", [source])
    sports_before = generate._category_generation_cache_key("sports", [source])
    monkeypatch.setattr(generate, "CATEGORY_ELIGIBILITY_CONTRACT_VERSION", original + "-changed")
    local_after = generate._category_generation_cache_key("local_gov", [source])
    sports_after = generate._category_generation_cache_key("sports", [source])
    assert local_before != local_after
    assert sports_before == sports_after


def test_category_eligibility_report_explains_incremental_rollout():
    report = generate._build_category_eligibility_report([
        {
            "category_key": "local_gov",
            "category_label": "Local Government",
            "category_eligibility_assessed_count": 2,
            "category_eligibility_rejections": [
                {
                    "headline": "Police chase",
                    "eligible": False,
                    "reason": "competing_story_form_without_government_action",
                }
            ],
        },
        {
            "category_key": "sports",
            "category_label": "Sports",
            "category_eligibility_assessed_count": 0,
            "category_eligibility_rejections": [],
        },
    ])
    assert report["schema_version"] == 1
    assert report["contract_version"] == generate.CATEGORY_ELIGIBILITY_CONTRACT_VERSION
    assert report["summary"]["rejected_count"] == 1
    assert report["summary"]["enforced_categories"] == ["local_gov"]
    assert "sports" in report["summary"]["observe_only_categories"]


def test_category_generation_report_counts_contract_rejections():
    report = generate._build_category_generation_report([
        {
            "status": "generated_live",
            "attempt_count": 1,
            "model_elapsed_seconds": 5,
            "archive_recovery_requested": False,
            "category_eligibility_rejection_count": 2,
        }
    ])
    assert report["schema_version"] == 5
    assert report["summary"]["category_eligibility_rejection_count"] == 2
