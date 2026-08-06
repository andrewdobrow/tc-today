# Review Guide — v1.13.1.6

## Apply

Extract the overlay at the repository root, replacing matching files. Commit and push, then run **Test Editorial Engine** followed by **Update Treasure Coast Today**.

## Expected preflight output

- `False-jurisdiction generator hotfix: ... verified=true`
- `False-jurisdiction publication repair: {...}`
- Reader-support preflight reports 50 checked.
- Package validation passes.
- Pytest passes.

## Production acceptance

1. The withdrawn URL redirects to `/indian-river/` and contains `noindex`.
2. The bad slug is absent from `archive.json`, `data.json`, RSS, both sitemaps, and visible homepage/category links.
3. An Indian River source pool with zero deterministic county hero candidates uses archive recovery without a Claude call.
4. A source that says Palm Beach County cannot authorize an Indian River headline, lead, card, hero, permalink, or cache reuse.
5. A source that genuinely names Indian River County, Vero Beach, Sebastian, Fellsmere, Wabasso, Gifford, or Orchid remains eligible.
6. The Ethan Boyd article and `ethan-boyd.png` override remain unchanged.
