# TCT production-prompt editorial shadow — isolated pilot

## Purpose and exact scope

Move beyond the generic historical model-capability test while avoiding any edits to the live newsroom. The pilot invokes **TCT's own** `scripts.generate._run_assignment_editor` and `_run_assignment_writer` functions (including their real prompts and parser/guard behavior) in a stand-alone read-only GitHub Actions job. Claude Sonnet 5 and GPT-6.1 Sol receive the same candidate packet and the writer is given the **same fixed story and angle** for a fair prose comparison; the editor independently decides story selection.

### Important limitation: reconstructed inputs, not live interception

The source pool comes from the previously saved `data/assignment-editor-shadow-report.json`: actual production categories, source URLs, candidate order, titles, dates, category-fit and hero eligibility. Its timestamp currently points to **September 3, 2026**, not October 25.

The report does **not** preserve the full historical prompt packet. The pilot reconstructs source text from pre-report historical Git versions of `data/generation-cache.json`, matching exact original source URLs, requiring at least 110 words, and requiring capture **within seven days before** the report timestamp. It refuses to compare any category with missing original source evidence and requires at least two distinct source URLs. It cannot reconstruct historically accurate canonical story contexts and therefore leaves those fields empty, marking `story_form="new"` as an assumption. The packet is **NOT** equivalent to the exact live packet.

This test is therefore valid for **production prompt behavior on authentic historical candidate pools**, NOT for canonical material-update continuity, incident identity, deduplication, final publication gate behavior, fresh story acquisition or actual homepage ordering. Those require a later explicit live packet capture and dry-run of the actual deterministic guards. Do not claim those capabilities have been proven by this pilot.

## Safety

- Reuses the existing **Historical Editorial Model Bake-Off** workflow with an opt-in `comparison_mode` input. **No new Actions workflow**.
- Manual dispatch only, `permissions: contents: read`, checkout `persist-credentials: false`.
- Does not invoke the generator's main publishing entry point, deploy, Git push, newsletters, database writes or canonical archive updates.
- Imports generator functions for prompt generation and edits its client only **in the disposable job process**; all outputs remain temporary GitHub Actions artifacts.
- The live `Update Treasure Coast Today` workflow, application, archive, canonical URLs and production Claude configuration are unchanged.
- Both APIs' credentials are referenced as Actions secrets only when `dry_run=false`. Never paste or commit keys.
- The pilot enforces a **$2 maximum internal estimated-cost guard**, even if the historical workflow's generic default is $12. This is **not** a provider-side billing hard stop; usage may exceed the estimate.
- A response failure leaves diagnostic artifacts and must not be counted as an editorial win.

## How to run

After CI passes and the PR is merged:

1. Actions → **Historical Editorial Model Bake-Off** → Run workflow on `main`.
2. Set **Comparison mode** = `production_prompt_shadow`.
3. Set **Shadow categories** = `2`, **Historic days** = `100`, **Max API spending** = `2`, and **Dry run** = **true**.
4. Read the artifact `editorial-shadow-output/coverage.json` and `packets.json`. Confirm that at least one complete source category was reconstructed, inspect timestamps, URL provenance and sources. **Do not switch to paid mode if coverage is poor.**
5. If the evidence is adequate, rerun identical options with **Dry run false**, then blind-score `blind-review.md` before opening `answer-key.json`. The artifact also includes `results.json` and `usage.json`.

### Scoring

Score editorial selection separately from same-story writing: source fidelity (30%), editorial choice / omission (25%), continuity and timing (20%), writing (15%), three-county relevance (10%). Failure conditions: fabricated direct quote, wrong incident or person, significant unsupported allegations, stale-event framing, incorrect source mapping, or duplicate story treated as an independent scoop. Watch for copied publisher attributions and headline / lead divergence. A model that produces a better prompt-replay output has **not** thereby passed TCT's canonical update or final publish gates.

## Beyond this pilot

For the **true live production-context shadow**, the next prerequisite is an explicitly gated, immutable capture of exact source packets **at the point the production engine builds them**, with the canonical-context registry snapshot and deterministic decision metadata. Compare both providers against the same captured packets with publication disabled; run material-update, identity, and final-ranking guard checks independently on the outputs. That capture must be developed and reviewed separately; never turn it on implicitly in production.


## Recovery and model-quality failures

Paid run [#40257576336](https://github.com/andrewdobrow/tc-today/actions/runs/40257576336) demonstrated two separate issues. The first category produced both models' complete writing and editor outputs. In the St. Lucie category, both models' writer paths were blocked by production `CopyDeskIntegrityError: ... chained_and` even after the generator's repair; **do not treat these as publishable drafts or score them as tied successes**. The run then crashed during report creation because results rows contain `source_inputs`, not a nested `packet`.

The repaired script always writes a full `blind-review.md` and `summary.json` from results, including failures; it preserves the assignment-editor plan when the writer subsequently fails. A test with at least one complete paired category now returns success with **explicit partial coverage** instead of confusing the result-generation crash with model quality. No paired output at all still fails, with preserved diagnostic artifacts.

To repair a **downloaded existing GitHub artifact offline and for $0**, extract its ZIP to a directory with `editorial-shadow-output/results.json` and `usage.json`, then run:

```sh
python scripts/production_prompt_shadow.py --output editorial-shadow-output --recover-existing
```

This only reads saved results and creates `blind-review.md` and `summary.json` locally. It neither calls OpenAI nor Anthropic, nor rewrites production news or existing result data. `answer-key.json` remains separate; review the blinded outputs first.

**Benchmark interpretation:** A green experiment job means the runner, output reporting and minimum viable paired comparison completed. It does **not** mean every model output passed TCT's newsroom quality checks. Always inspect `summary.json`, especially `failed_variants` and `complete_writing_and_editor_pairs`, before drawing editorial conclusions.


## Copy-desk investigation: retain both rejected draft and repair (2026-10-25)

Runs [#40257576336](https://github.com/andrewdobrow/tc-today/actions/runs/40257576336) and [#40259760351](https://github.com/andrewdobrow/tc-today/actions/runs/40259760351) encountered the same TCT production `CopyDeskIntegrityError: ... chained_and` on the St. Lucie writer path for **both** tested models. The successful reporting run had **one of two** complete writing pairs and **two of two** complete assignment-editor pairs. The actual rejected writer responses from those runs **were not saved**; a retrospective factual verdict on whether the model or the rule was at fault is impossible from those archives.

The production regression test `tests/test_newsroom_copydesk_quality.py` deliberately rejects repetitive `and` chains, accepts ordinary coordinated lists, and does not automatically condemn repetitions inside a direct quote. That supports leaving the live copy-desk threshold alone until we have a real failed response.

**The shadow capture now records, before validation, every raw model reply**, its chronological writer attempt number (initial draft vs copy-desk repair), response state, hashed prompt, and token usage; successful model content is not exempt from the same capture. It then annotates each draft with read-only issues from `generate._copydesk_text_issues` for the headline, teaser, and body. The writer and original model assignment still fail if the live copy desk says they fail. Neither a rejected original nor rejected repair is treated as publishable copy.

Artifacts:
- `results.json` keeps each variant's `writer_attempts` (raw response, text fields and validator issue diagnostics) even when the writer fails.
- `blind-review.md` displays **both** unpublished attempts and issue details, while keeping model identity hidden.
- `usage.json`, `summary.json`, `answer-key.json` remain separate.
- Historical artifacts from **before this capture change** cannot recover responses never saved.

**Review protocol for an eventual new paid run:** inspect candidate evidence and both attempts for fact fidelity and the precise sentence(s) flagged; distinguish actual grammar problems, correct quoted speech, false-positive detector hits and a failed copy-desk repair prompt. Only propose a production style-rule change if examples show a systematic false positive. A future run is optional: merge + dry run is free and proves the test wiring, while another paid run costs API usage and should be approved separately.

### Exact live source/canonical packet capture remains a separate milestone

This change does **not** claim to capture full live production packets. The existing `assignment-editor-shadow-report.json` stores only source summaries and the historical replay reconstructs missing article text. Full parity requires a separate **opt-in, read-only capture point in the actual production packet builder** `scripts/generate.py::_build_assignment_editor_packet`, preserving original source URLs, full extracted article texts, published/source timestamps, `story_form`, canonical headline/body, cross-source identity/revision metadata, and a deterministic fingerprint of the relevant locked story registry. Capture must run *before* publisher transformations and must not be used as publication authority. The current two-model replay will then consume that verified, immutable packet verbatim, rather than filling absent canonical context with `story_form="new"`. This integration requires a focused change to the large production generator and additional safety review; it is **not** enabled or hidden in this PR.


## Resolved diagnosis: 2026-10-26 paid shadow #40262582566

A paid replay generated 2/2 complete paired assignment-editor outputs, 1/2 complete paired writing outputs and an internal estimated cost of $0.122778. Its artifact captured four St. Lucie County writer attempts (first and repair for each provider).

Both models' first and repaired texts contain a grammatically valid construction in federal court reporting:

> prepare and submit false individual and trust tax returns

The two conjunctions coordinate **two different constituents**: two verbs ("prepare"/"submit") and two types of tax returns ("individual"/"trust"). The production `_copydesk_text_issues` implementation flagged this as `chained_and` because there are **three words** between the first and second `and`: `submit false individual`. It is not the `A and B and C` prose problem the validator is intended to block. The earlier rejected drafts did not become publishable; they simply failed an overbroad mechanical style check. The finding does **not** establish overall accuracy or appropriateness of those drafts, which require separate editorial review.

Targeted fix in PR: narrow the deterministic `chained_and` condition from **three or fewer intervening words** to **two or fewer**, preserving the existing checks for compressed repeated lists, em dashes, normal lists and quoted speech. A dedicated regression test reproduces the legal-reporting sentence and confirms it is accepted; other tests explicitly confirm real `A and B and C` patterns are still rejected. This is a purposeful, narrowly justified relaxation of an *overbroad heuristic*, not a wholesale lowering of TCT's newsroom standards.

Additionally, shadow diagnostics now preserve the validator's actual `snippet` property when present, making future failures easier to pinpoint without storing full production prompts. No shadow rerun or production publish was triggered while preparing this change.
