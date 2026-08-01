# TCT v1.12.1.2 — Newsletter Layout and Sticky-Bar Containment

## Summary

This release corrects the first production presentation of Kit newsletter forms.

## Changes

- Groups the active category hero and inline newsletter form in one left-column `lead-stack`.
- Extends the Latest News rail beside the combined hero and newsletter height on desktop.
- Preserves the single-column hero, newsletter, then Latest News order on mobile.
- Raises Kit's sticky-bar wrapper above the TCT masthead.
- Dynamically reserves the sticky bar's rendered height so it cannot cover the site header.
- Limits the sticky bar to 72px on desktop and 58px on mobile.
- Reduces the mobile sticky presentation to an email field and compact subscribe button.
- Keeps the article reading-progress indicator below the visible sticky bar.

## Compatibility

The Kit UIDs remain unchanged:

- Sticky bar: `4edef44197`
- Inline form: `30e15672d3`
