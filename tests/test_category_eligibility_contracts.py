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


def test_shared_contract_registry_enforces_local_government_and_business():
    assert generate.CATEGORY_ELIGIBILITY_CONTRACTS["local_gov"]["mode"] == "enforce"
    assert generate.CATEGORY_ELIGIBILITY_CONTRACTS["business"]["mode"] == "enforce"
    assert generate.CATEGORY_ELIGIBILITY_CONTRACTS["crime"]["mode"] == "enforce"
    assert generate.CATEGORY_ELIGIBILITY_CONTRACTS["things_to_do"]["mode"] == "enforce"
    for key in {"sports", "florida"}:
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
    assert report["summary"]["enforced_categories"] == ["business", "crime", "local_gov", "things_to_do"]
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
    assert report["schema_version"] == 7
    assert report["summary"]["category_eligibility_rejection_count"] == 2


def test_business_contract_rejects_exact_recent_production_bleed():
    fixtures = [
        _item(
            "Palm Beach County cities push for more trees and shade as extreme heat bakes neighborhoods",
            "Palm Beach County cities are considering tree canopy and shade policies as extreme heat grows.",
            source_title="Extreme heat is fueling a countywide push for more trees and shade in Palm Beach County",
            link="https://www.wptv.com/news/palm-beach-county/extreme-heat-trees-shade",
        ),
        _item(
            "South Florida communities weigh data center moratoriums as residents report constant noise from cooling fans",
            "Residents in Palm Beach County reported cooling-fan noise near a data center while officials considered a moratorium.",
            source_title="Data center noise complaints grow in Palm Beach County",
            link="https://www.wptv.com/news/palm-beach-county/data-center-noise",
        ),
        _item(
            "Early voting begins Saturday across Martin, St. Lucie, Indian River counties for August primary",
            "Early voting begins across Martin County, St. Lucie County and Indian River County ahead of the primary election.",
            link="https://publisher.example/treasure-coast/early-voting",
        ),
        _item(
            "Martin County neighbors report dogs suffering next door as sheriff says legal barriers prevent investigation",
            "Martin County neighbors said dogs are suffering. The sheriff investigation faces legal barriers and animal welfare concerns.",
            link="https://publisher.example/martin-county/dogs",
        ),
    ]
    reasons = []
    for item in fixtures:
        assessment = generate._category_eligibility_contract_assessment("business", item)
        assert assessment["eligible"] is False, item["headline"]
        assert assessment["would_reject"] is True
        reasons.append(assessment["reason"])
        assert generate._hero_eligible("business", item) is False
    assert "missing_treasure_coast_business_nexus" in reasons
    assert "competing_story_form_without_business_development_focus" in reasons


def test_business_contract_accepts_openings_development_jobs_and_transactions():
    fixtures = [
        _item(
            "King's Landing development in Fort Pierce advances with Marriott Hotel project",
            "Developers said the Fort Pierce mixed-use development and hotel project are under construction.",
            link="https://publisher.example/fort-pierce/kings-landing",
        ),
        _item(
            "Port St. Lucie manufacturer expands and adds 120 jobs",
            "A Port St. Lucie employer announced an expansion, hiring and job creation.",
            link="https://publisher.example/port-st-lucie/employer-expansion",
        ),
        _item(
            "New restaurant opens in Vero Beach shopping center",
            "The Vero Beach restaurant opens in a retail center with a new location.",
            link="https://publisher.example/vero-beach/restaurant-opening",
        ),
        _item(
            "Martin County commercial property sold to local developer",
            "A Martin County developer purchases the commercial property for redevelopment.",
            link="https://publisher.example/martin-county/property-sale",
        ),
    ]
    for item in fixtures:
        assessment = generate._category_eligibility_contract_assessment("business", item)
        assert assessment["eligible"] is True, (item["headline"], assessment)
        assert assessment["positive_signals"]
        assert assessment["local_nexus_signals"]
        assert generate._hero_eligible("business", item) is True, item["headline"]


def test_business_source_filter_rejects_before_model_generation():
    bad = _item(
        "Early voting begins across Martin, St. Lucie and Indian River counties",
        "The primary election early voting period begins across the Treasure Coast.",
        link="https://publisher.example/treasure-coast/early-voting",
    )
    good = _item(
        "Fort Pierce mixed-use development breaks ground",
        "Developers broke ground on a Fort Pierce mixed-use development project.",
        link="https://publisher.example/fort-pierce/development",
    )
    previous = generate.STORY_CLASSIFICATION
    try:
        generate.STORY_CLASSIFICATION = {
            bad["title"].lower(): {"business"},
            good["title"].lower(): {"business"},
        }
        selected = generate.filter_category_headlines(
            "business", [deepcopy(bad), deepcopy(good)], target=12, min_keep=6
        )
    finally:
        generate.STORY_CLASSIFICATION = previous
    assert [row["title"] for row in selected] == [good["title"]]


def test_archive_style_business_candidate_is_revalidated():
    bad = {
        "headline": "Martin County neighbors report dogs suffering next door as sheriff investigates",
        "teaser": "Animal welfare concerns prompted calls to the Martin County sheriff.",
        "body": "Neighbors described dogs suffering and asked for an animal cruelty investigation.",
        "source_headline": "Neighbors report dogs suffering in Martin County",
        "source_url": "https://publisher.example/martin-county/dogs",
        "article_text": "Martin County neighbors reported dogs suffering and contacted the sheriff.",
        "source_quality": "archive",
    }
    assessment = generate._category_eligibility_contract_assessment("business", bad)
    assert assessment["eligible"] is False
    assert assessment["reason"] == "competing_story_form_without_business_development_focus"


def test_custom_business_category_remains_authoritative():
    custom = _item(
        "Editor's business profile",
        "A custom TCT business article assigned by the editor.",
        is_custom=True,
        authoritative_custom=True,
    )
    assessment = generate._category_eligibility_contract_assessment("business", custom)
    assert assessment["eligible"] is True
    assert assessment["reason"] == "custom_authority_exempt"
    assert assessment["contract_version"] == generate.BUSINESS_ELIGIBILITY_CONTRACT_VERSION


def test_business_contract_version_invalidates_only_business_cache(monkeypatch):
    source = _item(
        "Fort Pierce development breaks ground",
        "A Fort Pierce developer broke ground on a commercial project.",
    )
    business_before = generate._category_generation_cache_key("business", [source])
    sports_before = generate._category_generation_cache_key("sports", [source])
    monkeypatch.setattr(
        generate,
        "BUSINESS_ELIGIBILITY_CONTRACT_VERSION",
        generate.BUSINESS_ELIGIBILITY_CONTRACT_VERSION + "-changed",
    )
    business_after = generate._category_generation_cache_key("business", [source])
    sports_after = generate._category_generation_cache_key("sports", [source])
    assert business_before != business_after
    assert sports_before == sports_after


def test_crime_contract_rejects_school_achievement_and_bus_admin_bleed():
    fixtures = [
        _item(
            "Four Indian River County elementary schools reach 90% reading proficiency milestone",
            "Four elementary schools reached a reading proficiency goal through a literacy program.",
        ),
        _item(
            "Indian River County Superintendent highlights new bus routing system on first day of school",
            "The superintendent highlighted a new routing system and parent bus tracking app.",
        ),
    ]
    for item in fixtures:
        assessment = generate._category_eligibility_contract_assessment("crime", item)
        assert assessment["eligible"] is False, item["headline"]
        assert assessment["reason"] == "missing_primary_crime_safety_focus"
        assert generate._hero_eligible("crime", item) is False


def test_crime_contract_keeps_real_public_safety_school_story():
    item = _item(
        "Indian River County schools add metal detectors, crisis alert badges as students return",
        "Schools added metal detectors and crisis alert badges as part of an active shooter safety program.",
    )
    assessment = generate._category_eligibility_contract_assessment("crime", item)
    assert assessment["eligible"] is True
    assert assessment["positive_signals"]


def test_crime_contract_version_invalidates_only_crime_cache(monkeypatch):
    source = _item(
        "Fort Pierce police arrest man after robbery",
        "Police arrested a suspect after a robbery in Fort Pierce.",
    )
    crime_before = generate._category_generation_cache_key("crime", [source])
    sports_before = generate._category_generation_cache_key("sports", [source])
    monkeypatch.setattr(
        generate,
        "CRIME_ELIGIBILITY_CONTRACT_VERSION",
        generate.CRIME_ELIGIBILITY_CONTRACT_VERSION + "-changed",
    )
    crime_after = generate._category_generation_cache_key("crime", [source])
    sports_after = generate._category_generation_cache_key("sports", [source])
    assert crime_before != crime_after
    assert sports_before == sports_after


def test_things_to_do_rejects_exact_martin_hoarding_recovery_story_even_if_classifier_is_wrong():
    item = _item(
        "Over 100 animals from Martin County hoarding cases begin recovery at Palm City shelter",
        "The Humane Society of the Treasure Coast is caring for rescued animals from a Palm City hoarding case. "
        "Paige O'Donnell faces 72 charges. Shelter staff said the dogs are healing and adoption applications begin Sept. 1.",
        feed_url="https://www.wptv.com/news/region-martin-county.rss",
    )
    assessment = generate._category_eligibility_contract_assessment("things_to_do", item)
    assert assessment["eligible"] is False
    assert assessment["reason"] in {
        "missing_attendable_activity_focus",
        "competing_story_form_without_attendable_activity_focus",
    }

    previous = generate.STORY_CLASSIFICATION
    try:
        generate.STORY_CLASSIFICATION = {item["title"].lower(): {"things_to_do", "martin"}}
        selected = generate.filter_category_headlines(
            "things_to_do", [deepcopy(item)], target=12, min_keep=6
        )
    finally:
        generate.STORY_CLASSIFICATION = previous
    assert selected == []


def test_things_to_do_hard_rejects_out_of_area_palm_beach_events_even_if_classified():
    outside = _item(
        "Palm Beach Food & Wine Festival unveils 2026 events and celebrity chefs",
        "The Palm Beach Food & Wine Festival will run across Palm Beach County with tickets and tasting events.",
        feed_url="https://www.wptv.com/news/local-news.rss",
    )
    previous = generate.STORY_CLASSIFICATION
    try:
        generate.STORY_CLASSIFICATION = {outside["title"].lower(): {"things_to_do"}}
        selected = generate.filter_category_headlines(
            "things_to_do", [deepcopy(outside)], target=12, min_keep=6
        )
    finally:
        generate.STORY_CLASSIFICATION = previous
    assert selected == []


def test_things_to_do_accepts_local_attendable_event():
    event = _item(
        "Fort Pierce brewery hosts Sunday food festival and live music",
        "A Fort Pierce brewery will host a food festival with live music Sunday. Tickets are available for the community event.",
        feed_url="https://www.wptv.com/news/region-st-lucie-county.rss",
    )
    assessment = generate._category_eligibility_contract_assessment("things_to_do", event)
    assert assessment["eligible"] is True
    assert assessment["reason"] == "local_attendable_activity_confirmed"

    previous = generate.STORY_CLASSIFICATION
    try:
        generate.STORY_CLASSIFICATION = {event["title"].lower(): {"things_to_do", "st_lucie"}}
        selected = generate.filter_category_headlines(
            "things_to_do", [deepcopy(event)], target=12, min_keep=6
        )
    finally:
        generate.STORY_CLASSIFICATION = previous
    assert [row["title"] for row in selected] == [event["title"]]
    assert selected[0]["hero_eligible"] == "yes"


def test_topic_routing_blocks_unclassified_story_instead_of_keyword_fallback():
    event = _item(
        "Fort Pierce weekend festival brings live music downtown",
        "The Fort Pierce event includes a festival, live music and family activities downtown.",
        feed_url="https://www.wptv.com/news/region-st-lucie-county.rss",
    )
    previous = generate.STORY_CLASSIFICATION
    try:
        generate.STORY_CLASSIFICATION = {}
        selected = generate.filter_category_headlines(
            "things_to_do", [deepcopy(event)], target=12, min_keep=6
        )
    finally:
        generate.STORY_CLASSIFICATION = previous
    assert selected == []


def test_things_to_do_contract_version_invalidates_only_things_to_do_cache(monkeypatch):
    source = _item(
        "Fort Pierce festival returns downtown",
        "A Fort Pierce festival returns with live music and tickets.",
    )
    things_before = generate._category_generation_cache_key("things_to_do", [source])
    crime_before = generate._category_generation_cache_key("crime", [source])
    monkeypatch.setattr(
        generate,
        "THINGS_TO_DO_ELIGIBILITY_CONTRACT_VERSION",
        generate.THINGS_TO_DO_ELIGIBILITY_CONTRACT_VERSION + "-changed",
    )
    things_after = generate._category_generation_cache_key("things_to_do", [source])
    crime_after = generate._category_generation_cache_key("crime", [source])
    assert things_before != things_after
    assert crime_before == crime_after


def test_exact_aug22_things_to_do_contaminated_pool_is_empty_before_generation():
    rows = [
        _item(
            "Palm Beach Food & Wine Festival unveils 2026 events, celebrity chefs and ticket sales",
            "The Palm Beach Food & Wine Festival will feature ticketed tasting events across Palm Beach County.",
            feed_url="https://www.wptv.com/news/local-news.rss",
        ),
        _item(
            "Morikami Museum and Japanese Gardens in Delray Beach to celebrate Obon Weekend",
            "The Delray Beach museum will host performances and activities during Obon Weekend.",
            feed_url="https://www.wptv.com/news/local-news.rss",
        ),
        _item(
            "Loggerhead Triathlon celebrates 40 years at Carlin Park in Jupiter",
            "The Jupiter triathlon at Carlin Park includes registration for several race formats.",
            feed_url="https://www.wptv.com/news/local-news.rss",
        ),
        _item(
            "70 truckloads of dirt brought to Amerant Bank Arena ahead of Monster Jam this weekend",
            "Monster Jam will take place at Amerant Bank Arena in Sunrise this weekend.",
            feed_url="https://www.wptv.com/news/local-news.rss",
        ),
        _item(
            "Palm Beach County homeowner surprised with fully furnished Habitat for Humanity home",
            "A Palm Beach County homeowner received a furnished Habitat for Humanity home.",
            feed_url="https://www.wptv.com/news/local-news.rss",
        ),
        _item(
            "Vote daily for Palm Beach Gardens nonprofit in NASCAR Foundation's $100K award contest",
            "A Palm Beach Gardens nonprofit founder is a finalist for a national award contest.",
            feed_url="https://www.wptv.com/news/local-news.rss",
        ),
        _item(
            "Animals rescued from Martin County hoarding cases start to show signs of healing",
            "More than 100 rescued animals from Stuart and Palm City hoarding investigations are recovering. "
            "One defendant faces animal cruelty charges and shelter staff described medical grooming and adoption applications.",
            feed_url="https://www.wptv.com/news/region-martin-county.rss",
        ),
    ]
    previous = generate.STORY_CLASSIFICATION
    try:
        # Deliberately simulate the worst case: stale/bad classifications label every
        # row Things To Do. Deterministic locality + beat contracts must still win.
        generate.STORY_CLASSIFICATION = {
            row["title"].lower(): {"things_to_do"} for row in rows
        }
        selected = generate.filter_category_headlines(
            "things_to_do", deepcopy(rows), target=12, min_keep=6
        )
    finally:
        generate.STORY_CLASSIFICATION = previous

    assert selected == []
    assert generate._things_to_do_zero_candidate_fast_recovery("things_to_do", selected) is True


def test_outside_area_crime_cannot_enter_local_crime_section_even_if_classifier_is_wrong():
    outside = _item(
        "Man arrested after shooting in Delray Beach",
        "Delray Beach police arrested a suspect after a shooting in Palm Beach County.",
        feed_url="https://www.wptv.com/news/local-news.rss",
    )
    previous = generate.STORY_CLASSIFICATION
    try:
        generate.STORY_CLASSIFICATION = {outside["title"].lower(): {"crime"}}
        selected = generate.filter_category_headlines(
            "crime", [deepcopy(outside)], target=12, min_keep=6
        )
    finally:
        generate.STORY_CLASSIFICATION = previous
    assert selected == []
