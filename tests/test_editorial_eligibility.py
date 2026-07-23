from tct_engine import EditorialEligibilityEngine, EligibilityStatus


def test_realtor_listing_is_rejected_before_registry():
    engine = EditorialEligibilityEngine()
    decision = engine.evaluate({
        "title": "1934 Westminster Cir Unit 9-5, Vero Beach, FL 32966",
        "link": "https://www.realtor.com/realestateandhomes-detail/example",
    }, source="Realtor.com")
    assert decision.eligible is False
    assert decision.status is EligibilityStatus.LISTING
    assert decision.source_profile.trust == 0


def test_local_news_is_publishable():
    engine = EditorialEligibilityEngine()
    decision = engine.evaluate({
        "title": "Martin County approves new budget",
        "link": "https://www.wptv.com/news/treasure-coast/martin-county/example",
    }, source="WPTV")
    assert decision.eligible is True
    assert decision.status is EligibilityStatus.PUBLISHABLE
    assert decision.source_profile.source_class == "local_news"


def test_aggregator_is_low_value_but_observable():
    engine = EditorialEligibilityEngine()
    decision = engine.evaluate({
        "title": "Officials announce road closure",
        "link": "https://www.aol.com/news/example.html",
    }, source="AOL")
    assert decision.eligible is True
    assert decision.status is EligibilityStatus.LOW_VALUE
