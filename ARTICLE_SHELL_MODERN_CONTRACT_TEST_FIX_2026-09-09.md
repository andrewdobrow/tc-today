# Article shell modern-contract regression test fix — 2026-09-09

This patch updates the article shell performance regression test to match the
current masthead contract introduced by the primary-navigation convergence fix.

- `site-masthead` is the canonical modern masthead marker.
- `newsroom-strip` is legacy and must not qualify a page as modern.
- The modern-shell test now uses the current masthead marker and verifies the
  legacy repair pass leaves a current article untouched.
- A second regression test verifies an obsolete newsroom-strip shell is not
  incorrectly skipped as modern.

No production article-generation behavior was relaxed by this patch.
