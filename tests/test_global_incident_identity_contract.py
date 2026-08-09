from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tct_engine.incident_identity import build_incident_signature, incident_anchor_key
from tct_engine.registry_repair import repair_registry_payload


LANG_HEADLINES = [
    "Indian River County government mourns firefighter who dedicated career to serving residents",
    "Indian River County Fire Rescue mourns death of firefighter Geoffrey Lang who dedicated his life to service",
    "Indian River County firefighter Geoffrey Lang dies following personal tragedy at Sebastian home",
    "Indian River County firefighter and paramedic died by suicide in Sebastian home",
    "Sebastian Police Department mourns death of Indian River County firefighter",
    "Vero Beach Police Department honors service of Indian River County firefighter",
]
LANG_TEASERS = [
    "County leaders joined Fire Rescue in mourning Firefighter/Paramedic Geoffrey Lang.",
    "Fire Rescue announced the death of firefighter Geoffrey Lang.",
    "Firefighter and paramedic Geoffrey Lang died following a personal tragedy.",
    "Firefighter/Paramedic Geoffrey Lang died by suicide at his Sebastian home.",
    "Sebastian police mourned the death of firefighter Geoffrey Lang.",
    "Police honored the life and service of firefighter Geoffrey Lang.",
]
LANG_SLUGS = [
    "2026-07-28-indian-river-county-government-mourns-firefighter-who-dedicated-career-to-servin",
    "2026-07-28-indian-river-county-fire-rescue-mourns-death-of-firefighter-geoffrey-lang-who-di",
    "2026-07-28-indian-river-county-firefighter-geoffrey-lang-dies-following-personal-tragedy-at",
    "2026-07-29-indian-river-county-firefighter-and-paramedic-died-by-suicide-in-sebastian-home",
    "2026-07-28-sebastian-police-department-mourns-death-of-indian-river-county-firefighter",
    "2026-07-28-vero-beach-police-department-honors-service-of-indian-river-county-firefighter",
]
ANCHOR = "named-person-death:geoffrey-lang"


def _load_generate(tmp_path=None):
    if "feedparser" not in sys.modules:
        feedparser = types.ModuleType("feedparser")
        feedparser.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules["feedparser"] = feedparser
    if "anthropic" not in sys.modules:
        anthropic = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *args, **kwargs):
                self.messages = types.SimpleNamespace(create=lambda *args, **kwargs: None)

        anthropic.Anthropic = _Anthropic
        sys.modules["anthropic"] = anthropic
    os.environ.setdefault("ANTHROPIC_API_KEY", "offline-test-key")
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_global_incident", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if tmp_path is not None:
        module.OUTPUT_DIR = Path(tmp_path)
    return module


def _rows():
    return [
        {
            "slug": slug,
            "headline": headline,
            "teaser": teaser,
            "date": "2026-07-28" if "2026-07-28" in slug else "2026-07-29",
            "category_key": "indian_river",
            "category_keys": ["indian_river", "crime"],
            "editorial_story_id": f"story_{index:06d}",
            "article_word_count": 300 + index,
        }
        for index, (slug, headline, teaser) in enumerate(
            zip(LANG_SLUGS, LANG_HEADLINES, LANG_TEASERS), start=500
        )
    ]


def _write_archive_and_redirects(root: Path, archive, redirects):
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "articles").mkdir(parents=True, exist_ok=True)
    (root / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    (root / "data" / "canonical-redirects.json").write_text(
        json.dumps({"redirects": redirects}), encoding="utf-8"
    )


def test_all_geoffrey_lang_framings_share_one_generic_anchor():
    keys = {
        incident_anchor_key(titles=(headline, teaser))
        for headline, teaser in zip(LANG_HEADLINES, LANG_TEASERS)
    }
    assert keys == {ANCHOR}


def test_named_person_death_anchor_rejects_unrelated_fire_and_shots_stories():
    assert incident_anchor_key(
        titles=("Shots fired at Orchard Grove apartments in Indian River County",)
    ) == ""
    assert incident_anchor_key(
        titles=("Cat and hamster rescued after Palm Beach County house fire",)
    ) == ""
    assert incident_anchor_key(
        titles=("Conner Ware named Florida State League Pitcher of the Week",)
    ) == ""


def test_named_person_death_anchor_requires_title_level_death_context():
    unrelated_body = (
        "More stories: Patricia Brennan died in Fort Myers. Officials later held a memorial."
    )
    title = "Port St. Lucie man arrested after video shows him allegedly abusing small dog"

    assert incident_anchor_key(
        titles=(title,),
        body=unrelated_body,
        entities=("Patricia Brennan",),
    ) == ""

    signature = build_incident_signature(
        titles=(title,),
        body=unrelated_body,
        entities=("Patricia Brennan",),
    )
    assert signature.family != "named_person_death"


def test_quoted_official_does_not_displace_named_death_subject():
    body = (
        "The county joined Fire Rescue in mourning Firefighter/Paramedic Geoffrey Lang. "
        "County spokeswoman Kathy Copeland said Lang dedicated his career to residents. "
        "County Administrator John Smith said the county supports first responders."
    )
    assert incident_anchor_key(
        titles=(LANG_HEADLINES[0],), body=body
    ) == ANCHOR


def test_registry_repair_moves_only_lang_entries_out_of_contaminated_stories():
    payload = {
        "stories": {
            "story_000549": {
                "story_id": "story_000549",
                "canonical_title": LANG_HEADLINES[2],
                "titles": [LANG_HEADLINES[2], "Shots fired at Orchard Grove apartments"],
                "events": ["death-geoffrey-lang", "shots-orchard-grove"],
                "timeline": [
                    {"article_id": "lang-a", "event_key": "death-geoffrey-lang", "title": LANG_HEADLINES[2]},
                    {"article_id": "shots-a", "event_key": "shots-orchard-grove", "title": "Shots fired at Orchard Grove apartments"},
                ],
            },
            "story_000721": {
                "story_id": "story_000721",
                "canonical_title": LANG_HEADLINES[1],
                "titles": [LANG_HEADLINES[1]],
                "events": ["lang-mourning"],
                "timeline": [
                    {"article_id": "lang-b", "event_key": "lang-mourning", "title": LANG_HEADLINES[1]},
                ],
            },
            "story_000793": {
                "story_id": "story_000793",
                "canonical_title": LANG_HEADLINES[4],
                "titles": [LANG_HEADLINES[4], "Cat and hamster rescued after house fire"],
                "events": ["lang-police", "cat-house-fire"],
                "title_candidates": [{"title": "Sebastian police mourn firefighter Geoffrey Lang"}],
                "timeline": [
                    {"article_id": "lang-c", "event_key": "lang-police", "title": LANG_HEADLINES[4]},
                    {"article_id": "cat-a", "event_key": "cat-house-fire", "title": "Cat and hamster rescued after house fire"},
                ],
            },
        },
        "story_aliases": {},
    }

    report = repair_registry_payload(payload)

    canonical_id = payload["incident_anchor_to_story"][ANCHOR]
    canonical = payload["stories"][canonical_id]
    canonical_titles = {entry["title"] for entry in canonical["timeline"]}
    assert LANG_HEADLINES[1] in canonical_titles
    assert LANG_HEADLINES[2] in canonical_titles
    assert LANG_HEADLINES[4] in canonical_titles
    remaining_titles = {
        entry["title"]
        for story in payload["stories"].values()
        for entry in story.get("timeline", [])
    }
    assert "Shots fired at Orchard Grove apartments" in remaining_titles
    assert "Cat and hamster rescued after house fire" in remaining_titles
    assert "Shots fired at Orchard Grove apartments" not in canonical_titles
    assert "Cat and hamster rescued after house fire" not in canonical_titles
    assert report.selective_incident_anchor_groups_repaired == 1
    assert report.contaminated_story_records_preserved >= 2


def test_publication_coalescing_uses_incident_anchor_before_fragmented_story_ids(tmp_path):
    g = _load_generate(tmp_path)
    left, right = _rows()[:2]
    assert left["editorial_story_id"] != right["editorial_story_id"]
    assert g._publication_coalesce_key(left) == f"incident-anchor:{ANCHOR}"
    assert g._publication_coalesce_key(right) == f"incident-anchor:{ANCHOR}"


def test_archive_cleanup_collapses_all_lang_urls_despite_six_story_ids(tmp_path):
    g = _load_generate(tmp_path)
    rows = _rows()
    cleaned, redirects = g.apply_canonical_story_cleanup(
        rows, tmp_path / "articles", tmp_path
    )

    anchored = [row for row in cleaned if row.get("incident_anchor_key") == ANCHOR]
    assert len(anchored) == 1
    canonical_slug = anchored[0]["slug"]
    assert {row["source_slug"] for row in redirects} == set(LANG_SLUGS) - {canonical_slug}
    assert {row["target_slug"] for row in redirects} == {canonical_slug}
    assert all(row.get("incident_anchor_key") == ANCHOR for row in redirects)


def test_archive_incident_contract_fails_before_cleanup_and_passes_after(tmp_path):
    g = _load_generate(tmp_path)
    rows = _rows()[:3]
    _write_archive_and_redirects(tmp_path, rows, [])
    with pytest.raises(RuntimeError, match="Global incident identity contract FAILED"):
        g.validate_archive_incident_uniqueness(rows, tmp_path)

    cleaned, redirects = g.apply_canonical_story_cleanup(
        rows, tmp_path / "articles", tmp_path
    )
    cleaned, _ = g.enforce_canonical_redirects(
        cleaned, tmp_path / "articles", tmp_path, redirects
    )
    report = g.validate_archive_incident_uniqueness(cleaned, tmp_path)
    assert report["passed"] is True
    assert report["duplicate_incident_group_count"] == 0


def test_final_identity_anchor_outranks_fragmented_story_ids(tmp_path):
    g = _load_generate(tmp_path)
    rows = _rows()[:2]
    canonical = min(rows, key=g._incident_canonical_key)
    context = g._build_final_canonical_surface_context(
        rows,
        tmp_path,
        identity_index=types.SimpleNamespace(safe_story_ids=set(), all_story_ids=set()),
        redirect_map={},
    )
    identities = [
        g._final_canonical_surface_identity(
            row,
            f"https://treasurecoast.today/articles/{row['slug']}.html",
            context,
        )
        for row in rows
    ]
    assert {identity["identity_key"] for identity in identities} == {f"incident:{ANCHOR}"}
    assert {identity["canonical_slug"] for identity in identities} == {canonical["slug"]}


def test_every_category_surface_is_deduped_not_only_top_news(tmp_path):
    g = _load_generate(tmp_path)
    rows = _rows()[:4]
    cleaned, redirects = g.apply_canonical_story_cleanup(
        rows, tmp_path / "articles", tmp_path
    )
    cleaned, _ = g.enforce_canonical_redirects(
        cleaned, tmp_path / "articles", tmp_path, redirects
    )
    (tmp_path / "archive.json").write_text(json.dumps(cleaned), encoding="utf-8")
    canonical_slug = cleaned[0]["slug"]
    category = {
        "category_key": "indian_river",
        "category_label": "Indian River County",
        "hero": {**rows[0], "_archived_slug": rows[0]["slug"]},
        "cards": [
            {**row, "_archived_slug": row["slug"]}
            for row in rows[1:]
        ],
    }

    g.canonicalize_all_live_category_surfaces([category], category, tmp_path)
    assert category["hero"]["_archived_slug"] == canonical_slug
    assert category["cards"] == []
    report = g.validate_live_category_canonical_uniqueness(
        [category], category, tmp_path
    )
    assert report["passed"] is True


def test_live_category_contract_rejects_parallel_lang_placements(tmp_path):
    g = _load_generate(tmp_path)
    rows = _rows()[:2]
    _write_archive_and_redirects(tmp_path, rows, [])
    category = {
        "category_key": "indian_river",
        "category_label": "Indian River County",
        "hero": {**rows[0], "_archived_slug": rows[0]["slug"]},
        "cards": [{**rows[1], "_archived_slug": rows[1]["slug"]}],
    }
    with pytest.raises(RuntimeError, match="Live category canonical contract FAILED"):
        g.validate_live_category_canonical_uniqueness([category], category, tmp_path)


def test_different_named_people_remain_separate_incidents():
    geoffrey = incident_anchor_key(
        titles=("Firefighter Geoffrey Lang dies following personal tragedy",)
    )
    another = incident_anchor_key(
        titles=("Firefighter Michael Torres dies following medical emergency",)
    )
    assert geoffrey == ANCHOR
    assert another == "named-person-death:michael-torres"
    assert geoffrey != another


def test_pipeline_contains_global_archive_and_all_category_fail_closed_gates():
    source = (
        Path(__file__).resolve().parents[1] / "scripts" / "generate.py"
    ).read_text(encoding="utf-8")
    assert "validate_archive_incident_uniqueness(archive, OUTPUT_DIR)" in source
    assert "canonicalize_all_live_category_surfaces(" in source
    assert "validate_live_category_canonical_uniqueness(" in source
    assert source.index("canonicalize_all_live_category_surfaces(") < source.rindex(
        "index_html = render_index(all_categories, top_cat)"
    )
