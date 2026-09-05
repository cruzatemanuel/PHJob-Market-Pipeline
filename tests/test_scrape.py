"""Unit tests for mock generation and Jooble API response handling."""

import json
import tempfile
import unittest
from pathlib import Path

from src import scrape


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return FakeResponse(next(self.payloads))

    def close(self):
        return None


class ScrapeTests(unittest.TestCase):
    def test_mock_jobs_are_deterministic_and_schema_compatible(self):
        first = scrape.generate_mock_jobs(3, seed=7)
        second = scrape.generate_mock_jobs(3, seed=7)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        self.assertTrue(first[0]["source_url"].startswith("mock://"))
        self.assertIn("salary_raw", first[0])

    def test_jooble_payload_uses_documented_pagination_fields(self):
        self.assertEqual(
            scrape.jooble_payload("data engineer", "Cebu", page=2, results_per_page=20),
            {
                "keywords": "data engineer",
                "location": "Cebu",
                "page": 2,
                "ResultOnPage": 20,
                "companysearch": False,
            },
        )

    def test_collect_jooble_jobs_normalizes_and_deduplicates_pages(self):
        config = scrape.JoobleConfig(
            api_key="test-key",
            api_base_url="https://ph.jooble.org/api",
            keywords=("data analyst",),
            locations=("Philippines",),
            results_per_page=2,
            max_pages_per_query=3,
            timeout_seconds=5,
            request_delay=0,
        )
        session = FakeSession(
            [
                {
                    "totalCount": 3,
                    "jobs": [
                        {
                            "id": 1,
                            "title": "Data Analyst",
                            "company": "Example Corp",
                            "location": "Makati",
                            "snippet": "Use SQL and Python.",
                            "salary": "PHP 40,000 - PHP 60,000",
                            "source": "Example Board",
                            "type": "Full-time",
                            "link": "https://example.com/jobs/1",
                            "updated": "2026-09-05T00:00:00Z",
                        },
                        {"id": 2, "title": "Incomplete", "company": "", "link": "https://example.com/jobs/2"},
                    ],
                },
                {
                    "totalCount": 3,
                    "jobs": [
                        {
                            "id": 1,
                            "title": "Data Analyst",
                            "company": "Example Corp",
                            "link": "https://example.com/jobs/1",
                        },
                        {
                            "id": 3,
                            "title": "Data Engineer",
                            "company": "Other Corp",
                            "link": "https://example.com/jobs/3",
                        },
                    ],
                },
            ]
        )

        jobs = scrape.collect_jooble_jobs(config, max_records=5, session=session)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["source"], "Jooble / Example Board")
        self.assertEqual(jobs[0]["query_location"], "Philippines")
        self.assertEqual([call["json"]["page"] for call in session.calls], [1, 2])
        self.assertEqual(session.calls[0]["url"], "https://ph.jooble.org/api/test-key")

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
