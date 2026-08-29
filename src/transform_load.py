#!/usr/bin/env python3
"""
PH Job Market ETL Pipeline (Transform & Load)
---------------------------------------------
Reads scraped raw JSON snapshots from data/raw/, normalizes entities (Companies, Jobs,
Locations, Salaries in PHP, Experience levels, and Skill keywords), and loads them into 
PostgreSQL or SQLite (fallback database).

Usage:
    python src/transform_load.py [--raw-file data/raw/jobs_20260829_XXXXXX.json]
"""

import argparse
import glob
import json
import logging
import os
import re
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("transform_load")


# Configuration Defaults
DEFAULT_USD_TO_PHP = float(os.getenv("USD_TO_PHP_RATE", "58.00"))
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ph_job_market")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres_pass")
SQLITE_FALLBACK_DB = "ph_job_market.db"


# Skills Dictionary for Keyword Extraction
SKILL_TAXONOMY = {
    "sk_python": ("Python", "Programming", [r"\bpython\b", r"\bpy\b"]),
    "sk_javascript": ("JavaScript", "Programming", [r"\bjavascript\b", r"\bjs\b"]),
    "sk_typescript": ("TypeScript", "Programming", [r"\btypescript\b", r"\bts\b"]),
    "sk_sql": ("SQL", "Database", [r"\bsql\b"]),
    "sk_postgresql": ("PostgreSQL", "Database", [r"\bpostgresql\b", r"\bpostgres\b"]),
    "sk_mysql": ("MySQL", "Database", [r"\bmysql\b"]),
    "sk_react": ("React", "Framework", [r"\breact\b", r"\breactjs\b"]),
    "sk_node": ("Node.js", "Framework", [r"\bnode\.?js\b", r"\bnode\b"]),
    "sk_vue": ("Vue.js", "Framework", [r"\bvue\.?js\b", r"\bvue\b"]),
    "sk_django": ("Django", "Framework", [r"\bdjango\b"]),
    "sk_fastapi": ("FastAPI", "Framework", [r"\bfastapi\b"]),
    "sk_aws": ("AWS", "Cloud/DevOps", [r"\baws\b", r"\bamazon web services\b"]),
    "sk_docker": ("Docker", "Cloud/DevOps", [r"\bdocker\b"]),
    "sk_kubernetes": ("Kubernetes", "Cloud/DevOps", [r"\bkubernetes\b", r"\bk8s\b"]),
    "sk_gcp": ("Google Cloud", "Cloud/DevOps", [r"\bgcp\b", r"\bgoogle cloud\b"]),
    "sk_pandas": ("Pandas", "Data/AI", [r"\bpandas\b"]),
    "sk_pyspark": ("PySpark", "Data/AI", [r"\bpyspark\b", r"\bspark\b"]),
    "sk_tableau": ("Tableau", "Data/AI", [r"\btableau\b"]),
    "sk_powerbi": ("Power BI", "Data/AI", [r"\bpower bi\b", r"\bpowerbi\b"]),
    "sk_git": ("Git", "Tool", [r"\bgit\b", r"\bgithub\b"]),
    "sk_english": ("English Communication", "Soft Skill", [r"\benglish\b", r"\bcommunication\b"])
}


def get_latest_raw_file(raw_dir: str = "data/raw") -> Optional[str]:
    """Finds the most recent raw JSON file in data/raw/."""
    files = glob.glob(os.path.join(raw_dir, "jobs_*.json"))
    if not files:
        return None
    return max(files, key=os.path.getctime)


def parse_region(location_str: str) -> Tuple[str, str]:
    """Parses raw location string into standardized PH Region and Work Setup."""
    loc_lower = (location_str or "").lower()
    
    if "remote" in loc_lower:
        region = "Remote"
        setup = "Remote"
    elif any(city in loc_lower for city in ["makati", "bgc", "taguig", "pasig", "ortigas", "quezon", "manila", "alabang", "mandaluyong"]):
        region = "Metro Manila"
        setup = "Hybrid" if "hybrid" in loc_lower else ("Remote" if "remote" in loc_lower else "On-site")
    elif any(city in loc_lower for city in ["cebu", "mandaue", "lapu-lapu"]):
        region = "Central Visayas"
        setup = "Hybrid" if "hybrid" in loc_lower else "On-site"
    elif "davao" in loc_lower:
        region = "Davao Region"
        setup = "On-site"
    elif any(city in loc_lower for city in ["clark", "pampanga", "angeles"]):
        region = "Central Luzon"
        setup = "Hybrid"
    else:
        region = "Other PH / International"
        setup = "On-site"

    return region, setup


def calculate_salary_php(sal_min: Optional[float], sal_max: Optional[float], currency: str, exchange_rate: float = DEFAULT_USD_TO_PHP) -> Optional[float]:
    """Calculates PHP equivalent average monthly salary."""
    if sal_min is None and sal_max is None:
        return None
    
    min_val = sal_min or sal_max or 0.0
    max_val = sal_max or sal_min or 0.0
    avg_val = (min_val + max_val) / 2.0
    
    if (currency or "PHP").upper() == "USD":
        return round(avg_val * exchange_rate, 2)
    return round(avg_val, 2)


def extract_skills_from_text(text: str, explicit_skills: List[str] = None) -> List[str]:
    """Extracts skill IDs matching the taxonomy from job description and skills list."""
    matched_skills = set()
    
    # Match from explicit skills list first
    if explicit_skills:
        for s in explicit_skills:
            s_clean = s.lower()
            for skill_id, (_, _, patterns) in SKILL_TAXONOMY.items():
                for pat in patterns:
                    if re.search(pat, s_clean, re.IGNORECASE):
                        matched_skills.add(skill_id)
                        
    # Match against full description text
    text_clean = text.lower()
    for skill_id, (_, _, patterns) in SKILL_TAXONOMY.items():
        for pat in patterns:
            if re.search(pat, text_clean, re.IGNORECASE):
                matched_skills.add(skill_id)
                break
                
    return list(matched_skills)


def get_db_connection():
    """Initializes PostgreSQL connection or falls back to SQLite."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            connect_timeout=3
        )
        logger.info(f"Connected to PostgreSQL database '{DB_NAME}' on {DB_HOST}:{DB_PORT}.")
        return conn, "postgres"
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed ({e}). Falling back to SQLite database '{SQLITE_FALLBACK_DB}'...")
        conn = sqlite3.connect(SQLITE_FALLBACK_DB)
        return conn, "sqlite"


def initialize_sqlite_schema(conn: sqlite3.Connection):
    """Initializes SQLite schema if fallback mode is used."""
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            company_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            industry TEXT,
            location TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company_id TEXT,
            company_name TEXT,
            location TEXT,
            region TEXT,
            work_setup TEXT,
            salary_min REAL,
            salary_max REAL,
            salary_currency TEXT,
            salary_php_equiv REAL,
            experience_level TEXT,
            employment_type TEXT,
            description TEXT,
            source TEXT,
            posted_date TEXT,
            scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS skills (
            skill_id TEXT PRIMARY KEY,
            skill_name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS job_skills (
            job_id TEXT,
            skill_id TEXT,
            PRIMARY KEY (job_id, skill_id)
        );
    """)
    
    # Pre-seed skills
    for skill_id, (skill_name, category, _) in SKILL_TAXONOMY.items():
        cursor.execute(
            "INSERT OR IGNORE INTO skills (skill_id, skill_name, category) VALUES (?, ?, ?)",
            (skill_id, skill_name, category)
        )
    conn.commit()


def transform_and_load(raw_filepath: str) -> dict:
    """Executes the transformation and database load step."""
    logger.info(f"Reading raw data snapshot from '{raw_filepath}'...")
    with open(raw_filepath, "r", encoding="utf-8") as f:
        raw_jobs = json.load(f)

    conn, db_type = get_db_connection()
    cursor = conn.cursor()

    if db_type == "sqlite":
        initialize_sqlite_schema(conn)

    companies_loaded = 0
    jobs_loaded = 0
    skills_linked = 0

    for item in raw_jobs:
        # 1. Company processing
        comp_name = item.get("company_name", "Unknown Company")
        comp_id = f"comp_{re.sub(r'[^a-zA-Z0-9]', '_', comp_name.lower())}"
        comp_industry = item.get("company_industry", "Technology")
        comp_loc = item.get("location", "Philippines")

        if db_type == "postgres":
            cursor.execute("""
                INSERT INTO companies (company_id, name, industry, location)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (company_id) DO NOTHING;
            """, (comp_id, comp_name, comp_industry, comp_loc))
        else:
            cursor.execute("""
                INSERT OR IGNORE INTO companies (company_id, name, industry, location)
                VALUES (?, ?, ?, ?);
            """, (comp_id, comp_name, comp_industry, comp_loc))
        companies_loaded += 1

        # 2. Job transformations
        job_id = item.get("job_id")
        title = item.get("title")
        raw_loc = item.get("location", "")
        region, work_setup = parse_region(raw_loc)
        
        # Override setup if explicitly provided
        if item.get("work_setup") in ["Remote", "Hybrid", "On-site"]:
            work_setup = item.get("work_setup")

        currency = item.get("salary_currency", "PHP")
        sal_min = item.get("salary_min")
        sal_max = item.get("salary_max")
        sal_php = calculate_salary_php(sal_min, sal_max, currency)

        exp_level = item.get("experience_level", "Unspecified")
        emp_type = item.get("employment_type", "Full-time")
        description = item.get("description", "")
        source = item.get("source", "Scraper")
        posted_date = item.get("posted_date", datetime.now().strftime("%Y-%m-%d"))

        if db_type == "postgres":
            cursor.execute("""
                INSERT INTO jobs (
                    job_id, title, company_id, company_name, location, region, work_setup,
                    salary_min, salary_max, salary_currency, salary_php_equiv,
                    experience_level, employment_type, description, source, posted_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO UPDATE SET
                    salary_php_equiv = EXCLUDED.salary_php_equiv,
                    region = EXCLUDED.region;
            """, (job_id, title, comp_id, comp_name, raw_loc, region, work_setup,
                  sal_min, sal_max, currency, sal_php, exp_level, emp_type, description, source, posted_date))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO jobs (
                    job_id, title, company_id, company_name, location, region, work_setup,
                    salary_min, salary_max, salary_currency, salary_php_equiv,
                    experience_level, employment_type, description, source, posted_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (job_id, title, comp_id, comp_name, raw_loc, region, work_setup,
                  sal_min, sal_max, currency, sal_php, exp_level, emp_type, description, source, posted_date))
        jobs_loaded += 1

        # 3. Skill extraction & linking
        explicit_skills = item.get("skills_required", [])
        matched_skill_ids = extract_skills_from_text(description, explicit_skills)

        for skill_id in matched_skill_ids:
            if db_type == "postgres":
                cursor.execute("""
                    INSERT INTO job_skills (job_id, skill_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                """, (job_id, skill_id))
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO job_skills (job_id, skill_id)
                    VALUES (?, ?);
                """, (job_id, skill_id))
            skills_linked += 1

    conn.commit()
    conn.close()

    summary = {
        "status": "success",
        "database_type": db_type,
        "companies_processed": companies_loaded,
        "jobs_loaded": jobs_loaded,
        "job_skills_linked": skills_linked
    }
    logger.info(f"ETL Complete [{db_type}]: Loaded {jobs_loaded} jobs, linked {skills_linked} skills.")
    return summary


def main():
    parser = argparse.ArgumentParser(description="PH Job Market ETL Pipeline")
    parser.add_argument("--raw-file", type=str, help="Path to raw JSON file. If omitted, uses latest file in data/raw.")
    args = parser.parse_args()

    raw_filepath = args.raw_file or get_latest_raw_file()
    if not raw_filepath or not os.path.exists(raw_filepath):
        logger.error("No valid raw data JSON file found. Please run 'python src/scrape.py' first.")
        sys.exit(1)

    transform_and_load(raw_filepath)


if __name__ == "__main__":
    main()
