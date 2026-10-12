# TCT homepage-to-iOS Top News authority

**Deploy website FIRST, then iOS.** If the app installs before the website has published its new endpoint, the app intentionally will NOT invent a hero from the newest archive entries. It will display a retry message (or previously verified in-memory feed) until the endpoint exists.

## Website steps

1. Extract `TCT_Website_Top_News_Feed_Overlay.zip` at the current **website repository root**, retaining paths. It adds `tct_engine/top_news_app_feed.py`, `tests/test_top_news_app_feed.py`, and `APPLY_TOP_NEWS_APP_FEED.py`; it does not replace your current `scripts/generate.py` or emergency-warning safety work.
2. Run `python APPLY_TOP_NEWS_APP_FEED.py` once from the repository root. This makes one idempotent edit to your current `scripts/generate.py`.
3. Run `python -m unittest discover -s tests -p 'test_top_news_app_feed.py'` and your normal **Test Editorial Engine** workflow. (The latter is the authoritative production regression gate.)
4. Run **Update Treasure Coast Today** to publish the feed. Confirm `https://treasurecoast.today/data/top-news-app-feed.json` serves `200` and includes `schema_version:1`, `hero`, `top_stories`, and `more_news`.
5. Confirm `hero.slug` corresponds to the link in the homepage's visible lead hero, and `top_stories` matches the order of the website's visible Top Stories. Do not deploy the app until this matches.

### What it publishes

- `hero`: EXACT homepage lead-story slug.
- `top_stories`: EXACT ordered selected homepage Top Stories deck, excluding the hero and duplicates.
- `more_news`: supplemental homepage cards plus recent eligible canonical archive stories, at most 7 calendar days old, aiming for 20 total cards and capped at 24. The seven-day limit deliberately avoids stale backfill on slow news days. It excludes retired/redirected entries, publication duplicates, and headlines about current emergency warnings.
- It uses only public archive slugs and metadata; no protected article bodies or secrets.

If the current hero is not canonical/publishable, the site generation stops instead of distributing a different app hero.

## iOS steps

1. AFTER production has the new JSON, extract the separate `TCT_iOS_Homepage_Top_News_Parity_Overlay.zip` into your latest `tct-ios` checkout.
2. Run the iOS Python suite and **iPhone Ad Hoc (signed, manual)** workflow.
3. Verify site and app have the identical lead story and Top Stories sequence. On quiet days the app shows `More Local News` below that deck rather than elevating archived stories into the hero slot.
4. With the feed unavailable, pull to refresh: the app must retain only a previously verified editorial sequence (if present) and show an error, never switch to newest-first.

Both packages were prepared from October 12 uploaded snapshots. Preserve any newer production fixes by comparing changed iOS source files with your live branch before applying. No changes to payment, paywall, advertising, signing or editorial selection logic are included.
