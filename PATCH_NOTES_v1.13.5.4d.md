# TCT v1.13.5.4d — CI Launch-State Isolation Hotfix

Incremental overlay for repositories that already have v1.13.5.4c applied.

## Fix
- Removes `TCT_MEMBERSHIP_UI_ENABLED` repository-variable inheritance from the **Test Editorial Engine** job.
- Keeps editorial CI deterministic and independent of the live reader-facing launch switch.
- Launch-state banner behavior remains tested explicitly with a synthetic `MEMBERSHIP_UI_ENABLED=True` test.
- Updates the workflow regression so only the production workflow is required to inherit the live membership switch.

## Why
v1.13.5.4c incorrectly exposed the live membership variable to the entire pytest process. When the repository variable was `true`, legacy reader-support unit tests loaded `scripts.generate` in launch mode and correctly returned no banners, causing six unrelated pre-launch banner-contract tests to fail.

## Validation
- `tests/test_reader_support_banner.py`: 12 passed.
- Membership + launch + shark provenance + workflow + reader-support focused suite: 57 passed.
- `scripts/validate_package.py`: 35 modules / 119 public exports passed.
- Python 3.11 grammar parse: passed.
