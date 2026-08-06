# TCT v1.13.1.8 — Web-Upload-Safe Cumulative Recovery

This is the same cumulative v1.13.1.8 correction, repackaged for GitHub's 25 MB browser-upload limit.

## Packaging change

`data/editorial_story_registry.json` is intentionally omitted because the tracked file is approximately 28 MB. Do not delete or replace the registry already in the repository.

Both TCT workflows already run `python scripts/repair_editorial_story_registry.py` before package validation and pytest. The production workflow later commits the normalized registry together with generated output.

## Corrections retained

- Durable Ethan Boyd RSS-image validation by canonical permalink rather than mutable headline text.
- Safe false-jurisdiction retirement that cannot delete neighboring RSS or sitemap entries.
- Source-backed county-jurisdiction enforcement.
- Withdrawal of the false Indian River/Palm Beach article from public surfaces.
- Regression coverage preserving unrelated entries before and after the withdrawn article.
- Clean generation-cache and generated surface state.

## Upload limits

- Largest included file: under 3 MB.
- No included file exceeds 25 MB.
- The ZIP itself is under 5 MB.
