# TCT v1.13.9.98 — MARTY factual copy correction + absence-language hard stop

## Incident
The Oct. 8 MARTY article published the sentence:

> The county did not identify the transit provider or explain why the service was canceled.

That sentence violated TCT's existing no-absence-language editorial policy and was also factually stale/incomplete by publication time. Martin County Transit, LLC had publicly identified itself as the operator withdrawing from the MARTY contract and said rising insurance, fuel and maintenance costs had made the contract financially unsustainable.

## Root cause
The writer prompt already prohibited absence language, but the deterministic post-generation guard did not cover the construction `officials/the county did not identify/explain/...`. The source article used that wording and it passed through the sanitizer.

## Production changes
- `scripts/generate.py`
  - Extends the existing deterministic absence-language cleanup to catch information-gap constructions such as `did not identify`, `did not explain`, `did not specify`, `did not disclose`, `did not clarify`, and `did not say/state whether`.
- `tct_engine/article_prose_policy.py`
  - Adds a subject-scoped official-information-gap prose guard.
  - It applies to reporting-process gaps from officials/agencies/government/company sources.
  - It deliberately does **not** remove substantive negative actions such as `The commission did not approve the proposed tax increase.`
- `data/article-content-overrides.json`
  - Surgically repairs the already-published MARTY article without regenerating or rewriting unrelated copy.
  - Replaces the prohibited sentence with:
    `Martin County Transit, LLC, the contracted operator, said it withdrew from the MARTY operating contract because rising insurance, fuel and maintenance costs had made the contract financially unsustainable.`
  - Does not change the original publication timestamp or artificially refresh ranking.
  - Stores the external verification sources in override metadata for auditability.

## Regression coverage
Permanent regression coverage is included because this patch changes production prose-policy logic, not merely content.

Validated suites: **42 passed, 0 failed**.

## Scope
No changes to deduplication, canonical identity, redirects, publication identity, membership/paywall behavior, image logic, category routing, or model selection.
