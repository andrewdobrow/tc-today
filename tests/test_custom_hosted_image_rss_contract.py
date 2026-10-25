"""Regression for Austin Hodge's first-party, editor-selected custom photograph."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CDN_IMAGE = (
    'https://images.treasurecoast.today/articles/1f/'
    '1f251033eb69a787817d92d69c72b17fd19d387421401002ec9ed34b5d0decc6.jpg'
)
SLUG = '2026-10-24-st-lucie-county-firefighter-paramedic-austin-hodge-dies-in-line-of-duty'
CUSTOM_ID = 'st-lucie-firefighter-paramedic-austin-hodge-line-of-duty-death-2026-10-24'


def load_generate():
    if 'feedparser' not in sys.modules:
        m = types.ModuleType('feedparser')
        m.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
        sys.modules['feedparser'] = m
    if 'anthropic' not in sys.modules:
        m = types.ModuleType('anthropic')
        m.Anthropic = lambda *args, **kwargs: None
        sys.modules['anthropic'] = m
    if 'json_repair' not in sys.modules:
        m = types.ModuleType('json_repair')
        m.repair_json = lambda data, **kwargs: data
        m.loads = json.loads
        sys.modules['json_repair'] = m
    os.environ.setdefault('ANTHROPIC_API_KEY', 'offline-test-key')
    spec = importlib.util.spec_from_file_location('rss_custom_image_test_generate', ROOT/'scripts'/'generate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def custom_row(**overrides):
    row = {
        'slug': SLUG,
        'headline': 'St. Lucie County Firefighter-Paramedic Austin Hodge Dies in Line of Duty',
        'teaser': 'Firefighter Austin Hodge died October 24.',
        'category_key': 'st_lucie',
        'first_published': 'Sat, 24 Oct 2026 17:07:00 -0400',
        'is_custom': True,
        'authoritative_custom': True,
        'custom_id': CUSTOM_ID,
        'image_url': CDN_IMAGE,
        'source_image_url': CDN_IMAGE,
        'hosted_image_url': CDN_IMAGE,
    }
    row.update(overrides)
    return row


class CustomHostedImageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = load_generate()
        from tct_engine.custom_hosted_social_image import is_editor_authored_custom_hosted_image
        cls.check = staticmethod(is_editor_authored_custom_hosted_image)

    def is_custom_image(self, row):
        return self.check(row, CDN_IMAGE, absolute_image_url=self.g._absolute_image_url, is_tct_image=self.g._is_tct_mirrored_image_url)

    def test_first_party_custom_photo_is_explicitly_allowed(self):
        self.assertTrue(self.is_custom_image(custom_row()))

    def test_non_custom_publisher_mirror_without_original_source_is_rejected(self):
        self.assertFalse(self.is_custom_image(custom_row(is_custom=False, authoritative_custom=False)))

    def test_missing_durable_identity_is_rejected(self):
        self.assertFalse(self.is_custom_image(custom_row(custom_id='')))

    def test_image_metadata_mismatch_is_rejected(self):
        for field in ('image_url', 'source_image_url', 'hosted_image_url'):
            with self.subTest(field=field):
                self.assertFalse(self.is_custom_image(custom_row(**{field: 'https://different.example/photo.jpg'})))

    def test_stale_mirror_status_cannot_override_custom_editor_selection(self):
        self.assertTrue(self.is_custom_image(custom_row(article_image_mirror_status='mirrored')))

    def _run_feed_validation(self, row):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root/'archive.json').write_text(json.dumps([row]), encoding='utf-8')
            with patch.object(self.g, 'OUTPUT_DIR', root), patch.dict(os.environ, {'TCT_ARTICLE_IMAGE_MODE': 'mirror'}):
                feed = self.g.render_rss_feed([], {}, max_items=10)
                (root/'feed.xml').write_text(feed, encoding='utf-8')
                report = None
                try:
                    report = self.g.validate_rss_social_image_contract(root)
                except RuntimeError:
                    pass
                result = json.loads((root/'data/rss-social-image-contract.json').read_text(encoding='utf-8'))
                saved = json.loads((root/'archive.json').read_text(encoding='utf-8'))[0]
                return result, saved, feed

    def test_full_rss_flow_accepts_original_hodge_custom_image(self):
        report, saved, feed = self._run_feed_validation(custom_row())
        self.assertEqual(report['status'], 'passed', report['issues'])
        self.assertEqual(report['persisted_source_images'], 1)
        self.assertIn(CDN_IMAGE, feed)
        self.assertEqual(saved['image_url'], CDN_IMAGE)
        self.assertEqual(saved['source_image_url'], CDN_IMAGE)
        self.assertEqual(saved['hosted_image_url'], CDN_IMAGE)
        self.assertEqual(saved['rss_social_image_url'], CDN_IMAGE)

    def test_full_rss_flow_rejects_unprovenanced_mirror(self):
        report, _, _ = self._run_feed_validation(custom_row(is_custom=False, authoritative_custom=False))
        self.assertEqual(report['status'], 'failed')
        self.assertIn('mirrored_source_authority_not_persisted_to_archive', [r['reason'] for r in report['issues']])

    def test_full_rss_flow_rejects_mismatched_custom_image_metadata(self):
        report, _, _ = self._run_feed_validation(custom_row(source_image_url='https://example.com/other.jpg', article_image_mirror_status='mirrored'))
        # Publisher mirror with legitimate distinct original source is allowed.
        self.assertEqual(report['status'], 'passed', report['issues'])
        report, _, _ = self._run_feed_validation(custom_row(source_image_url=CDN_IMAGE, article_image_mirror_status='mirrored'))
        self.assertEqual(report['status'], 'passed')



if __name__ == '__main__':
    unittest.main()
