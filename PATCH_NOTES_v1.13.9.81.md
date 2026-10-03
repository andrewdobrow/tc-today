# TCT v1.13.9.81 — Newsroom copy-desk quality guard

Apply on top of v1.13.9.80.

## Why
Repeated generated prose was reaching publication with mechanical conjunction chains such as:

> video and phone and vehicle search warrants

TCT already required factual grounding and told the model not to use em dashes, but there was no deterministic publication boundary for objective copy-style failures and no bounded repair step when the writer missed house style.

## Changes

- Adds a shared `NEWSROOM_COPY_DESK_STANDARD` for all automated news writing.
- Requires publication-ready grammar, syntax, punctuation, parallel construction, clarity, varied sentence structure, and natural newspaper prose while preserving factual limits.
- Reiterates that engaging prose must never become sensationalized, speculative, editorialized, embellished, or padded.
- Enforces **no em dashes** in generated headline, teaser, or body copy.
- Adds a narrow deterministic detector for compressed repeated-`and` chains such as `A and B and C`, while avoiding ordinary coordinated clauses and direct quotations.
- Adds one bounded wording-only Sonnet 5 copy-desk repair when the writer violates an objective house-style rule.
- The repair is prohibited from adding facts, inferences, background, or causal claims. It preserves names, numbers, chronology, attribution, uncertainty, and allegation status.
- Direct quotations may not be silently edited. If a quote itself conflicts with the no-em-dash rule, the repair is instructed to paraphrase the supported statement instead.
- Adds a second final generated-copy gate so legacy/rollback paths cannot bypass the house-style rules.
- Adds a dedicated `copydesk_integrity` generation failure code so a persistent defect fails closed into the existing bounded retry/archive-recovery path rather than publishing bad copy.
- Bumps `CATEGORY_GENERATION_PROMPT_VERSION` to `v1.13.9.81-newsroom-copy-desk` so stale cached generated copy is not reused under the new writing standard.

## Scope

This changes automated generated news copy only. It does not rewrite custom/manual articles. It does not alter factual/source identity, canonical identity, Bunny image mirroring, events, paywall behavior, or publication routing.

## Validation

- Exact Rondon-style repeated-`and` regression covered.
- Normal comma-list construction accepted.
- Em dash detection covered.
- Direct-quote repeated-conjunction exemption covered.
- Bounded copy-desk repair path covered.
- Final publication boundary covered.
- Production pytest suite, excluding the same two intentionally ignored suites used by the workflow: **1,479 passed, 0 failed** across four chunks.
- `python scripts/validate_package.py`: **42 modules imported, 123 public exports verified**.
- `python -m py_compile scripts/generate.py`: passed.
