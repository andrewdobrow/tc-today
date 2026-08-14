# TCT v1.13.6.1a — Exact-headline archive reconciliation runtime hotfix

## Scope

Tiny production hotfix on top of v1.13.6.1. No editorial matching policy changes.

## Root cause

`_exact_headline_incident_evidence()` emitted a decision-trace field named
`shared_specific_topic_core`, but `specific_topic_core` is local to the separate
late-reprint evidence function. When exact-headline archive reconciliation reached
that trace, production raised `NameError` and stopped before archive writing.

## Fix

- Remove the stray foreign-scope diagnostic line.
- Preserve every existing exact-headline identity input, threshold, authorization
  rule, and decision outcome.
- Add a runtime regression that executes the full decision-trace path and proves
  the function cannot reference that undefined symbol again.
