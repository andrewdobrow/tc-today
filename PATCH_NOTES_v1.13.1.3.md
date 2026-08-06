# v1.13.1.3 — Generator HTML Alias and Registry Write Batching Hotfix

## Production failure repaired

The August 6 production run reached the final output stage and then failed in
`_apply_article_content_overrides_to_outputs()` because the generator imports the
standard-library HTML module as `html_lib` but the new override code called
`html.unescape()`.

The hotfix rewrites only that invalid reference to `html_lib.unescape()` and
compiles the resulting generator before it can run.

## Runtime regression repaired

The editorial audit was writing the multi-megabyte persistent story registry once
for nearly every feed candidate. As the registry grew, those writes became about
1.5 seconds apiece and added several minutes to each production cycle.

The hotfix wraps each category's audit candidates in the registry's existing
atomic deferred-save context. Decisions remain sequential and deterministic, but
all registry mutations for the category are persisted in one write instead of one
write per candidate.

## Safe application model

This overlay does not replace `scripts/generate.py`. The included idempotent patcher
edits the repository's current generator, preserving newer article, image, custom
content, and identity changes. Both workflows run the patcher before importing the
generator.

The successful production workflow will commit the patched generator normally.
