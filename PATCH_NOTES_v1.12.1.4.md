# TCT v1.12.1.4 — Newsletter Responsive Presentation

## Summary

This release separates newsletter acquisition by viewport:

- Desktop loads Kit sticky bar `4edef44197`.
- Mobile loads Kit modal `be625cadfe`.
- Mobile never reserves masthead space for the desktop sticky form.
- Existing inline form `30e15672d3` remains unchanged on article and category pages.

## Production correction

The prior compact-sticky implementation still competed with the TCT mobile masthead. Even when the sticky wrapper was promoted above the header, the available mobile height made the result intrusive and fragile.

The shared footer no longer hard-codes a Kit presentation script. `main.js` selects and injects exactly one presentation based on the 680px breakpoint. Crossing that breakpoint reloads the page so Kit can initialize from a clean state.

## Safety behavior

Mobile CSS suppresses any stale sticky wrapper that may survive in an older generated page or cached Kit response. It also clears the sticky body/header offset and constrains the modal to the viewport with internal scrolling.
