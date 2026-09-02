"""Unit tests for the scraper's reproducible, source-independent behaviour."""

import json
import tempfile
import unittest
from pathlib import Path

from src import scrape


class ScrapeTests(unittest.TestCase):
    def test_mock_jobs_are_deterministic_and_schema_compatible(self):
        first = scrape.generate_mock_jobs(3, seed=7)
        second = scrape.generate_mock_jobs(3, seed=7)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        self.assertEqual(
            set(first[0]),
            {
                "title", "company", "location", "salary_raw", "posted_raw",
                "source_url", "raw_description", "source", "scraped_at",
            },
        )
        self.assertTrue(first[0]["source_url"].startswith("mock://"))

    def test_live_config_requires_pagination_and_core_selectors(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "invalid.json"
            config_path.write_text(
                json.dumps({"source_name": "Example", "listing_url_template": "https://example.com/jobs"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "\\{page\\}"):
                scrape.load_live_config(config_path)

    def test_main_writes_a_mock_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            result = scrape.main(["--mode", "mock", "--count", "2", "--seed", "3", "--output-dir", str(output_dir)])

            self.assertEqual(result, 0)
            snapshots = list(output_dir.glob("raw_jobs_*.json"))
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(len(json.loads(snapshots[0].read_text(encoding="utf-8"))), 2)


if __name__ == "__main__":
    unittest.main()
