from __future__ import annotations

import importlib.util
import html as html_stdlib
import json
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tct_engine.semantic_material_update import (
    compose_material_update,
    validate_material_update,
)

CANONICAL_SLUG = (
    "2026-07-29-martin-county-commissioners-move-to-rewrite-shark-fishing-"
    "rules-after-public-bea"
)
UPDATE_SLUG = (
    "2026-08-01-martin-county-reviews-shark-fishing-ordinance-after-state-"
    "says-local-rules-must"
)
CANONICAL_HEADLINE = (
    "Martin County moves to rewrite shark fishing rules after complaints "
    "about drones, chum"
)
UPDATE_HEADLINE = (
    "Martin County reviews shark fishing ordinance after state says local "
    "rules must align with state law"
)
CANONICAL_BODY = (
    "Martin County commissioners directed staff to rewrite fishing rules for "
    "public beaches after residents complained that shark fishermen were using "
    "drones and remote-controlled boats to carry chum offshore near swimming "
    "areas. County attorneys told commissioners that Florida law allows fishing "
    "from public beaches and takes precedence over conflicting local rules.\n\n"
    "Residents said the use of drones and remotely operated boats could draw "
    "sharks closer to shore. Chumming directly from the beach is prohibited by "
    "state law, but speakers argued that carrying bait offshore could let anglers "
    "avoid that restriction while creating a safety concern for swimmers.\n\n"
    "Commissioners asked county staff to draft a replacement ordinance based on "
    "public safety. The proposal could restrict fishing during lifeguard hours and "
    "near boat docks while remaining consistent with state fishing law."
)
UPDATE_BODY = (
    "Martin County commissioners are continuing their review of shark fishing "
    "rules after the Florida Fish and Wildlife Conservation Commission directed "
    "the county to bring its beach ordinance into alignment with state law.\n\n"
    "The state guidance affects how the county can regulate fishing from public "
    "beaches. County staff is reviewing the ordinance and the limits created by "
    "Florida's preemption of local saltwater fishing regulations.\n\n"
    "The county's earlier discussion followed complaints about drones, chum and "
    "shark fishing near swimmers. Staff is expected to return with revised language "
    "for commissioners to consider."
)
COMPOSED_BODY = (
    "Martin County commissioners are continuing a rewrite of beach shark fishing "
    "rules that began after complaints about drones and chum, now after the Florida "
    "Fish and Wildlife Conservation Commission directed the county to align its "
    "local ordinance with state law. The new state direction will shape the same "
    "ordinance process commissioners started earlier this week.\n\n"
    "The original review followed complaints that shark fishermen were using drones "
    "and remote-controlled boats to carry bait offshore near swimming areas. "
    "Residents told commissioners the practice could attract sharks closer to shore. "
    "County attorneys also explained that Florida law permits fishing from public "
    "beaches and takes precedence over conflicting county restrictions.\n\n"
    "Commissioners had directed staff to draft a replacement ordinance grounded in "
    "public safety. Ideas discussed included limiting fishing during lifeguard hours "
    "and near boat docks while boats are launching or returning. Chumming directly "
    "from a beach is already prohibited under state law, while the complaints focused "
    "in part on bait being carried offshore before it was dropped.\n\n"
    "The wildlife commission's directive now gives Martin County formal guidance as "
    "staff prepares that rewrite. The county must make the local ordinance consistent "
    "with state law while deciding which safety restrictions remain within its local "
    "authority. Revised language is expected to return to commissioners for a future "
    "public vote."
)


class _Response:
    def __init__(self, payload: dict):
        self.content = [types.SimpleNamespace(text=json.dumps(payload))]


class _Messages:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.payload)


class _Client:
    def __init__(self, payload: dict):
        self.messages = _Messages(payload)


class _SequenceMessages:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.payloads) - 1)
        return _Response(self.payloads[index])


class _SequenceClient:
    def __init__(self, payloads):
        self.messages = _SequenceMessages(payloads)


def _load_generate(tmp_path: Path):
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
    path = ROOT / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("generate_material_update", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    module.OUTPUT_DIR = tmp_path
    module.SEMANTIC_GATE_CACHE_PATH = tmp_path / "data" / "semantic-publication-gate-cache.json"
    module.SEMANTIC_GATE_REPORT_PATH = tmp_path / "data" / "semantic-publication-gate.json"
    module.EDITORIAL_REGISTRY_PATH = tmp_path / "data" / "editorial_story_registry.json"
    return module


def _archive_row(slug: str, headline: str, date: str, story_id: str, body: str, source_url: str):
    return {
        "slug": slug,
        "headline": headline,
        "teaser": body.split("\n\n", 1)[0],
        "category_key": "local_gov",
        "category_label": "Local Government",
        "category_keys": ["local_gov", "martin"],
        "county_keys": ["martin"],
        "date": date,
        "lastmod": date,
        "first_published": f"{date}T12:00:00-04:00",
        "source_url": source_url,
        "source_headline": headline,
        "editorial_story_id": story_id,
        "legacy_identity_status": "identified",
        "ranking_eligible": True,
        "article_word_count": len(body.split()),
        "article_paragraph_count": 3,
        "publication_id": f"publication:{story_id}",
        "canonical_publication_id": f"publication:{story_id}",
        "canonical_slug": slug,
    }


def _write_page(root: Path, slug: str, headline: str, body: str, published: str):
    articles = root / "articles"
    articles.mkdir(parents=True, exist_ok=True)
    body_html = "".join(f"<p>{paragraph}</p>" for paragraph in body.split("\n\n"))
    (articles / f"{slug}.html").write_text(
        f'<span class="article-published">Published {published}</span>'
        f'<h1 class="article-headline">{headline}</h1>'
        f'<div class="article-body">{body_html}</div>'
        '<div class="article-share">share</div>',
        encoding="utf-8",
    )


def _decision():
    return {
        "status": "validated",
        "action": "update_existing_canonical",
        "recommended_action": "update_existing_canonical",
        "selected_candidate_slug": CANONICAL_SLUG,
        "same_real_world_event": True,
        "material_new_update": True,
        "confidence": 0.92,
        "shared_anchors": [
            "Martin County shark fishing ordinance",
            "same county commission proceeding",
        ],
        "novel_facts": [
            "Florida Fish and Wildlife Conservation Commission directed the county",
            "Local rules must align with state law",
        ],
        "reason": "The state directive materially changes the continuing ordinance process.",
        "validation_errors": [],
    }


def _composition_payload():
    return {
        "headline": "Martin County shark fishing rewrite advances after state directive",
        "teaser": (
            "Martin County is continuing its shark fishing ordinance rewrite after "
            "state wildlife officials directed the county to align its beach rules "
            "with Florida law."
        ),
        "body": COMPOSED_BODY,
    }


def test_material_update_composer_requires_original_context_and_new_development():
    canonical = {
        "headline": CANONICAL_HEADLINE,
        "teaser": CANONICAL_BODY.split("\n\n", 1)[0],
        "body": CANONICAL_BODY,
    }
    incoming = {
        "headline": UPDATE_HEADLINE,
        "teaser": UPDATE_BODY.split("\n\n", 1)[0],
        "body": UPDATE_BODY,
    }
    result = validate_material_update(
        _composition_payload(),
        canonical=canonical,
        incoming=incoming,
        decision=_decision(),
    )
    assert result["status"] == "validated"
    assert result["paragraph_count"] == 4
    assert result["baseline_lead_hits"]
    assert result["novelty_lead_hits"]


def test_material_update_composer_calls_model_once_and_validates_result():
    client = _Client(_composition_payload())
    result = compose_material_update(
        client,
        model="claude-sonnet-4-5",
        canonical={"headline": CANONICAL_HEADLINE, "body": CANONICAL_BODY},
        incoming={"headline": UPDATE_HEADLINE, "body": UPDATE_BODY},
        decision=_decision(),
    )
    assert result["status"] == "validated"
    assert len(client.messages.calls) == 1
    assert "temperature" not in client.messages.calls[0]


def test_material_update_rejects_stale_canonical_headline_even_when_body_is_valid():
    canonical = {
        "headline": "Martin County Sheriff's Office searches for missing Oklahoma visitor last seen at Chastain Beach",
        "teaser": "Deputies are searching for Michael Anthony Debevec II after he disappeared near Chastain Beach.",
        "body": CANONICAL_BODY,
    }
    incoming = {
        "headline": "Body found in Hutchinson Island mangroves believed to be missing Michael Debevec",
        "teaser": "A body believed to be Debevec was recovered near the House of Refuge.",
        "body": UPDATE_BODY,
    }
    decision = {
        **_decision(),
        "novel_facts": [
            "A body believed to be Michael Debevec was recovered in mangroves near the House of Refuge",
            "Formal identification remained pending",
        ],
    }
    payload = _composition_payload()
    payload["headline"] = canonical["headline"]
    result = validate_material_update(
        payload, canonical=canonical, incoming=incoming, decision=decision
    )
    assert result["status"] == "invalid_composition"
    assert "headline_not_refreshed_for_material_update" in result["validation_errors"]
    assert "headline_missing_material_development" in result["validation_errors"]


def test_material_update_composer_retries_once_when_only_headline_is_stale():
    stale = _composition_payload()
    stale["headline"] = CANONICAL_HEADLINE
    refreshed = _composition_payload()
    client = _SequenceClient([stale, refreshed])
    result = compose_material_update(
        client,
        model="claude-sonnet-4-5",
        canonical={"headline": CANONICAL_HEADLINE, "body": CANONICAL_BODY},
        incoming={"headline": UPDATE_HEADLINE, "body": UPDATE_BODY},
        decision=_decision(),
    )
    assert result["status"] == "validated"
    assert result["headline"] == refreshed["headline"]
    assert result["headline_retry"] is True
    assert len(client.messages.calls) == 2
    assert "REVISION REQUIRED" in client.messages.calls[1]["messages"][0]["content"]


def test_retroactive_material_update_rewrites_canonical_and_redirects_later_url(
    tmp_path, monkeypatch
):
    generate = _load_generate(tmp_path)
    canonical = _archive_row(
        CANONICAL_SLUG,
        CANONICAL_HEADLINE,
        "2026-07-29",
        "story_001155",
        CANONICAL_BODY,
        "https://www.wpbf.com/shark-rules",
    )
    incoming = _archive_row(
        UPDATE_SLUG,
        UPDATE_HEADLINE,
        "2026-08-01",
        "story_001724",
        UPDATE_BODY,
        "https://www.wptv.com/shark-state-directive",
    )
    incoming["source_image_url"] = "https://ewscripps.example.com/shark-update.jpg"
    incoming["image_url"] = incoming["source_image_url"]
    _write_page(tmp_path, CANONICAL_SLUG, CANONICAL_HEADLINE, CANONICAL_BODY, "July 29")
    _write_page(tmp_path, UPDATE_SLUG, UPDATE_HEADLINE, UPDATE_BODY, "August 1")

    def fake_gate(row, archive, cache, report, phase="forward_publication"):
        report["summary"]["evaluations"] += 1
        if row["slug"] == CANONICAL_SLUG:
            report["summary"]["no_candidate_passes"] += 1
            report["summary"]["retroactive_rows_retained"] += 1
            return ({"action": "new_story"}, None, [])
        report["summary"]["candidate_pairs"] += 1
        report["summary"]["canonical_updates_selected"] += 1
        decision = _decision()
        report["decisions"].append({
            "phase": phase,
            "incoming_headline": row["headline"],
            "incoming_story_id": row["editorial_story_id"],
            "decision": decision,
            "candidates": [{"slug": CANONICAL_SLUG}],
        })
        return decision, canonical, [{
            "slug": CANONICAL_SLUG,
            "headline": CANONICAL_HEADLINE,
            "evidence": {"retrieval_score": 0.78},
        }]

    monkeypatch.setattr(generate, "_run_semantic_publication_gate", fake_gate)
    monkeypatch.setattr(generate, "client", _Client(_composition_payload()))
    # The synthetic image host is deliberately accepted for this routing test.
    monkeypatch.setattr(generate, "_is_real_source_image_url", lambda value: bool(value))

    report = generate._new_semantic_publication_gate_report()
    cleaned, redirects, repair = generate._repair_recent_semantic_archive_duplicates(
        [canonical, incoming],
        tmp_path / "articles",
        tmp_path,
        {},
        report,
    )

    assert [row["slug"] for row in cleaned] == [CANONICAL_SLUG]
    assert repair["material_update_redirects"] == 1
    assert redirects[0]["source_slug"] == UPDATE_SLUG
    assert redirects[0]["target_slug"] == CANONICAL_SLUG
    assert redirects[0]["story_stage"] == "semantic-material-update-routing"
    assert canonical["meaningful_update_validated"] is True
    assert canonical["headline"] == _composition_payload()["headline"]
    assert canonical["headline"] != CANONICAL_HEADLINE
    assert canonical["lastmod"]
    assert canonical["latest_source_url"] == "https://www.wptv.com/shark-state-directive"
    assert len(canonical["source_history"]) == 2
    assert canonical["semantic_material_update_novel_facts"]
    assert report["summary"]["material_updates_applied"] == 1
    assert report["summary"]["material_update_composer_calls"] == 1

    html = (tmp_path / "articles" / f"{CANONICAL_SLUG}.html").read_text(
        encoding="utf-8"
    )
    assert "Updated " in html
    assert "Florida Fish and Wildlife Conservation Commission" in html
    assert "Published July 29, 2026" in html


def test_material_update_composition_failure_preserves_both_pages(tmp_path, monkeypatch):
    generate = _load_generate(tmp_path)
    canonical = _archive_row(
        CANONICAL_SLUG,
        CANONICAL_HEADLINE,
        "2026-07-29",
        "story_001155",
        CANONICAL_BODY,
        "https://www.wpbf.com/shark-rules",
    )
    incoming = _archive_row(
        UPDATE_SLUG,
        UPDATE_HEADLINE,
        "2026-08-01",
        "story_001724",
        UPDATE_BODY,
        "https://www.wptv.com/shark-state-directive",
    )
    _write_page(tmp_path, CANONICAL_SLUG, CANONICAL_HEADLINE, CANONICAL_BODY, "July 29")
    _write_page(tmp_path, UPDATE_SLUG, UPDATE_HEADLINE, UPDATE_BODY, "August 1")

    def fake_gate(row, archive, cache, report, phase="forward_publication"):
        if row["slug"] == CANONICAL_SLUG:
            return ({"action": "new_story"}, None, [])
        return _decision(), canonical, [{"slug": CANONICAL_SLUG, "evidence": {}}]

    monkeypatch.setattr(generate, "_run_semantic_publication_gate", fake_gate)
    monkeypatch.setattr(
        generate,
        "client",
        _Client({"headline": "Too short", "teaser": "No", "body": "No context."}),
    )
    report = generate._new_semantic_publication_gate_report()
    cleaned, redirects, repair = generate._repair_recent_semantic_archive_duplicates(
        [canonical, incoming],
        tmp_path / "articles",
        tmp_path,
        {},
        report,
    )

    assert {row["slug"] for row in cleaned} == {CANONICAL_SLUG, UPDATE_SLUG}
    assert redirects == []
    assert repair["held_count"] == 1
    assert report["summary"]["material_update_holds"] == 1


def test_absorbed_material_update_source_reuses_canonical_row(tmp_path):
    generate = _load_generate(tmp_path)
    canonical = _archive_row(
        CANONICAL_SLUG,
        CANONICAL_HEADLINE,
        "2026-07-29",
        "story_001155",
        CANONICAL_BODY,
        "https://www.wpbf.com/shark-rules",
    )
    canonical["meaningful_update_validated"] = True
    canonical["latest_source_url"] = "https://www.wptv.com/shark-state-directive"
    canonical["source_history"] = [
        {
            "role": "material_update",
            "source_url": "https://www.wptv.com/shark-state-directive",
        }
    ]
    incoming = {
        "source_url": "https://www.wptv.com/shark-state-directive?utm_source=rss"
    }

    matched = generate._find_absorbed_semantic_material_update_source(
        incoming, [canonical]
    )

    assert matched is canonical


def test_material_update_render_failure_is_transactional(tmp_path, monkeypatch):
    generate = _load_generate(tmp_path)
    canonical = _archive_row(
        CANONICAL_SLUG,
        CANONICAL_HEADLINE,
        "2026-07-29",
        "story_001155",
        CANONICAL_BODY,
        "https://www.wpbf.com/shark-rules",
    )
    incoming = _archive_row(
        UPDATE_SLUG,
        UPDATE_HEADLINE,
        "2026-08-01",
        "story_001724",
        UPDATE_BODY,
        "https://www.wptv.com/shark-state-directive",
    )
    original = json.loads(json.dumps(canonical))
    _write_page(tmp_path, CANONICAL_SLUG, CANONICAL_HEADLINE, CANONICAL_BODY, "July 29")
    _write_page(tmp_path, UPDATE_SLUG, UPDATE_HEADLINE, UPDATE_BODY, "August 1")

    def fake_gate(row, archive, cache, report, phase="forward_publication"):
        if row["slug"] == CANONICAL_SLUG:
            return ({"action": "new_story"}, None, [])
        decision = _decision()
        report["decisions"].append(
            {
                "phase": phase,
                "incoming_headline": row["headline"],
                "incoming_story_id": row["editorial_story_id"],
                "decision": decision,
                "candidates": [{"slug": CANONICAL_SLUG}],
            }
        )
        return decision, canonical, [{"slug": CANONICAL_SLUG, "evidence": {}}]

    monkeypatch.setattr(generate, "_run_semantic_publication_gate", fake_gate)
    monkeypatch.setattr(generate, "client", _Client(_composition_payload()))
    monkeypatch.setattr(
        generate,
        "_render_retroactive_semantic_material_update",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk error")),
    )

    report = generate._new_semantic_publication_gate_report()
    cleaned, redirects, repair = generate._repair_recent_semantic_archive_duplicates(
        [canonical, incoming],
        tmp_path / "articles",
        tmp_path,
        {},
        report,
    )

    assert {row["slug"] for row in cleaned} == {CANONICAL_SLUG, UPDATE_SLUG}
    assert redirects == []
    assert repair["held_count"] == 1
    assert report["summary"]["material_update_holds"] == 1
    assert canonical == original


class _CurrentSdkStrictMaterialMessages:
    """Minimal current Anthropic messages.create signature: no temperature kwarg."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    def create(self, *, max_tokens, messages, model, timeout=None):
        self.calls.append({
            "max_tokens": max_tokens,
            "messages": messages,
            "model": model,
            "timeout": timeout,
        })
        return _Response(self.payload)


class _CurrentSdkStrictMaterialClient:
    def __init__(self, payload: dict):
        self.messages = _CurrentSdkStrictMaterialMessages(payload)


def test_material_update_request_matches_current_anthropic_sdk_without_temperature():
    client = _CurrentSdkStrictMaterialClient(_composition_payload())
    result = compose_material_update(
        client,
        model="claude-sonnet-4-5",
        canonical={"headline": CANONICAL_HEADLINE, "body": CANONICAL_BODY},
        incoming={"headline": UPDATE_HEADLINE, "body": UPDATE_BODY},
        decision=_decision(),
    )

    assert result["status"] == "validated"
    assert len(client.messages.calls) == 1


def test_waste_pro_semantic_update_passes_second_context_contract(tmp_path, monkeypatch):
    """Regression for Aug. 31 Waste Pro false ``new_development_missing`` hold."""
    generate = _load_generate(tmp_path)
    canonical = {
        "slug": "2026-08-29-port-st-lucie-homeowners-to-receive-credits-on-solid-waste-bills-from-24-million",
        "headline": "Port St. Lucie homeowners to receive credits on solid waste bills from $24 million Waste Pro settlement",
        "teaser": "Port St. Lucie residents will receive credits from the city's Waste Pro settlement.",
        "body": (
            "Port St. Lucie reached a $24 million settlement with former trash hauler Waste Pro after "
            "a dispute over missed pickups. The city said eligible residents would receive credits.\n\n"
            "The settlement resolved litigation over Waste Pro service.\n\n"
            "City officials said distribution details would follow."
        ),
        "date": "2026-08-29",
        "first_published": "2026-08-29T12:00:00-04:00",
    }
    incoming = {
        "headline": "Port St. Lucie homeowners are getting a notice in the mail about their Waste Pro credit - WPEC",
        "source_headline": "Port St. Lucie homeowners are getting a notice in the mail about their Waste Pro credit - WPEC",
        "source_title": "Port St. Lucie homeowners are getting a notice in the mail about their Waste Pro credit - WPEC",
        "body": (
            "Port St. Lucie homeowners are finding a flyer in their mailboxes explaining how the $24 million "
            "settlement will appear on their property tax bill. The settlement is being distributed over "
            "95,000 eligible properties, with different credit amounts based on eligibility."
        ),
        "source_url": "https://cbs12.com/news/local/waste-pro-credit",
        "published": "Mon, 31 Aug 2026 16:35:41 GMT",
    }
    decision = {
        "status": "validated",
        "action": "update_existing_canonical",
        "selected_candidate_slug": canonical["slug"],
        "same_real_world_event": True,
        "material_new_update": True,
        "confidence": 0.95,
        "shared_anchors": ["$24 million Waste Pro settlement", "Port St. Lucie"],
        "novel_facts": [
            "Specific credit amounts: $364 for 57,000 long-term homeowners, $64 for 38,000 other eligible properties",
            "95,000 total eligible properties",
            "Credits appearing on property tax bills (not just solid waste bills)",
            "City Council voted in June to use tax credits instead of checks",
        ],
        "validation_errors": [],
    }
    composed_body = (
        "Port St. Lucie homeowners are finding flyers in their mailboxes explaining how the city's $24 million "
        "settlement with Waste Pro will appear as credits on their property tax bills. The settlement money is "
        "being distributed over 95,000 eligible properties following the city's lawsuit against its former trash "
        "hauler for two years of unreliable service and missed pickups.\n\n"
        "About 57,000 homeowners who have stayed at the same property since the 2022 tax roll will receive an "
        "estimated $364 credit. Roughly 38,000 other eligible properties will receive an estimated $64 credit.\n\n"
        "The City Council voted in June to return all of the settlement money through property tax credits rather "
        "than mailing checks. Residents objected to the decision.\n\n"
        "The credits are landing as property owners receive their TRIM notices, and voters are expected to weigh "
        "in on twice-weekly pickup through a straw ballot question in November."
    )
    monkeypatch.setattr(
        generate,
        "compose_semantic_material_update",
        lambda *args, **kwargs: {
            "status": "validated",
            "headline": "Port St. Lucie homeowners receiving Waste Pro settlement credits on property tax bills",
            "teaser": "Port St. Lucie homeowners are receiving Waste Pro settlement credits on property tax bills, with different amounts across 95,000 eligible properties.",
            "body": composed_body,
            "word_count": len(composed_body.split()),
            "paragraph_count": 4,
            "baseline_lead_hits": ["port", "lucie", "waste", "settlement"],
            "novelty_lead_hits": ["95000", "property"],
            "validation_errors": [],
        },
    )
    report = {"summary": {}, "material_update_compositions": []}

    merged, result = generate._semantic_material_update_composition(
        canonical,
        incoming,
        decision,
        report,
        phase="forward_publication",
    )

    assert merged is not None
    assert result["status"] == "validated"
    assert result["context_diagnostics"]["passed"] is True
    assert result["context_diagnostics"]["novelty_anchor"] == "semantic_gate_novel_fact"
    assert "95000" in result["context_diagnostics"]["semantic_novel_fact_hits"]


def test_committed_debevec_material_update_repairs_stale_headline_without_changing_permalink(tmp_path):
    """Production regression: body can be current while the canonical H1 is stale.

    Once a semantic material update has already been committed/absorbed, the source
    may not naturally replay through the composer.  The persisted latest source
    headline is therefore allowed to repair the visible headline only when it
    demonstrably advances the recorded semantic novelty, while the original slug and
    custom identity key remain immutable.
    """
    generate = _load_generate(tmp_path)
    slug = (
        "2026-08-29-martin-county-sheriffs-office-searches-for-missing-"
        "oklahoma-visitor-last-seen-at-chastain-beach"
    )
    old_headline = (
        "Martin County Sheriff's Office searches for missing Oklahoma visitor "
        "last seen at Chastain Beach"
    )
    source_headline = (
        "Martin County Sheriff's Office investigates body found in Hutchinson "
        "Island mangroves - WPTV"
    )
    repaired_headline = (
        "Martin County Sheriff's Office investigates body found in Hutchinson "
        "Island mangroves"
    )
    updated_body = (
        "A body discovered deep in the mangroves on Hutchinson Island is believed "
        "to be Michael Anthony Debevec II, according to the Martin County Sheriff's "
        "Office. Formal identification remained pending with the Medical Examiner."
    )
    entry = {
        "slug": slug,
        "headline": old_headline,
        "permalink_origin_headline": old_headline,
        "custom_headline_key": generate._exact_custom_headline(old_headline),
        "authoritative_custom": True,
        "meaningful_update_validated": True,
        "meaningful_update_basis": "semantic_material_update_gate",
        "semantic_material_update_novel_facts": [
            "A body was discovered deep in mangroves near the House of Refuge on Hutchinson Island",
            "The Sheriff's Office believes the body may be Michael Anthony Debevec II based on clothing",
            "Formal identification remained pending with the Medical Examiner",
        ],
        "latest_source_headline": source_headline,
        "latest_source_url": (
            "https://www.wptv.com/news/treasure-coast/region-martin-county/"
            "martin-county-sheriffs-office-investigates-body-found-in-hutchinson-island-mangroves"
        ),
    }
    articles = tmp_path / "articles"
    articles.mkdir(parents=True)
    page = articles / f"{slug}.html"
    schema = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": old_headline,
        "url": f"https://treasurecoast.today/articles/{slug}.html",
    }
    page.write_text(
        "\n".join([
            f"<title>{old_headline} | Treasure Coast Today</title>",
            f'<meta property="og:title" content="{old_headline} | Treasure Coast Today">',
            f'<meta name="twitter:title" content="{old_headline} | Treasure Coast Today">',
            f'<script type="application/ld+json">{json.dumps(schema)}</script>',
            f'<h1 class="article-headline">{old_headline}</h1>',
            f'<figure><img src="image.jpg" alt="{old_headline}"></figure>',
            f'<div class="article-body"><p>{updated_body}</p></div>',
            f'<script>const data = {{ title: document.title, text: {json.dumps(old_headline)}, url: window.location.href }};</script>',
        ]),
        encoding="utf-8",
    )
    body_before = updated_body
    custom_key_before = entry["custom_headline_key"]

    report = generate._repair_stale_semantic_material_update_headlines(
        [entry], articles, tmp_path
    )

    assert report["repaired_count"] == 1
    assert report["repaired"][0]["slug"] == slug
    assert report["repaired"][0]["updated_headline"] == repaired_headline
    assert entry["slug"] == slug
    assert entry["headline"] == repaired_headline
    assert entry["permalink_origin_headline"] == old_headline
    assert entry["custom_headline_key"] == custom_key_before
    assert entry["semantic_material_update_headline_repaired"] is True

    html = page.read_text(encoding="utf-8")
    escaped_repaired = html_stdlib.escape(repaired_headline, quote=True)
    assert f"<title>{escaped_repaired} | Treasure Coast Today</title>" in html
    assert f'<meta property="og:title" content="{escaped_repaired} | Treasure Coast Today">' in html
    assert f'<meta name="twitter:title" content="{escaped_repaired} | Treasure Coast Today">' in html
    assert f'<h1 class="article-headline">{html_stdlib.escape(repaired_headline)}</h1>' in html
    assert f'alt="{escaped_repaired}"' in html
    assert f'text: {json.dumps(repaired_headline)}' in html
    assert body_before in html
    schema_text = html.split('<script type="application/ld+json">', 1)[1].split("</script>", 1)[0]
    assert json.loads(schema_text)["headline"] == repaired_headline[:110]

    repair_report = json.loads(
        (tmp_path / "data" / "material-update-headline-repair.json").read_text(encoding="utf-8")
    )
    assert repair_report["repaired_count"] == 1


def test_committed_material_update_headline_repair_is_noop_when_headline_already_advanced(tmp_path):
    generate = _load_generate(tmp_path)
    slug = "2026-08-29-example-missing-person"
    old_headline = "Sheriff searches for missing Oklahoma visitor"
    current_headline = "Body found in mangroves believed to be missing Oklahoma visitor"
    entry = {
        "slug": slug,
        "headline": current_headline,
        "permalink_origin_headline": old_headline,
        "meaningful_update_validated": True,
        "meaningful_update_basis": "semantic_material_update_gate",
        "semantic_material_update_novel_facts": [
            "A body was found in mangroves during the search",
        ],
        "latest_source_headline": "Body found in mangroves during missing-person search - WPTV",
        "latest_source_url": "https://www.wptv.com/example",
    }
    articles = tmp_path / "articles"
    articles.mkdir(parents=True)
    page = articles / f"{slug}.html"
    original_html = f'<h1 class="article-headline">{current_headline}</h1><p>Updated body.</p>'
    page.write_text(original_html, encoding="utf-8")

    report = generate._repair_stale_semantic_material_update_headlines(
        [entry], articles, tmp_path
    )

    assert report["repaired_count"] == 0
    assert entry["headline"] == current_headline
    assert page.read_text(encoding="utf-8") == original_html
