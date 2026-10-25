"""Regression contracts for the isolated historical provider comparison."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "scripts" / "historical_editorial_bakeoff.py"
SPEC = importlib.util.spec_from_file_location("historical_editorial_bakeoff", CODE)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class HistoricalEditorialBakeoff(unittest.TestCase):
    def test_normalized_source_urls_ignore_tracking_and_hostnames(self):
        self.assertEqual(MOD.urlkey("https://www.wptv.com/news/example-incident?fbclid=1"),
                         "wptv.com/news/example-incident")
        self.assertEqual(MOD.urlkey("http://www.wptv.com/news/example-incident"),
                         "wptv.com/news/example-incident")
        self.assertEqual(MOD.urlkey("https://news.google.com/rss/articles/abc"), "")
        self.assertEqual(MOD.urlkey("https://example.com"), "")

    def test_only_exact_historic_source_evidence_and_canonical_articles_match(self):
        source_url = "https://www.example.com/local/stuart-proposal-record"
        source = {MOD.urlkey(source_url): {
            "source_url": source_url,
            "evidence": "The county approved a proposal.",
            "captured": "2026-09-20T12:10:00Z",
            "snapshot": "a" * 40,
        }}
        baseline = {"slug": "2026-09-19-stuart-county-proposal",
                    "canonical_slug": "2026-09-19-stuart-county-proposal",
                    "headline": "TCT headline must not be sent to either provider",
                    "source_url": source_url, "date": "2026-09-19",
                    "category_label": "Martin County", "source_headline": "Proposal record"}
        archive = [baseline, {**baseline, "slug": "2026-09-19-other-incident",
                              "source_url": "https://example.com/other/page"},
                   {**baseline, "slug": "2026-09-19-duplicate",
                    "canonical_slug": baseline["slug"]},
                   {**baseline, "slug": "2026-09-19-custom-story", "is_custom": True}]
        chosen, eligible, all_candidates = MOD.cases(archive, source, 30, 1)
        self.assertEqual(eligible, 1)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(len(all_candidates), 1)
        prompt = MOD.writing_prompt(chosen[0])
        self.assertNotIn("TCT headline must not be sent", prompt)
        self.assertIn("The county approved a proposal.", prompt)
        self.assertIn("2026-09-19", prompt)

    def test_homepage_groups_never_mix_historic_days(self):
        rows = [{"id": str(i), "date": day, "evidence": "Evidence",
                 "source_headline": "Title"}
                for day, num in (("2026-08-20", 3), ("2026-09-12", 2))
                for i in range(num)]
        groups = MOD.ranking_groups(rows)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["date"], "2026-08-20")
        self.assertEqual(len(groups[0]["rows"]), 3)

    def test_replay_is_not_production_or_scheduled(self):
        workflow = (ROOT / ".github/workflows/historical-editorial-bakeoff.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("dry_run:", workflow)
        self.assertNotIn("git push", workflow)
        self.assertNotIn("scripts/generate.py", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("cron:", workflow)
        self.assertNotIn("production", workflow.lower().split("jobs:", 1)[1].split("name:", 1)[0])

    def test_review_scoring_is_blind_and_devoid_of_provider_names(self):
        row = {"source": {"id": "001", "slug": "article", "date": "2026-09-18",
                           "reference_headline": "Editorial reference only",
                           "source_url": "https://example.com/a/very-long-path",
                           "evidence": "Original source passage"},
               "variants": {"A": {"data": {"headline": "Story", "teaser": "Summary", "body": "Text"}},
                            "B": {"data": {"headline": "Other", "teaser": "Summary", "body": "Text"}}}}
        review = MOD.markdown([row], [])
        self.assertIn("Variant A", review)
        self.assertIn("Variant B", review)
        self.assertNotIn("claude-sonnet-5", review)
        self.assertNotIn("gpt-6.1-sol", review)


if __name__ == "__main__":
    unittest.main()
