# v1.13.1.4 — Complete HTML Alias Runtime Fix

## Emergency correction

The v1.13.1.3 patch repaired `html.unescape()` but did not repair the later
`html.escape()` calls inside `_apply_article_content_overrides_to_outputs()`.
The production workflow therefore reached the end of generation and failed with
another `NameError`.

This release replaces every bare `html.*` reference in that function with the
existing `html_lib.*` alias. It also fails the preflight if any bare reference
remains, preventing another method-by-method runtime failure.

## Scope

- Replaces the source-targeted runtime patcher only.
- Preserves the registry-write batching improvement from v1.13.1.3.
- Does not replace `scripts/generate.py` with an older copy.
- Does not alter articles, archive records, custom content, images, redirects,
  registry data, or identity rules.
