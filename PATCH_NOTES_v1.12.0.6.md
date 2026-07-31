# TCT v1.12.0.6 — Cross-Source Update Identity Integrity

## Problem

Different-publisher follow-ups could arrive with a new URL, rewritten headline and fragmented or missing persistent story ID. When exact ledger keys did not connect the reports, the conservative fallback rejected legitimate continuations and allowed `generate_new` to reach the slug-creation path.

The July 30 regressions included the Port St. Lucie double-shooting 911 calls, the 80-mph roof-chase arrests report and Martin County shark-fishing pushback.

## Fix

- Adds deterministic, source-independent same-event evidence before generation and again at both publication write barriers.
- Uses corroborating people, precise street-level locations, event family, locality, agency/governing body, subject phrases, bounded time and distinctive incident facts.
- Treats changed reporting stages such as 911 calls, arrests, neighbor reaction and public pushback as possible developments rather than automatic new stories.
- Makes one-sided structured anchors non-contradictory while retaining hard rejection for two conflicting anchors, localities or event families.
- Repairs fragmented or missing incoming story IDs to the canonical story ID and changes `generate_new` to `update_existing` before generation.
- Attaches the original canonical context before article generation.
- Preserves the established page when a contextual update lead fails, rather than minting a parallel permalink.
- Preserves `first_published`; `last_meaningful_update_at` remains gated by changed content, original-event context and genuine novelty.
- Keeps authoritative and recurring custom publications outside the cross-source fallback.

## New report

`data/cross-source-update-identity.json`

Each match records the incoming headline, resolved publisher URL, canonical slug and headline, fragmented and canonical story IDs, evidence dimensions, confidence, relationship, decision trace and final publication action.

## Permanent regressions

Positive fixtures cover:

- double shooting → later 911-call report;
- 80-mph roof chase → later arrest report;
- shark-fishing proposal → public/commissioner pushback;
- infant death → neighbor reaction;
- Google News wrapper → resolved different publisher;
- different or missing persistent story ID.

Negative controls cover unrelated shootings, unrelated pursuits, different county policy proposals, similar 911 wording without shared facts and recurring custom reports.

## Test maintenance

The existing follow-up importance test now uses relative recent timestamps so its lifecycle assertion cannot expire as the calendar advances. Production scoring behavior is unchanged.
