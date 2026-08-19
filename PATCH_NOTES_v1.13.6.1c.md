# v1.13.6.1c — Editorial engine test clock hotfix

## Scope
Test-only hotfix. No production/editorial behavior changes.

## Failure
`tests/test_editorial_engine.py` used a fixed `DEFAULT_TIME` of 2026-07-20. Once the real clock passed the story lifecycle's 30-day archival threshold, the first synthetic cat-rescue story became `archived`. The relationship classifier intentionally skips archived stories, so the subsequent arrest update was reported as `same_event` instead of the test's expected `follow_up`.

This caused exactly two failures:
- `test_custom_tct_story_replaces_external_canonical`
- `test_external_story_with_new_fact_updates_custom_story`

## Fix
The engine-routing test fixture now sets `DEFAULT_TIME` from the current UTC time at test-module load (microseconds stripped). These tests are intended to exercise canonical replacement/update and relationship behavior, not lifecycle aging.

The 30-day archival threshold and the production rule that archived stories are skipped by the follow-up relationship classifier are unchanged.

## Validation
- `tests/test_editorial_engine.py`: 8 passed
- `tests/test_editorial_engine.py tests/test_story_lifecycle.py tests/test_story_relationships.py`: 21 passed
