#!/usr/bin/env python3
"""One-time, non-destructive integration with TCT's current website generator.

Run from the WEBSITE repository root after extracting this overlay. It edits
only scripts/generate.py, inserting one block at a stable section boundary.
The integration intentionally does not overwrite your live editorial engine.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
source = ROOT / 'scripts' / 'generate.py'
if not source.is_file():
    raise SystemExit('ERROR: extract the overlay at the TCT WEBSITE repo root (scripts/generate.py missing)')
if not (ROOT / 'tct_engine/top_news_app_feed.py').is_file():
    raise SystemExit('ERROR: missing tct_engine/top_news_app_feed.py from overlay')

text = source.read_text(encoding='utf-8')
marker = '    # -- OLDER: per-category archived stories no longer shown as current cards --'
sentinel = '    # Native Top News follows the FINAL homepage hero + visible Top Stories,'
if sentinel in text:
    print('iOS top-news publisher already present; nothing to change.')
else:
    if text.count(marker) != 1 or 'def render_index(all_categories, top_cat):' not in text:
        raise SystemExit('ERROR: unexpected generator layout. No changes made; review updated main before patching.')
    insertion = '''    # Native Top News follows the FINAL homepage hero + visible Top Stories,
    # never the shadow ranker or a newest-first archive fallback. Below that,
    # recent eligible archive stories fill the quieter days in a separate section.
    from tct_engine.top_news_app_feed import write_top_news_app_feed, slug_from_url
    _native_top_feed = write_top_news_app_feed(
        OUTPUT_DIR,
        hero_slug=slug_from_url(_hero_permalink),
        top_story_slugs=[slug_from_url(card_permalink(c)) for c in topnews],
        homepage_other_slugs=[slug_from_url(card_permalink(c)) for c in all_cards_display],
        archive=archive_for_links,
        is_publishable=_archive_entry_publishable,
    )
    print(
        "  iOS Top News: homepage hero + "
        f"{len(_native_top_feed['top_stories'])} Top Stories; "
        f"{len(_native_top_feed['more_news'])} supplemental recent stories"
    )

'''
    updated = text.replace(marker, insertion + marker)
    compile(updated, str(source), 'exec')
    source.write_text(updated, encoding='utf-8')
    print('Integrated data/top-news-app-feed.json export into scripts/generate.py')
