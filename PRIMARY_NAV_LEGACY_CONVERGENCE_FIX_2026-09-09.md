# Primary Navigation Legacy Convergence Fix — 2026-09-09

This patch hardens the retained-page primary navigation/masthead migration after a production run failed on a small set of June article pages.

## Changes

- Scope masthead replacement to `header.site-masthead` when present.
- For legacy plain `<header>` wrappers, replace only the header that actually owns the matched primary navigation, never an unrelated page/article hero header.
- If a very old primary nav exists outside a header, replace it with the complete canonical masthead in one pass.
- Validate navigation and masthead tokens inside the canonical site masthead rather than against unrelated page-body headers/navs.
- Remove all retained `newsroom-strip` utility bars, not only the first copy.
- Stop the article shell repair from re-injecting the obsolete `newsroom-strip`; time and weather already live in the canonical masthead.
- Treat `site-masthead` as the modern article shell marker so already-modern retained articles can be skipped rather than rewritten on every run.

## Validation

- `tests/test_events_aggregation.py`: 49 passed.
- Production-sized static corpus: 939 masthead-bearing pages converged on first pass; second pass updated 0 pages.
- `scripts/generate.py` compiles successfully.
