# v1.13.6.7n Production Review Guide

After applying v1.13.6.7n, run Test Editorial Engine and then one normal production run.

## Required production evidence

Look in `data/semantic-publication-gate.json` for decisions with:

`"phase": "terminal_permalink_authority"`

For every ordinary generated story that would otherwise create a new URL, there should be a terminal decision.

Expected log messages:

- `TERMINAL PERMALINK DUPLICATE LOCK` — same event, no new URL.
- `TERMINAL PERMALINK UPDATE ROUTE` — material development refreshed canonical.
- `TERMINAL PERMALINK HOLD` — ambiguous/model failure; no URL.
- New URL creation is allowed only after the terminal report records `new_story`.

## Immediate cleanup checks

After the run, the following should no longer remain independent archive/live stories:

- Aug. 26 resident-takes-cover tornado article.
- Aug. 26 residents-clean-up tornado article.
- Aug. 26 `to-consider` trash-fee permalink.

They should resolve through canonical redirects to the retained tornado/trash canonicals.

## Date check

A new article generated after 8 p.m. Eastern should carry the current **Eastern** calendar date in its slug, not the next UTC date.

## Fail-closed invariant

Any ordinary create-path item without `_terminal_permalink_new_authorized` must log:

`TERMINAL PERMALINK WRITE BARRIER`

and must not create an article page.
