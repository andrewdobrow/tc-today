# TCT v1.13.7.0c — Registry + Material Update Integrity

This overlay **supersedes v1.13.7.0b**. Apply 0c directly over the post-0a/current repository; a separate 0b application is not required.

## 1. Registry fixed-point repair (carried forward from 0b)

- Keeps the 16-pass convergence ceiling unchanged.
- Timeline-coherence splits create durable negative identity evidence.
- Weaker whole-record identity matching cannot immediately glue freshly split, incompatible incidents back together.
- Backward-compatible with historical timeline split metadata.

## 2. Waste Pro material-update novelty regression

Production evidence showed the semantic publication gate correctly selecting `update_existing_canonical` at 0.95 confidence for the Port St. Lucie Waste Pro settlement, and the material-update composer produced a valid contextual article. A second, older deterministic lead validator then rejected it as `new_development_missing` because it looked for literal source-headline wording such as `notice`/`mail` while the article accurately paraphrased that development as `flyers in their mailboxes` and stated stronger quantified facts.

0c changes the second deterministic contract so a semantic material update validates novelty against the semantic gate's explicit `novel_facts`, not merely source-headline token differences. It also preserves comma-formatted numeric facts (`95,000`, `$364`, etc.) as meaningful update tokens.

The guard remains fail-closed: the replacement lead still must contain original-event context, a real new-development fact, and sufficient lead length.

## 3. Custom canonical update authority audit

The old custom protection rule was still present. Its original purpose was correct: an unverified external feed copy must never overwrite a manually authored custom article or mint a parallel permalink.

However, `_authorized_custom_material_update()` recognized only the pre-generation material-update promotion path. A valid material update discovered at the late published-story write barrier could pass semantic materiality, composition, and canonical-write authorization and still be dropped by the old custom protection.

0c narrows that rule:

- The **custom permalink remains authoritative and immutable**.
- Unverified feed copies are still dropped.
- A custom article's text is **not frozen forever**.
- A feed source may update the existing custom page only after target-bound identity, semantic materiality, composition, and canonical-write authorization succeed.
- Both pre-generation and late write-barrier material-update paths are recognized.

The existing custom-submission contract remains unchanged: a newly submitted custom payload does not fuzzy-reuse another custom permalink merely because its headline is similar.

## Regression coverage

- Exact Aug. 31 Waste Pro `new_development_missing` class.
- Semantic novel facts survive accurate paraphrasing in a contextual lead.
- Quantified developments such as `95,000` remain visible to deterministic novelty validation.
- Late validated material updates may refresh a custom canonical in place.
- Unverified external rewrites still cannot modify custom canonicals.
- Registry split/merge oscillation regressions from 0b remain included.

## Validation

- `python scripts/validate_package.py`: 38 modules / 122 public exports verified.
- CI-equivalent pytest command: **1,057 passed / 0 failed**.
- 44 existing datetime deprecation warnings.
