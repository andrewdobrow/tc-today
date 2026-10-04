# TCT v1.13.9.92 — Multi-day event card date rollover

## Problem
A legitimate multi-day event could remain visible after its first day but continue to display its original start date on the card. Even after v1.13.9.91 stopped an old-start event from pinning the top of the Events page, an Oct. 2 event viewed on Oct. 4 could still visually say Oct. 2.

## Fix
- Still-live multi-day events now roll their **displayed card date** forward to the current Treasure Coast date.
- The underlying `starts_at` and `ends_at` values are unchanged and remain authoritative for filtering, chronology and expiration.
- A rolled-forward card uses `ONGOING` as its date-box kicker so readers are not led to believe the event originally began that day.
- The context line adds the original start date, for example: `All day · Started Oct 2 · Memorial Park · Stuart`.
- The browser applies the same rollover on every page load, so the visible date advances each day even if the server-rendered Events snapshot was built the previous day.
- First-day and future events retain their normal weekday/date presentation.

## Example
A still-live event beginning Oct. 2 appears as:
- Oct. 2: normal `FRI / OCT 2`
- Oct. 3: `ONGOING / OCT 3` + `Started Oct 2`
- Oct. 4: `ONGOING / OCT 4` + `Started Oct 2`
- and so on until the event is no longer live, at which point the existing expiration logic removes it.

## Validation
- Focused Events tests include Oct. 4 and Oct. 5 daily rollover regressions.
- Server and browser presentation contracts both use the current Eastern calendar date without modifying event identity or source dates.
