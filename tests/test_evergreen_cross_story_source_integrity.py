"""Regression: 2026-11-24 Evergreen Club source chrome injected October stabbing.

The original run at 2026-11-24T13:43:26Z logged
"SOURCE FACT GUARD: repaired missing named-suspect fact in article draft".
Source-derived incident identity from the original run contained 'Bradley Martin',
'El Rio Trail', and unrelated violent-crime tokens, in a burglary story.
"""
from tct_engine.critical_source_facts import (
    conflicting_named_crime_claim,
    named_suspect_facts,
    unrelated_named_crime_facts,
)

SOURCE_TITLE = (
    "4 men arrested after overnight burglary at Martin County’s Evergreen Club - WPEC"
)
CONTAMINANT = (
    "MCSO also said Bradley Martin, 32, was charged with attempted murder "
    "after allegedly slashing an acquaintance in the neck with a box cutter."
)
CLEAN_BODY = (
    "Four men from Jacksonville are in custody after an overnight burglary "
    "at the Evergreen Club in Palm City, Martin County deputies said Tuesday. "
    "Residents were asked to inspect their homes and vehicles for missing items. "
    "The sheriff's office said it tracked down the four men, who were wearing "
    "masks and gloves, and took them into custody. "
    "Anyone in Palm City who finds property missing from a home or vehicle "
    "should call the sheriff's office at 772-220-7060. "
    "Investigators said the men traveled to the area from Jacksonville."
)
SHORT_SINCLAIR_SOURCE = (
    "Now 81 ° Watch News. 4 men arrested after overnight burglary at Martin "
    "County's Evergreen Club by CBS12 News. Share story Share topics: "
    "Palm City Martin County Burglary Evergreen Club Sheriff Arrested "
    "PALM CITY, Fla. (CBS12) — " + CLEAN_BODY + " " + CONTAMINANT
    + " NEWS IN PHOTOS: See more local news. "
    "Boca Raton El Rio Trail and other unrelated headlines. "
    "Sign up for breaking news and alerts. Read more about sports and weather."
)


def test_actual_nov24_short_sinclair_extract_filters_unrelated_criminal_case():
    from scripts import generate

    assert 80 <= len(SHORT_SINCLAIR_SOURCE.split()) < 220
    row = {"title": SOURCE_TITLE, "source_url": "https://cbs12.com/news/local/evergreen-club"}
    clean = generate._focus_extracted_source_text(SHORT_SINCLAIR_SOURCE, row)
    assert clean != SHORT_SINCLAIR_SOURCE
    assert "Evergreen Club" in clean
    assert "Jacksonville" in clean
    assert "772-220-7060" in clean
    assert "Bradley Martin" not in clean
    assert "attempted murder" not in clean
    assert "El Rio Trail" not in clean


def test_crime_claim_must_match_assigned_event_even_when_name_looks_like_county():
    assert conflicting_named_crime_claim(SOURCE_TITLE, CONTAMINANT)
    assert not named_suspect_facts(SHORT_SINCLAIR_SOURCE, source_title=SOURCE_TITLE)
    assert [f.name for f in unrelated_named_crime_facts(SOURCE_TITLE, CONTAMINANT)] == [
        "Bradley Martin"
    ]


def test_genuine_named_criminal_charge_not_discarded_when_title_matches():
    title = "Bradley Martin charged with attempted murder after stabbing on SE Indian Street"
    assert not conflicting_named_crime_claim(title, CONTAMINANT)
    assert [f.name for f in named_suspect_facts(CONTAMINANT, source_title=title)] == [
        "Bradley Martin"
    ]


def test_story_mentioning_both_crime_families_not_automatically_discarded():
    title = "Burglary and attempted murder investigations continue in Martin County"
    assert not conflicting_named_crime_claim(title, CONTAMINANT)


def test_assignment_editor_cannot_make_cross_story_name_a_mandatory_fact():
    from scripts import generate
    row = {"title": SOURCE_TITLE, "article_text": SHORT_SINCLAIR_SOURCE,
           "summary": "Four men detained after burglary", "source_quality": "full",
           "source_type": "full_source", "source_url": "https://cbs12.com/news/local/evergreen-club"}
    packet = generate._build_assignment_editor_packet(
        category_key="crime", category_label="Crime & Safety", headlines=[row]
    )
    assert not packet["source_inputs"][0]["_critical_named_suspects"]


def test_final_publication_gate_blocks_cross_story_named_crime_allegation():
    from scripts import generate
    row = {
        "headline": "Four arrested in Evergreen Club burglary",
        "source_headline": SOURCE_TITLE,
        "source_type": "full_source",
        "source_quality": "full",
        "article_text": CLEAN_BODY,
        "body": CLEAN_BODY + "\n\n" + CONTAMINANT,
    }
    assert not generate._publishable_article(row, hero=True)


def test_alternate_extractor_cannot_reintroduce_different_incident_charge():
    from tct_engine.critical_source_facts import reconcile_same_article_extraction
    primary = CLEAN_BODY
    alternate = CLEAN_BODY + " " + CONTAMINANT
    assert reconcile_same_article_extraction(
        primary, alternate, source_title=SOURCE_TITLE
    ) == CLEAN_BODY


def test_alternate_extractor_still_adds_real_named_suspect_from_same_case():
    from tct_engine.critical_source_facts import reconcile_same_article_extraction
    primary = "The police continue to investigate an attempted murder stabbing."
    alternate = (
        "Police said they arrested Bradley Martin after the stabbing. "
        "Bradley Martin, 32, was charged with attempted murder."
    )
    result = reconcile_same_article_extraction(
        primary, alternate, source_title="Bradley Martin charged after stabbing"
    )
    assert "Bradley Martin" in result
