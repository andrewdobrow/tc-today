# Rolling Source URL Identity Review Guide — v1.12.0.8.2

## Expected startup and completion

The existing quarantined-story denylist should still load at startup. The production run must complete with:

- `persistent-story-identity-integrity.json` → `passed: true`
- `active_contaminated_count: 0`
- `violation_count: 0`
- `event-identity-authority.json` → no unauthorized destructive writes

## Production regression to inspect

The WPBF rolling weather URL formerly attached a new showers/thunderstorms forecast to `story_001574`, whose persisted title was a Palm Beach County heat advisory. After this release:

- `story_001574` must retain only its original heat-advisory identity;
- the newer forecast must not receive `story_001574` through exact source identity;
- no source-ledger key may authorize an overwrite from that rolling URL;
- the integrity gate must not report `active_contaminated_story=story_001574`.

## Allowed exact-source behavior

A normal one-off article URL remains authoritative. A rolling URL is accepted only when the incoming headline has event-level continuity with the persisted story. Minor headline evolution is allowed; a materially different weather event is not.

## Reports to review

1. `data/persistent-story-identity-integrity.json`
2. `data/cross-source-update-identity.json`
3. `data/editorial_story_registry.json`
4. Complete workflow log

Search the registry for `story_001574` and confirm that unrelated forecast titles or event keys were not appended.
