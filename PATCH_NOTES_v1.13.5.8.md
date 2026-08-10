# TCT v1.13.5.8 — Manual article update/paywall idempotence repair

This increment fixes the repeated **Original report** corruption on the Ethan Boyd
missing-child resolution article and closes the underlying generator/paywall bug so
a manual article content override cannot grow another copy on every production run.

## Root cause

`_apply_article_content_overrides_to_outputs()` still treated an article body as a
single flat `<div class="article-body">...</div>` and replaced it with a non-greedy
regular expression. After the membership launch, retained article pages contain a
nested preview/paywall/protected-content structure. The old expression stopped at
the first nested `</div>`, left the remainder of the prior article shell behind, and
then appended another `Original report` block on the next run.

The accumulated stray `</div>` elements also closed the editorial grid early, which
caused the article side rail to disappear in the browser.

A second related parser in `prepare_membership_paywall.py` had the same flat-body
assumption. A manual update containing the nested `.article-update` block could be
truncated before the original report when the protected membership payload was
rebuilt.

## What changes

- Manual content overrides now replace the **entire article-content region** and stop
  only at the stable newsletter/share boundary.
- The replacement is idempotent: rerunning the production generator replaces the
  same region instead of appending another update/original block.
- Membership paywall preparation now extracts a full article body through the same
  stable newsletter/share boundary, preserving nested update markup and the complete
  original report in the protected full-body payload.
- The already-generated Ethan Boyd article is repaired in this overlay:
  - one bounded public teaser
  - one paywall
  - one protected-content slot
  - one newsletter block
  - one share block
  - one article side rail
  - no repeated public full-body copies
- The existing `data/article-content-overrides.json` remains the editorial authority
  for the resolved headline, update text, image and original report.

## Protected-content recovery

The repaired public HTML contains only the bounded membership teaser. On the next
normal production run, the generator reconstructs the authoritative manual article
body, the fixed membership preparer exports the complete body outside the public
repo, and the normal protected-article sync overwrites the protected store with the
complete update + original report.

## Not changed

- Stripe/Supabase entitlement rules
- paywall pricing or teaser character budget
- member no-flash behavior from v1.13.5.7
- story identity, duplicate matching or Top Stories ranking
- the authoritative Ethan Boyd content override itself

## Validation

- Focused regression suite: **25 passed**
- Package validation: **35 modules / 119 public exports**
- generator runtime hotfix check: passed
- false-jurisdiction generator guard check: passed
- Python compile checks: passed
- Python 3.11 grammar parse for changed Python files: passed
- repaired article structural check: exactly one paywall, protected slot, newsletter,
  share block and side rail; no repeated hidden full-detail paragraph in public HTML

The full workflow-equivalent pytest suite was not rerun in this local container
because its package index cannot install the workflow-only `feedparser`, `anthropic`
and `json-repair` dependencies. The production/Test Editorial Engine workflow should
remain the final Python 3.11 integration gate after applying this overlay.

### Corrupted-page reproduction

The pre-fix repository copy containing **17** `Original report` blocks was run
through the fixed override + membership preparation path in an isolated scratch
site. The result contained one public paywall, one side rail, one bounded public
`Original report` occurrence, and one complete protected `Original report` body.
The hidden physical-description paragraph was present in the protected export and
absent from public HTML.
