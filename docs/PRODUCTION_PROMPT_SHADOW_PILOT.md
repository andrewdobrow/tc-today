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
