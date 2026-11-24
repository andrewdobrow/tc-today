# Incident: cross-story criminal allegation in Evergreen Club burglary report (2026-11-24)

## Severity
**Critical editorial integrity / incorrect criminal attribution.** The published November 24 burglary article falsely connected a named man and an attempted-murder allegation from an unrelated October 29 stabbing report to a Palm City burglary. A first-party correction alone is insufficient; this incident requires provenance and publication safeguards.

## Confirmed reconstruction (original production evidence)

- Original generation workflow: [Update Treasure Coast Today, run 45405809207](https://github.com/andrewdobrow/tc-today/actions/runs/45405809207), started 2026-11-24 13:40:09 UTC. The site produced its first contaminated article in commit `fd57d4c3e1412b9ccbaf1b534b99f5f7a410e5b8` (13:51:12 UTC), before the later run 45439788921.
- Source, from original `archive.json` in the **generation-diagnostics artifact** (ID `14925608301`): `https://cbs12.com/news/local/4-men-arrested-after-overnight-burlgary-martins-county-evergreen-club-caught-wearing-masks-gloves-palm-city-residents-check-vehicles-crime-florida-news` (WPEC/CBS12), source headline "4 men arrested after overnight burglary at Martin County’s Evergreen Club - WPEC".
- The same original archive's **source-derived** `event_identity` for this article included `bradley`, `acquaintance`, `box`, `neck`, `slash`, `murd`, `boca`, `rio`, `trail`, and `event_families: ["shooting"]`, despite the headline and story being a burglary. These cannot have originated in the later HTML-rendering layer; they were present before publication and before the writer's final output.
- The original job log at 2026-11-24 13:43:26.6289864 UTC states: **`SOURCE FACT GUARD: repaired missing named-suspect fact in article draft`**.
- Next log lines report one assignment-editor writer call, a 165-word source fetch, and a successfully generated Crime & Safety hero. The model repair path in `scripts/generate.py` prompts for "Verified SAME-ARTICLE source evidence" whenever a regex-derived named-suspect fact is missing, and accepts the repair if the named person appears.
- The full original first-commit article body included `MCSO also said Bradley Martin, 32, was charged with attempted murder after allegedly slashing an acquaintance in the neck with a box cutter.` Both a later normal regeneration and the site's source/copydesk checks retained the paragraph.
- The named alleged offense belongs to TCT's **2026-10-29 SE Indian Street attack**, not the 2026-11-24 Evergreen Club burglary. Nothing in this evidence supports an allegation that the October suspect was connected to the burglary.

## Defect chain and defenses that failed

1. **Publisher chrome contaminated source extraction.** The source text recovered from the CBS12 page was not restricted to the actual reported incident. The old Sinclair recommendation-section cleaner was gated behind the generic **220-word** source-focus threshold, although this run fetched **165 words**. It also relied on word overlap, including potential overlap between the suspect's surname and "Martin County". Short articles and recommendation cards therefore escaped containment.
2. **The candidate was converted into a mandatory "verified" suspect.** `named_suspect_facts` matched any charge/arrest declaration in the assembled source text without comparing the incident type to the assigned source headline. `_build_assignment_editor_packet` carried it as a critical fact.
3. **The AI copy-repair stage amplified the contamination.** The initial draft omitted the unrelated name. `_run_assignment_writer` explicitly prompted a second writer call to insert omitted named-suspect information. The log confirms that repair succeeded.
4. **The final publisher accepted it.** The source-fact gate previously only checked for **missing** named facts; it did not reject a newly inserted named criminal allegation belonging to a competing incident. Existing copydesk tests passed.

## Remediation in this patch

- Run recognizably Sinclair-specific source-chrome cleanup on short articles **before** generic 220-word logic, and before persisting fetched publisher text to the generation cache. Recheck cached values on every read.
- Prevent suspect surnames matching local county tokens from authorizing unrelated crime claims; stop Sinclair chrome extraction upon a positively detected cross-incident named criminal allegation.
- Make named-suspect fact extraction source-headline aware. Only explicit named criminal incident conflicts are vetoed; normal news articles mentioning a suspect in the same incident remain eligible.
- Re-filter critical facts even when they come from a cached assignment packet. In the live writer and final publication gate, refuse a named criminal allegation about an incompatible incident.
- Add incident-derived tests for source focus under 220 words, positive named identity, multi-event headlines, assignment fact extraction, and final publication rejection.

## Correction and boundaries

The unrelated paragraph was separately removed from the public article HTML on main in commit `019f0ff785edde04abd1546fefc3cf88fe806005`, and a durable slug-scoped content correction was added in commit `78ae50cefdce23f82352b0a4c8c02663a4e28458`.

The archived source-text bytes/model prompts were not available in the retained generation-diagnostics artifact; this audit does **not** pretend to reconstruct the exact trafilatura text or prove which specific HTML section introduced each unrelated token. The combination of original source-derived identity, production log, source-focus code, and actual repair flow establishes the software failure chain. The safety fix does not claim to solve every possible semantic hallucination; future factual-claim verification should expand provenance checks beyond explicit named criminal allegations.

## Evidence

- [Original run 45405809207](https://github.com/andrewdobrow/tc-today/actions/runs/45405809207)
- [Original bad publication commit fd57d4c](https://github.com/andrewdobrow/tc-today/commit/fd57d4c3e1412b9ccbaf1b534b99f5f7a410e5b8)
- [Second run 45439788921](https://github.com/andrewdobrow/tc-today/actions/runs/45439788921)
- [Original generation diagnostics artifact 14925608301](https://github.com/andrewdobrow/tc-today/actions/runs/45405809207/artifacts/14925608301)
