# TCT v1.12.2.6 — Semantic Policy-Subject Recall

## Problem

The semantic final publication gate correctly adjudicated duplicate candidates once they reached Claude, but candidate retrieval still missed public-policy stories whose publishers used different regulatory vocabulary.

The production example was the Martin County shark-fishing proceeding:

- `2026-07-29-martin-county-commissioners-move-to-rewrite-shark-fishing-rules-after-public-bea`
- `2026-08-01-martin-county-reviews-shark-fishing-ordinance-after-state-says-local-rules-must`

The headlines described the same regulated subject but alternated among **rules**, **laws**, and **ordinance**, and among **rewrite**, **change**, and **review**. Their publisher-generated event keys conflicted, while the raw shared-token count remained below the existing conflict-override thresholds. Claude therefore never saw the pair.

A July 30 shark-fishing article represented the same recall gap and is covered by the same regression.

## Change

The final-gate retriever now:

- normalizes `rule`, `law`, and `ordinance` to the shared `regulation` concept;
- normalizes `rewrite`, `review`, `change`, and related forms to `revise`;
- normalizes commissioner variants and common fishing forms;
- records the headline basis, all shared canonical headline tokens, and shared topical tokens;
- adds a conservative `policy_subject_continuity` conflict-override tier.

That tier requires all of the following:

- the stories remain within the seven-day bounded window;
- shared locality and a shared public-policy/government/regulation event family;
- headline similarity of at least `0.56`;
- at least six shared canonical headline tokens;
- the shared `regulation` concept;
- at least two additional shared subject tokens after generic locality/government/action words are removed.

The tier only nominates the pair for Claude. It does not merge, redirect, or update a story without the existing structured Claude adjudication and confidence contract.

## Safety

A regression verifies that a Martin County noise-ordinance article does not become a candidate for the shark-fishing story merely because both concern county rules.
