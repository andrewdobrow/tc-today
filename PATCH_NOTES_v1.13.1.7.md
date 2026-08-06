# v1.13.1.7 — Image Surface Contract Alignment

## Failure corrected

`test_current_surfaces_use_selected_image` required the Ethan Boyd image URL to occur at least twice in `index.html`. That assumption became invalid after final canonical surface deduplication correctly reduced the story to one homepage placement.

## Change

The test now verifies the actual invariant:

- the retained Ethan Boyd permalink exists on the homepage; and
- that exact linked placement contains `https://treasurecoast.today/images/ethan-boyd.png`.

This is stronger than a raw occurrence count and remains valid whether the article appears as a hero or card.

## Scope

Test-only change. No generator, workflow, article, archive, image, identity, redirect, RSS, sitemap, or public-page logic is modified.
