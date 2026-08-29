#!/usr/bin/env python3
"""
Pipeline & Data Integrity Test Suite
------------------------------------
Automated validation suite for PH Job Market Data Pipeline using standard unittest.

Usage:
    python3 tests/validate_load.py
    python3 -m unittest tests/validate_load.py
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest

# Ensure project root is in Python module search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrape import generate_mock_job, scrape_jobs
from src.transform_load import (
    calculate_salary_php,
    extract_skills_from_text,
    initialize_sqlite_schema,
    parse_region,
    transform_and_load,
)
from src.generate_charts import main as run_generate_charts


class TestPHJobMarketPipeline(unittest.TestCase):

    def test_mock_job_generation_schema(self):
        """Validates structure and required fields of mock job payload."""
        job = generate_mock_job(1)
        required_keys = [
            "job_id", "title", "company_name", "company_industry",
            "location", "region", "work_setup", "salary_min",
            "salary_max", "salary_currency", "experience_level",
            "description", "source", "posted_date"
        ]
        for key in required_keys:
            self.assertIn(key, job, f"Missing required field '{key}' in generated job payload.")
            
        self.assertLessEqual(job["salary_min"], job["salary_max"], "salary_min must be <= salary_max")
        self.assertIn(job["salary_currency"], ["PHP", "USD"], f"Unexpected currency: {job['salary_currency']}")

    def test_scraper_json_creation(self):
        """Validates that scrape_jobs creates a valid raw JSON snapshot."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = scrape_jobs(mode="mock", count=5, outdir=tmp_dir)
            
            self.assertTrue(os.path.exists(out_file), "Scraper output JSON file should exist.")
            with open(out_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            self.assertIsInstance(data, list), "JSON data must be a list."
            self.assertEqual(len(data), 5, f"Expected 5 job records, found {len(data)}")

    def test_salary_conversion(self):
        """Validates PHP salary conversion for PHP and USD currencies."""
        # PHP test
        php_sal = calculate_salary_php(50000, 70000, "PHP")
        self.assertEqual(php_sal, 60000.0)

        # USD test with rate 58.0
        usd_sal = calculate_salary_php(1000, 2000, "USD", exchange_rate=58.0)
        self.assertEqual(usd_sal, 87000.0)

        # None handling
        self.assertIsNone(calculate_salary_php(None, None, "PHP"))

    def test_region_and_setup_parsing(self):
        """Validates location text parsing into standard region and work setup."""
        reg, setup = parse_region("Makati City, Metro Manila")
        self.assertEqual(reg, "Metro Manila")
        self.assertIn(setup, ["On-site", "Hybrid", "Remote"])

        reg_cebu, _ = parse_region("Cebu IT Park, Cebu City")
        self.assertEqual(reg_cebu, "Central Visayas")

        reg_remote, setup_remote = parse_region("Remote Philippines")
        self.assertEqual(reg_remote, "Remote")
        self.assertEqual(setup_remote, "Remote")

    def test_skill_keyword_extraction(self):
        """Validates regex matching for skills taxonomy."""
        text = "We are seeking a Senior Python Developer with Docker, AWS, and PostgreSQL experience."
        skills = extract_skills_from_text(text)
        
        self.assertIn("sk_python", skills)
        self.assertIn("sk_docker", skills)
        self.assertIn("sk_aws", skills)
        self.assertIn("sk_postgresql", skills)

    def test_end_to_end_etl(self):
        """Integration test: Scrapes mock data, loads into DB, and verifies records."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = scrape_jobs(mode="mock", count=15, outdir=tmp_dir)
            
            result = transform_and_load(json_path)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["jobs_loaded"], 15)
            self.assertGreater(result["job_skills_linked"], 0)

            test_db = "ph_job_market.db"
            self.assertTrue(os.path.exists(test_db), "Fallback SQLite database should exist after load.")

            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs;")
            count = cursor.fetchone()[0]
            self.assertGreaterEqual(count, 15, "Database jobs count should be at least 15.")
            conn.close()


if __name__ == "__main__":
    unittest.main()
