# TCT v1.13.9.91 — Events live-presentation rollover fix

## Problem
The events page could keep an event with an older start date at the top of the page after the calendar day changed. This was especially visible for legitimate multi-day events: a multi-day event beginning Oct. 2 could remain the first card on Oct. 4. The server-rendered snapshot could also show events that had ended since the last scheduled events refresh because the browser did not reconcile the initial cards until a user interacted with a filter or the View more control.

## Fix
- Adds a presentation-layer effective-end calculation matching the ingestion safety rules.
- Removes elapsed events from the rendered events list.
- Orders still-live events as:
  1. events occurring today,
  2. ongoing multi-day events that began on an earlier date,
  3. future events.
- Keeps legitimate ongoing multi-day events discoverable without allowing an old start date to pin the top slot.
- Applies the same live filtering and ordering in browser JavaScript using the viewer's current Eastern date/time.
- Reconciles the page immediately on load instead of waiting for the first filter/search/View more interaction.
- Date-range filters now treat multi-day events as overlapping a range when appropriate.
- Collection JSON-LD uses the same current presentation set.
- Validation now checks the filtered presentation set and the new live-reconciliation JavaScript contract.

## Oct. 4 regression
At 3:27 PM ET on Oct. 4, the Oct. 2–6 Bible Reading Marathon remains an eligible ongoing event but no longer leads the page. The first rendered card is an Oct. 4 event, and already-ended Oct. 3 events are excluded.

## Validation
- `python -m pytest -q tests/test_events_aggregation.py tests/test_events_live_presentation_v91.py`
- Result: 60 passed, 0 failed.
- `scripts/update_events.py` compiles successfully.
- Current retained `data/events.json` was rendered under `TCT_EVENTS_NOW=2026-10-04T15:27:00-04:00`; output validation passed and the first server-rendered card is dated Oct. 4.
