"""Regression tests for source posting-date parsing."""

import unittest
from datetime import date, timedelta

from src.transform_load import parse_posted_date


class PostedDateTests(unittest.TestCase):
    def test_parses_jooble_iso_timestamp(self):
        self.assertEqual(parse_posted_date("2026-09-05T12:34:56.3870000Z"), date(2026, 9, 5))

    def test_preserves_relative_date_support(self):
        self.assertEqual(parse_posted_date("3 days ago"), date.today() - timedelta(days=3))


if __name__ == "__main__":
    unittest.main()
