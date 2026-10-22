import unittest
from datetime import datetime, timezone, timedelta
from tct_engine.top_news_app_feed import build_top_news_app_feed

NOW = datetime(2026,10,12,18,0, tzinfo=timezone.utc)

def item(slug, days_old=1, **kw):
    base = dict(slug=slug, canonical_slug=slug, canonical_publication_id=slug,
                headline=slug.replace('-', ' '), ranking_eligible=True,
                date=(NOW.date()-timedelta(days=days_old)).isoformat())
    base.update(kw)
    return base

class PublishedHomeParity(unittest.TestCase):
    def test_hero_and_top_stories_preserve_website_order(self):
        records=[item(x) for x in ['hero','top-b','top-a','more-a','more-b']]
        feed=build_top_news_app_feed(hero_slug='hero',top_story_slugs=['top-b','top-a'],
            homepage_other_slugs=['more-b','more-a'],archive=records,now=NOW)
        self.assertEqual(feed['hero']['slug'],'hero')
        self.assertEqual([r['slug'] for r in feed['top_stories']],['top-b','top-a'])
        self.assertEqual([r['slug'] for r in feed['more_news']][:2],['more-b','more-a'])

    def test_quiet_weekend_supplements_from_seven_day_archive_not_top(self):
        records=[item('hero'),item('top-1'),item('top-2'),item('top-3')]+[
            item(f'archive-{k}',days_old=(k%6)+1) for k in range(40)]
        feed=build_top_news_app_feed(hero_slug='hero',top_story_slugs=['top-1','top-2','top-3'],
            homepage_other_slugs=[],archive=records,now=NOW)
        self.assertEqual(len(feed['top_stories']),3)
        self.assertGreaterEqual(len(feed['more_news']),16)
        self.assertEqual(len(feed['more_news'])+len(feed['top_stories'])+1,20)
        self.assertEqual(feed['hero']['slug'],'hero')

    def test_retired_redirected_duplicates_and_stale_alerts_excluded(self):
        records=[item('hero'),item('top'),item('ok'),
                 item('retired',ranking_eligible=False),
                 item('alias',canonical_slug='another'),
                 item('old-stale',days_old=9),
                 item('flash-flood-warning-hits-martin',days_old=1),
                 item('same-story',canonical_publication_id='ok')]
        feed=build_top_news_app_feed(hero_slug='hero',top_story_slugs=['top'],
             homepage_other_slugs=['retired','alias','old-stale','flash-flood-warning-hits-martin','ok','same-story'],
             archive=records,now=NOW)
        self.assertEqual([r['slug'] for r in feed['more_news']],['ok'])

    def test_missing_homepage_slug_provides_useful_diagnostics(self):
        with self.assertRaisesRegex(ValueError, "absent from archive.json"):
            build_top_news_app_feed(hero_slug='new-but-never-archived',
                                    top_story_slugs=[], homepage_other_slugs=[],
                                    archive=[item('real-canonical-story')], now=NOW)

    def test_present_but_ineligible_hero_gives_explicit_reason(self):
        with self.assertRaisesRegex(ValueError, "ranking_eligible=False"):
            build_top_news_app_feed(hero_slug='real-story',
                                    top_story_slugs=[], homepage_other_slugs=[],
                                    archive=[item('real-story', ranking_eligible=False)], now=NOW)

    def test_redirect_alias_hero_fails_closed_with_canonical_diagnostic(self):
        with self.assertRaisesRegex(ValueError, "different canonical slug"):
            build_top_news_app_feed(hero_slug='old-story',
                                    top_story_slugs=[], homepage_other_slugs=[],
                                    archive=[item('old-story', canonical_slug='real-story')], now=NOW)

    def test_no_unpublished_hero_fallback(self):
        with self.assertRaises(ValueError):
            build_top_news_app_feed(hero_slug='ghost',top_story_slugs=['top'],
                                   homepage_other_slugs=[],archive=[item('top')],now=NOW)

if __name__ == '__main__': unittest.main()
