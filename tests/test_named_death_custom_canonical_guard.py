"""Named-death custom canonicals must survive a change in story angle."""
import importlib
import json
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path

from tct_engine.custom_named_death_identity import same_named_death_as_custom

ORIGINAL = '2026-10-24-st-lucie-county-firefighter-paramedic-austin-hodge-dies-in-line-of-duty'
DUPLICATE = '2026-10-24-st-lucie-fire-district-mourns-second-hodge-brother-in-a-year'
ORIGINAL_IMAGE = 'https://images.treasurecoast.today/articles/1f/1f251033eb69a787817d92d69c72b17fd19d387421401002ec9ed34b5d0decc6.jpg'


def original():
    return {
        'slug': ORIGINAL,
        'headline': 'St. Lucie County Firefighter-Paramedic Austin Hodge Dies in Line of Duty',
        'teaser': 'Austin Hodge, a St. Lucie County firefighter-paramedic, died on duty October 24.',
        'body': 'Firefighter-Paramedic Austin Hodge died Saturday, Oct. 24, while on duty. He joined the St. Lucie County Fire District in 2017.',
        'date': '2026-10-24', 'is_custom': True, 'authoritative_custom': True,
        'image_url': ORIGINAL_IMAGE,
        'category_key': 'st_lucie',
        'custom_id': 'st-lucie-firefighter-paramedic-austin-hodge-line-of-duty-death-2026-10-24',
    }


def duplicate():
    return {
        'slug': DUPLICATE,
        'headline': 'St. Lucie Fire District Mourns Second Hodge Brother in a Year',
        'teaser': 'A firefighter-paramedic with the St. Lucie County Fire District died Saturday morning while on duty, a year after his brother. Austin Hodge joined the district in 2017.',
        'body': 'Austin Hodge was assigned to Station 9. His younger brother Jarius Hodge died in July 2025.',
        'date': '2026-10-24',
        'is_custom': False,
        'category_key': 'st_lucie',
    }


def earlier_brother():
    return {
        'slug': '2025-07-23-jarius-hodge-firefighter-dies-after-falling-ill-on-duty',
        'headline': 'Jarius Hodge Dies After Falling Ill on Duty',
        'teaser': 'St. Lucie County Fire District firefighter Jarius Hodge died in July 2025.',
        'body': 'His older brother Austin Hodge worked for the same fire district.',
        'date': '2025-07-23',
        'category_key': 'st_lucie',
    }


def load_generate():
    if 'feedparser' not in sys.modules:
        feedparser = types.ModuleType('feedparser')
        feedparser.parse = lambda *a, **k: types.SimpleNamespace(entries=[])
        sys.modules['feedparser'] = feedparser
    if 'anthropic' not in sys.modules:
        anthropic = types.ModuleType('anthropic')
        class API:
            def __init__(self, *a, **kw):
                self.messages = types.SimpleNamespace(create=lambda **kw: None)
        anthropic.Anthropic = API
        sys.modules['anthropic'] = anthropic
    os.environ.setdefault('ANTHROPIC_API_KEY', 'offline-test-key')
    return importlib.import_module('scripts.generate')


class CanonicalHodgeTests(unittest.TestCase):
    def test_exact_same_death_despite_brother_angle(self):
        self.assertTrue(same_named_death_as_custom(duplicate(), original())[0])

    def test_different_brother_different_death(self):
        self.assertFalse(same_named_death_as_custom(earlier_brother(), original())[0])

    def test_surname_only_is_never_sufficient(self):
        other = duplicate()
        other['teaser'] = 'A St. Lucie Fire District firefighter named Alex Hodge died Saturday.'
        other['body'] = 'His brother was also a firefighter.'
        self.assertFalse(same_named_death_as_custom(other, original())[0])

    def test_wrong_date_cannot_own_old_custom_url(self):
        later = duplicate()
        later['slug'] = '2026-11-29-st-lucie-fire-district-mourns-second-hodge-brother-in-a-year'
        later['date'] = '2026-11-29'
        self.assertFalse(same_named_death_as_custom(later, original())[0])

    def test_wrong_agency_is_not_duplicate(self):
        other = duplicate()
        other['headline'] = 'City Firefighters Mourn Second Hodge Brother'
        other['teaser'] = 'A firefighter in Orlando died on duty. Austin Hodge was remembered.'
        other['body'] = 'Austin Hodge joined a different department.'
        self.assertFalse(same_named_death_as_custom(other, original())[0])

    def test_incorrect_name_is_not_duplicate(self):
        other = duplicate()
        other['teaser'] = other['teaser'].replace('Austin Hodge', 'Jarius Hodge')
        other['body'] = 'Jarius Hodge was assigned to Station 3.'
        self.assertFalse(same_named_death_as_custom(other, original())[0])

    def test_integration_resolves_to_original_custom(self):
        g = load_generate()
        match, confidence, basis = g._find_authoritative_custom_incident_match(
            duplicate(), archived_customs=[original()], current_customs=[])
        self.assertEqual(match['slug'], ORIGINAL)
        self.assertEqual(confidence, 100)
        self.assertIn('named-death-custom', basis)

    def test_published_skip_target_is_custom(self):
        g = load_generate()
        target, basis = g._published_skip_canonical(duplicate(), [original()])
        self.assertIsNotNone(target)
        self.assertEqual(target['slug'], ORIGINAL)

    def test_duplicate_cleanup_keeps_custom_and_redirects_new_url(self):
        g = load_generate()
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / 'articles').mkdir()
            cleaned, redirects = g.apply_canonical_story_cleanup(
                [original(), duplicate(), earlier_brother()], root / 'articles', root
            )
        slugs = [r['slug'] for r in cleaned]
        self.assertIn(ORIGINAL, slugs)
        self.assertIn(earlier_brother()['slug'], slugs)
        self.assertNotIn(DUPLICATE, slugs)
        self.assertTrue(any(r['source_slug'] == DUPLICATE and r['target_slug'] == ORIGINAL for r in redirects))
        self.assertEqual(next(r for r in cleaned if r['slug'] == ORIGINAL)['image_url'], ORIGINAL_IMAGE)

    def test_only_one_active_custom_article(self):
        path = Path('custom_articles.json')
        if not path.exists():
            self.skipTest('custom queue absent from test fixture')
        queued = json.loads(path.read_text(encoding='utf8'))
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]['slug'], ORIGINAL)
        self.assertEqual(queued[0]['image_url'], ORIGINAL_IMAGE)
        self.assertIn('Jarius', queued[0]['body'])


if __name__ == '__main__':
    unittest.main()
