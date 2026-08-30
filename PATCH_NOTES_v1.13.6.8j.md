# v1.13.6.8j — Editorial Audit Retention Hotfix

## Problem
`data/editorial_audit.jsonl` is an append-only diagnostic log. It had no retention policy and eventually crossed the production workflow's 90 MiB generated-repository safety ceiling.

## Fix
- Added `scripts/compact_editorial_audit.py`.
- Retention triggers at 64 MiB and atomically keeps the newest ~48 MiB of complete JSONL rows.
- Surviving audit rows are copied byte-for-byte; no JSON records are rewritten.
- `scripts/generate.py` applies retention immediately after appending each run's audit rows.
- The production workflow also performs the same compaction before package validation/tests, so an already-large tracked audit is bounded before generation begins.
- The existing 90 MiB repository guard remains unchanged.

## Authority / data safety
`editorial_audit.jsonl` is diagnostic history only. Editorial state and publication identity remain in their existing authoritative state/registry artifacts. This hotfix removes only the oldest diagnostic audit rows.

## Real-file validation
On the current 86.94 MiB audit snapshot:
- before: 91,162,927 bytes / 46,230 rows
- after: 50,328,764 bytes / 24,464 rows
- reclaimed: 40,834,163 bytes
- oldest retained timestamp: 2026-08-06T06:56:29Z
- newest retained timestamp: 2026-08-28T21:21:27Z

## Validation
- `python scripts/validate_package.py`: PASS — 38 modules / 122 exports
- production-equivalent pytest suite: 1,032 passed / 0 failed / 41 existing warnings
