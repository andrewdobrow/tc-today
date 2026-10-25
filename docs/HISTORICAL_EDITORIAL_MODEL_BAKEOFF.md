# Historical editorial model bake-off — TCT

## Why this exists

Test **editorial quality first** between the existing Claude Sonnet 5 and OpenAI GPT-6.1 Sol without waiting for fresh Sunday reporting and without touching the production newsroom, site, archive, editorial sorting, or notifications. The workflow is manual-only and has read-only repository permissions. All experiment results are private GitHub Actions artifacts, not repository commits.

## Corpus construction

1. Check out full Git history.
2. Inspect one historical revision of the existing data/generation-cache.json per day, up to the requested historical depth. Read *source_text* snapshots already retained at the time; do not scrape current live article pages.
3. Link original source URLs to **already-published canonical** entries in archive.json. Require an exact normalized source-URL match, a substantial archived source excerpt, and a source capture within one day before through two days after the original published date. Exclude custom, sponsored, and unresolved-identity items.
4. Stratify article examples across months and sections rather than selecting only recent or sensational stories. The previously published TCT headline is held back for human evaluation and **not** supplied to either writing model.
5. For homepage ranking, independently collect groups of at least three source-supported stories that were published on the **same historical day**. No artificial comparison of a June news event with one in October.
6. Fail rather than fabricating evidence or falling back to TCT's final article text if fewer than 12 trustworthy cases are available.

The result is a replay benchmark, not proof that the archived source text was exhaustive or that the originally published TCT story was correct. Some excerpt caches may be incomplete; score unsupported claims and quote accuracy particularly carefully. Direct competitor attributions in article prose violate TCT style.

## Running it

After the pull request is reviewed and merged, open **Actions → Historical Editorial Model Bake-Off → Run workflow**.

- Article count: 30 initially (range 12–50).
- Historical daily snapshots: 100 initially (range 10–160).
- Estimated combined API spending limit: $12 initially ($2–$50).
- Dry run: **true** initially. This verifies source coverage without any model calls or API keys. Download the resulting artifact and review coverage.json and source-cases.json. Confirm the archive covers multiple months and ranking-candidate-groups.json contains same-day cohorts.
- For the real comparison, add repository Actions secrets **OPENAI_API_KEY** and **ANTHROPIC_API_KEY**, select Dry run **false**, and run the workflow again. Anthropic is already used in production, but the OpenAI secret may still need to be configured.

The API spending guard uses response token counts and standard list-price estimates, not guaranteed invoice-level metering. Do not infer that a ChatGPT Plus/Pro subscription covers OpenAI API usage. The workflow does not commit, publish, send newsletter emails, or start other Actions.

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

This first study compares model capability under a **shared neutral prompt**. It does not replace an end-to-end production pipeline A/B test using TCT's full assignment-editor, writer, update, ranking, and identity-guard logic. Keep Claude in production until the blinded results justify further shadow testing. A low number of eligible same-day ranking cohorts means homepage ordering remains inconclusive.

## Safety and rollback

This workflow has only workflow_dispatch, uses contents: read, checks out without persisted credentials, stores artifacts for 30 days, and never invokes scripts/generate.py, cleanup_archive.py, or production update workflows. If no evidence is available, it fails closed. Deleting the workflow or not running it is sufficient to stop the experiment.
