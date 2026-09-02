# v1.13.7.1o — Membership Regression Expectation Alignment

## Problem
The production membership copy was correctly changed from the obsolete "Completely ad-free" promise to "Supports local journalism", but one Test Editorial Engine checkout retained the old assertion in `tests/test_membership_ui_dark_launch.py`. That made the test suite fail even though the rendered membership card was correct.

## Fix
Updates only the stale regression expectation:
- requires `Supports local journalism`
- explicitly requires that `ad-free` is absent from the membership card

No production code, paywall behavior, pricing, Mediavine integration, registry logic, or article generation logic is changed.

## Validation
- `python -m pytest tests/test_membership_ui_dark_launch.py -q` -> 2 passed
- `python -m pytest tests -q --ignore=tests/test_canonical_identity.py --ignore=tests/test_matcher_contract.py` -> 1100 passed, 0 failed
- `python scripts/validate_package.py` -> 38 modules imported, 122 public exports verified
