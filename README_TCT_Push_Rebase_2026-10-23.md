# TCT October 23 — Generated Update Push/Rebase Hardening

## Files in this root-path overlay

- `scripts/push_generated_update.sh` — replaces the current push/rebase helper.
- `tests/test_generated_update_rebase_conflicts_oct23.py` — adds regression tests using local temporary Git repositories.

No generator, archive, article, paywall, event, config, workflow or editorial override files are included.

## Why

Update workflow #1364 started from commit `44d662f` while a previous
bot-generated commit `4f4c453` landed on `main` during its execution.
The script can deliberately exit 2 when a Git rebase conflict is not recognized
as generated. The provided truncated log does not show the precise conflicted
path(s), so this is a highly plausible failure mode, not a fully confirmed
forensic diagnosis.

The original allowlist omits genuine generated paths such as `feed.xml`,
`archive.html`, `story-registry.json`, and numerous output contracts shown in
the failed run/previous bot commit. This overlay adds those known output paths.
It also fixes a modify/delete rebase conflict when the bot intentionally
removed a generated file and Git has no `--theirs` blob to check out.

## Safeguards

1. Editorial hand-maintained content remains outside the allowlist:
   `data/article-content-overrides.json`, `data/custom_articles.json`,
   `data/manual_events.json`, `data/article-image-overrides.json`.
2. Any conflict on code, workflow, unknown config or editor-owned data fails
   closed, aborts rebase, and leaves remote `main` untouched.
3. Conflicts are classified before any automatic resolution is staged.
4. Other human commits are retained when rebasing generated artifacts.
5. No changes are made to `scripts/generate.py` or its editorial safeguards.

## Validation performed locally

- `bash -n scripts/push_generated_update.sh`: passed.
- 59+ direct tests in new suite and 6 existing bounded-working-set tests:
  **65 passed**, including actual local-Git rebase integration tests.
- Earlier baseline/relevance selection of hero, chronology, source facts,
  membership/article correction and publisher tests: **124 passed** before the
  final allowlist expansion. The later expansion is limited to the push helper.
- The complete suite was attempted but did not finish within the available
  execution time. Production GitHub Tests (Python 3.11) remain authoritative.

## Deployment

Extract this ZIP into the **root of the newest local `tc-today` repository**,
replace `scripts/push_generated_update.sh`, add the test file, commit and push.
Run **Test Editorial Engine first**, then **Update Treasure Coast Today**.
A workflow already running when the fix is pushed will still use its old code.

## Scope distinction

The Oct. 9 hit-and-run article now contains the name under an explicit
verified editorial override. That is a separate fix and is NOT included
in this overlay. The root cause of missing future material updates is not
proven resolved by this push/rebase change.
