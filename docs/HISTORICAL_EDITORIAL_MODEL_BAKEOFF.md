# Historical editorial model bake-off — TCT

## Why this exists

Test **editorial quality first** between the existing Claude Sonnet 5 and OpenAI GPT-6.1 Sol without waiting for fresh Sunday reporting and without touching the production newsroom, site, archive, editorial sorting, or notifications. The workflow is manual-only and has read-only repository permissions. Experiment results are stored as GitHub Actions artifacts, not committed or published on TCT. Artifact access follows the GitHub repository's permissions; do not treat these artifacts as a secret vault.

## Corpus construction

1. Check out full Git history.
2. Inspect one historical revision of the existing data/generation-cache.json per day, up to the requested historical depth. Read *source_text* snapshots already retained at the time; do not scrape current live article pages.
3. Link original source URLs to **already-published canonical** entries in archive.json. Require an exact normalized source-URL match, a substantial archived source excerpt, and a source capture **on the publication date or the preceding day, never after**. Exclude custom, sponsored, and unresolved-identity items. Historical publication dates are day-granular, so same-day extracts may still contain later developments; this is **not** a precise publication-time replay.
4. Stratify article examples across months and sections rather than selecting only recent or sensational stories. The previously published TCT headline is held back for human evaluation and **not** supplied to either writing model.
5. For homepage ranking, use **all eligible historical cases**, independently of the writing sample. Collect up to eight month-diverse cohorts of three to six stories published on the **same historical day**, each with a distinct original source URL. No artificial comparison of a June event with one in October.
6. Fail rather than fabricating evidence or falling back to TCT's final article text if fewer than 12 trustworthy writing cases **or zero distinct-source same-day ranking cohorts** are available. Even on failure, inspect the coverage and source artifacts to diagnose gaps.

The result is a replay benchmark, not proof that the archived source text was exhaustive or that the originally published TCT story was correct. Some excerpt caches may be incomplete or include sidebars; reviewers see the full archived evidence supplied to the writing models, the capture date, and the snapshot reference. Score unsupported claims and quote accuracy particularly carefully. Direct competitor attributions in article prose violate TCT style.

## Running it

After the pull request is reviewed and merged, open **Actions → Historical Editorial Model Bake-Off → Run workflow**.

- Article count: 30 initially (range 12–50).
- Historical daily snapshots: 100 initially (range 10–160).
- Estimated combined API spending limit: $12 initially ($2–$50).
- Dry run: **true** initially. This verifies source coverage without any model calls or API keys. Download the resulting artifact and review coverage.json and source-cases.json. Confirm the archive covers multiple months and ranking-candidate-groups.json contains at least one same-day, distinct-source cohort. A failed dry run leaves diagnostic artifacts.
- For the real comparison, add repository Actions secrets **OPENAI_API_KEY** and **ANTHROPIC_API_KEY**, select Dry run **false**, and run the workflow again. Anthropic is used in production, but its repository secret name and availability must still be verified. Do not paste credentials in chat or commit them.

The API spending guard uses response token counts and standard list-price estimates, not guaranteed invoice-level metering. Do not infer that a ChatGPT Plus/Pro subscription covers OpenAI API usage. The workflow does not commit, publish, send newsletter emails, or start other Actions.


## API setup (required only for the paid run)

OpenAI API usage is separate from ChatGPT subscription billing. Sign in at https://platform.openai.com/; set up billing at https://platform.openai.com/settings/organization/billing/overview; create a project-scoped key at https://platform.openai.com/api-keys. Consider a dedicated project with an appropriate spending limit and no automatic prepaid recharge. On GitHub, use repository **Settings → Secrets and variables → Actions → New repository secret** and save the key as **OPENAI_API_KEY**. Verify **ANTHROPIC_API_KEY** is also available to this workflow. Never place either key in a PR, issue, artifact, or chat.

The configured provider IDs are `claude-sonnet-5` and `gpt-6.1-sol`. The script's USD estimates use standard $2/million input and $10/million output token rates, **not** a provider-enforced spending cap. Verify account eligibility and real prices before the paid run. An OpenAI or Anthropic account may impose separate credit, project, or organization limits.

## Results

The private artifact contains:
- source-cases.json: historical source evidence and canonical article references.
- coverage.json: total matched cases, months represented and snapshots inspected.
- ranking-candidate-groups.json: each contemporaneous homepage comparison set.
- writing.json and ranking.json: blind Variants A and B.
- blind-review.md: newsroom-quality paired reading and scoring sheet.
- answer-key.json: variant-to-model mapping; **do not read until blind scoring is complete**.
- usage.json: input/output tokens and estimated cost by provider.

Reviewers should score factual fidelity 30%, editorial/news judgment 25%, contextual accuracy 20%, headline/prose 15%, local relevance 10%. Fabricated quotations, incorrect incident identity, false serious allegations, or ungrounded developments are automatic failures. Structural screening is not an independent fact checker. Humans must verify assertions against source material.

This first study compares model capability under a **shared neutral prompt**. It does not replace an end-to-end production pipeline A/B test using TCT's full assignment-editor, writer, update, ranking, and identity-guard logic. Keep Claude in production until the blinded results justify further shadow testing. If no qualifying same-day ranking cohort exists, the bake-off fails before model API calls rather than incorrectly implying ranking was measured. One or very few ranking cohorts should still be regarded as limited evidence, not a conclusive ranking test.

## Safety and rollback

This workflow has only workflow_dispatch, uses contents: read, checks out without persisted credentials, stores artifacts for 30 days, and never invokes scripts/generate.py, cleanup_archive.py, or production update workflows. If no evidence is available, it fails closed. Deleting the workflow or not running it is sufficient to stop the experiment.
