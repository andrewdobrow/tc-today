# v1.12.0.8.2 — Rolling Source URL Identity Guard

## Production failure addressed

A publisher-backed Google News URL was reused for two materially different WPBF weather headlines:

- `Heat advisory in effect for metro and coastal Palm Beach County Friday`
- `Tracking showers and thunderstorms with triple digit feels-like temps across South Florida`

The persistent registry treated exact URL equality as definitive event identity, attached a second sparse event to `story_001574`, and correctly failed the final integrity contract with `active_contaminated_story=story_001574`.

## Root cause

An article URL is normally a strong source identity, but weather, forecast, traffic, live-blog, radar, and similar pages may be rolling content slots. The same URL can represent a different real-world event after the publisher updates the page. Exact URL equality therefore cannot independently authorize a persistent-story merge or canonical overwrite for a rolling source.

## Changes

- Adds rolling-source detection for weather/forecast/radar/live/traffic paths and weather-signaled Google News items.
- Requires event-level title continuity before a rolling URL can join an existing persistent story.
- Keeps compatible evolving headlines together when they retain at least two specific shared concepts and meaningful proportional overlap.
- Creates a new story when a reused rolling URL changes subject materially.
- Prevents rolling URLs from becoming canonical publication-ledger keys.
- Requires title continuity before exact rolling-source identity may select, preserve, reconcile, or overwrite an archive page.
- Prevents registry repair from re-merging two incompatible stories solely because they share a rolling URL.
- Keeps ordinary one-off publisher and Google News article URLs authoritative when they do not carry rolling-content signals.

## Safety behavior

When a rolling URL changes identity, the engine fails closed toward separation:

- no existing story enrichment;
- no inherited persistent story ID;
- no canonical write authorization;
- no existing permalink overwrite;
- a new event/story may be created if otherwise eligible.
