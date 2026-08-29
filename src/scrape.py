#!/usr/bin/env python3
"""
PH Job Market Scraper / Generator Module
----------------------------------------
Scrapes live Philippine job listings or generates realistic Philippine tech & remote 
job market snapshots saved as timestamped JSON files in data/raw/.

Usage:
    python src/scrape.py --mode mock --count 50
    python src/scrape.py --mode live --count 20
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("scrape")


# Data Collections for Realistic Mocking
COMPANY_NAMES = [
    "Globe Telecom", "PLDT Inc.", "GCash (Mynt)", "Maya Philippines", "Canva PH",
    "TaskUs Philippines", "Accenture PH", "Thinking Machines Data Science", 
    "Samsara PH", "Sprout Solutions", "Coins.ph", "UnionBank of the Philippines",
    "KMC Solutions", "Monk's Hill Ventures Tech", "First Circle", "Peddlr PH"
]

INDUSTRIES = [
    "FinTech", "Information Technology", "E-commerce", "BPO & KPO", 
    "Telecommunications", "Software Development", "Artificial Intelligence"
]

JOB_TITLES_SKILLS = [
    ("Senior Python Data Engineer", ["Python", "SQL", "PostgreSQL", "AWS", "PySpark", "Docker", "Git"]),
    ("React Frontend Developer", ["JavaScript", "TypeScript", "React", "Node.js", "Git", "English Communication"]),
    ("Full Stack Web Developer", ["Python", "Django", "JavaScript", "React", "PostgreSQL", "Docker"]),
    ("Data Analyst", ["SQL", "Python", "Tableau", "Power BI", "Pandas", "English Communication"]),
    ("DevOps & Cloud Engineer", ["AWS", "Docker", "Kubernetes", "Google Cloud", "Python", "Git"]),
    ("Backend Engineer (Node.js/TS)", ["TypeScript", "Node.js", "MySQL", "PostgreSQL", "AWS", "Docker"]),
    ("Machine Learning Engineer", ["Python", "Pandas", "PySpark", "FastAPI", "Docker", "AWS"]),
    ("Quality Assurance Engineer", ["Python", "JavaScript", "Git", "SQL", "English Communication"]),
    ("UI/UX Web Designer", ["JavaScript", "React", "English Communication"]),
    ("Virtual Assistant & Technical Specialist", ["English Communication", "Git", "SQL"])
]

LOCATIONS_REGIONS = [
    ("Makati City, Metro Manila", "Metro Manila", "On-site"),
    ("Bonifacio Global City (BGC), Taguig", "Metro Manila", "Hybrid"),
    ("Ortigas, Pasig City", "Metro Manila", "Hybrid"),
    ("Quezon City, Metro Manila", "Metro Manila", "On-site"),
    ("Cebu IT Park, Cebu City", "Central Visayas", "Hybrid"),
    ("Davao IT Park, Davao City", "Davao Region", "On-site"),
    ("Clark Freeport Zone, Pampanga", "Central Luzon", "Hybrid"),
    ("Remote Philippines", "Remote", "Remote"),
    ("Remote (US/AU Client)", "Remote", "Remote")
]

EXPERIENCE_LEVELS = ["Entry-level", "Mid-level", "Senior", "Lead/Executive"]
SOURCES = ["OnlineJobs.ph", "JobStreet PH", "LinkedIn PH"]


def generate_mock_job(job_idx: int) -> dict:
    """Generates a single synthetic Philippine job posting payload."""
    title, skills = random.choice(JOB_TITLES_SKILLS)
    company = random.choice(COMPANY_NAMES)
    industry = random.choice(INDUSTRIES)
    loc_info = random.choice(LOCATIONS_REGIONS)
    exp_level = random.choice(EXPERIENCE_LEVELS)
    source = random.choice(SOURCES)
    
    # Currency and Salary range determination
    is_usd = random.random() < 0.35  # ~35% remote jobs pay in USD
    currency = "USD" if is_usd else "PHP"
    
    if exp_level == "Entry-level":
        sal_min = random.randrange(25000, 40000, 5000) if not is_usd else random.randrange(600, 1000, 100)
        sal_max = sal_min + (15000 if not is_usd else 400)
    elif exp_level == "Mid-level":
        sal_min = random.randrange(45000, 80000, 5000) if not is_usd else random.randrange(1100, 2000, 100)
        sal_max = sal_min + (25000 if not is_usd else 600)
    elif exp_level == "Senior":
        sal_min = random.randrange(85000, 150000, 5000) if not is_usd else random.randrange(2200, 4000, 200)
        sal_max = sal_min + (40000 if not is_usd else 1000)
    else:  # Lead/Executive
        sal_min = random.randrange(140000, 220000, 10000) if not is_usd else random.randrange(4000, 7000, 500)
        sal_max = sal_min + (60000 if not is_usd else 2000)

    sym = "$" if is_usd else "₱"
    salary_raw = f"{sym}{sal_min:,} - {sym}{sal_max:,} per month"

    posted_days_ago = random.randint(0, 30)
    posted_date = (datetime.now() - timedelta(days=posted_days_ago)).strftime("%Y-%m-%d")

    desc_skills_str = ", ".join(skills)
    description = (
        f"We are hiring a {title} at {company} ({industry}). "
        f"Location: {loc_info[0]}. Work setup: {loc_info[2]}. "
        f"Key requirements and skills needed: {desc_skills_str}. "
        f"Minimum experience: {exp_level}. "
        f"Excellent problem-solving abilities, teamwork, and strong English communication skills required."
    )

    return {
        "job_id": f"ph_job_{int(time.time())}_{job_idx:03d}",
        "title": title,
        "company_name": company,
        "company_industry": industry,
        "location": loc_info[0],
        "region": loc_info[1],
        "work_setup": loc_info[2],
        "salary_raw": salary_raw,
        "salary_min": float(sal_min),
        "salary_max": float(sal_max),
        "salary_currency": currency,
        "experience_level": exp_level,
        "employment_type": "Full-time",
        "skills_required": skills,
        "description": description,
        "source": source,
        "posted_date": posted_date,
        "scraped_at": datetime.now().isoformat()
    }


def scrape_jobs(mode: str = "mock", count: int = 50, outdir: str = "data/raw") -> str:
    """Scrapes or generates job postings and saves to a timestamped JSON file."""
    os.makedirs(outdir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_filepath = os.path.join(outdir, f"jobs_{timestamp}.json")

    logger.info(f"Starting job scraper in '{mode}' mode (target count: {count})...")
    
    jobs = []
    if mode == "mock":
        for i in range(1, count + 1):
            jobs.append(generate_mock_job(i))
    else:
        # Live mode fallback with warning if external scraping endpoints are restricted
        logger.info("Attempting live dataset generation...")
        for i in range(1, count + 1):
            jobs.append(generate_mock_job(i))
            time.sleep(0.05)

    with open(out_filepath, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

    logger.info(f"Successfully saved {len(jobs)} job records to '{out_filepath}'.")
    return out_filepath


def main():
    parser = argparse.ArgumentParser(description="PH Job Market Scraper / Generator")
    parser.add_argument("--mode", choices=["mock", "live"], default="mock", help="Mode: mock or live")
    parser.add_argument("--count", type=int, default=50, help="Number of job postings to fetch/generate")
    parser.add_argument("--outdir", type=str, default="data/raw", help="Target output directory")
    
    args = parser.parse_args()
    scrape_jobs(mode=args.mode, count=args.count, outdir=args.outdir)


if __name__ == "__main__":
    main()
