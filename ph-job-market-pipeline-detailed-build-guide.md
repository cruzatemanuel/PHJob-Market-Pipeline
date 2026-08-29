# PH Job Market Analytics Pipeline — Full Detailed Build Guide

**Repo:** `ph-job-market-pipeline` (5-Week Build)

This is the code-level companion to the phase overview: every file you need to write, filled in, per phase. Copy, adapt the TODOs, ship.

## Contents
- [Prerequisites](#prerequisites)
- [Repository Structure](#repository-structure)
- [Phase 0 — Data Source Decision](#phase-0--data-source-decision-recap)
- [Phase 1 (Week 1) — Foundation](#phase-1-week-1--foundation)
- [Phase 2 (Week 2) — Extract](#phase-2-week-2--extract)
- [Phase 3 (Week 3) — Transform + Load](#phase-3-week-3--transform--load)
- [Phase 4 (Week 4) — Analyze + Visualize](#phase-4-week-4--analyze--visualize)
- [Phase 5 (Week 5) — Polish + Ship](#phase-5-week-5--polish--ship)
- [Appendix A — Troubleshooting](#appendix-a--troubleshooting)
- [Appendix B — Risk Reminders](#appendix-b--risk-reminders)

---

## Prerequisites

- Python 3.12, Docker Desktop, a GitHub account, a Postgres client (DBeaver / TablePlus / `psql`)
- `pip install playwright && playwright install chromium` if you're scraping a JS-rendered source
- **This is the same core stack as PhilWeather v2** (Python, pandas, PostgreSQL, SQLAlchemy, matplotlib, GitHub) — Docker is the one piece coming back from v1 here, added deliberately for environment reproducibility, not scope creep. Web scraping and a real branching workflow are the two genuinely new skills this project proves.
- Since you're already running Claude Code, you can hand it each phase's section below as a task directly — the code blocks are written to be implemented as-is, not just read.

**Timing flag worth checking now:** your semester runs a 17-week structure with synchronized Prelim/Midterm/Final weeks, and Week 4–5 of this build is roughly when Prelims tend to land. Pull up your actual exam schedule before committing to the Week 4 date — if Prelims overlap, front-load Phase 4's SQL queries earlier (they don't depend on anything in Phase 4 beyond a loaded database) so Week 5 is polish-only, not a scramble.

---

## Repository Structure

```
ph-job-market-pipeline/
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── docker-compose.yml
├── requirements.txt
├── data/
│   └── raw/              # scraped JSON snapshots — gitignored, structure documented below
├── db/
│   └── schema.sql
├── src/
│   ├── scrape.py
│   ├── transform_load.py
│   └── generate_charts.py
├── queries/
│   └── analysis.sql
├── charts/               # PNG output from generate_charts.py
└── tests/
    └── validate_load.py
```

---

## Phase 0 — Data Source Decision (recap)

Lock this before Week 1. JobStreet PH is JS-rendered and ToS-restricted — Kalibrr is more scrape-tolerant but smaller. If unresolved, default to: attempt your first choice for 3 days max in Week 2, fall back to a smaller (50–80 post) sample from the friendlier source if blocked, and document the decision in the README's Data Source section. Everything below is written source-agnostically so it works either way — only the selectors in `scrape.py` change.

---

## Phase 1 (Week 1) — Foundation

### `.gitignore`
```gitignore
# Python
__pycache__/
*.pyc
.venv/
venv/

# Env
.env

# Data
data/raw/*.json

# OS
.DS_Store
```

### `.env.example`
```env
POSTGRES_USER=ph_job_market_user
POSTGRES_PASSWORD=changeme
POSTGRES_DB=ph_job_market
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

### `requirements.txt`
```
requests==2.32.3
beautifulsoup4==4.12.3
playwright==1.47.0
pandas==2.2.3
SQLAlchemy==2.0.35
psycopg2-binary==2.9.9
python-dotenv==1.0.1
matplotlib==3.9.2
```
Treat these as starting pins, not gospel — run `pip list --outdated` after your first install and update deliberately rather than leaving versions to drift silently.

### `docker-compose.yml`
```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16
    container_name: ph_job_market_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/schema.sql:/docker-entrypoint-initdb.d/schema.sql

volumes:
  pgdata:
```
The mounted `schema.sql` only auto-runs on the **first** container init (when the volume is empty). If you change the schema later, `docker compose down -v` (wipes the volume) then `docker compose up -d` to re-apply it — don't lose an afternoon wondering why your `ALTER`-free schema edit isn't showing up.

### `db/schema.sql`
```sql
-- PH Job Market Analytics Pipeline — Schema
-- Auto-runs on first container init via docker-entrypoint-initdb.d

CREATE TABLE companies (
    company_id      SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL UNIQUE,
    industry        VARCHAR(100)          -- e.g. 'BPO', 'Banking', 'Tech', 'Telco' — powers Query 4's PARTITION BY
);

CREATE TABLE job_postings (
    job_id              SERIAL PRIMARY KEY,
    title               VARCHAR(255) NOT NULL,
    company_id          INTEGER REFERENCES companies(company_id),
    location            VARCHAR(255),
    salary_monthly_php  NUMERIC(10,2),     -- normalized midpoint during transform; NULL if source omitted it
    level               VARCHAR(20) CHECK (level IN ('entry', 'mid', 'senior', 'unspecified')),
    posted_date         DATE,
    source_url          TEXT UNIQUE,       -- also your dedup key
    raw_description     TEXT,
    scraped_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE skills (
    skill_id        SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE   -- canonicalized: always 'SQL', never 'sql' / 'Sql'
);

CREATE TABLE job_skills (
    job_id          INTEGER REFERENCES job_postings(job_id) ON DELETE CASCADE,
    skill_id        INTEGER REFERENCES skills(skill_id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, skill_id)
);

CREATE INDEX idx_job_postings_company ON job_postings(company_id);
CREATE INDEX idx_job_postings_level ON job_postings(level);
CREATE INDEX idx_job_skills_skill ON job_skills(skill_id);
```

### Git setup + branching
```bash
git init
git branch -M main
git remote add origin https://github.com/<you>/ph-job-market-pipeline.git

git checkout -b feature/db-schema
# ... add the files above ...
git add .
git commit -m "Add DB schema, docker-compose, and project scaffolding"
git push -u origin feature/db-schema
# open a PR on GitHub, merge into main, then:
git checkout main && git pull && git branch -d feature/db-schema
```
Suggested branch per phase: `feature/db-schema` (Wk1) → `feature/scraper` (Wk2) → `feature/transform-load` (Wk3) → `feature/analytics-charts` (Wk4) → `feature/readme-polish` (Wk5). Merge each via PR even solo — the PR history is itself part of the portfolio signal.

### Week 1 exit checklist
- [ ] `docker compose up -d` starts Postgres and auto-applies `schema.sql`
- [ ] `psql` (or your DB client) shows all 4 tables
- [ ] At least one PR merged into `main`

---

## Phase 2 (Week 2) — Extract

**Timebox: 3 days.** If your chosen source isn't yielding results by day 3, fall back to Phase 0's smaller-sample plan — don't let this phase eat Week 3.

### `src/scrape.py`
```python
"""
scrape.py — Extract job postings from your chosen source.

The selectors below are PLACEHOLDERS. Every job site's DOM differs and changes over
time — inspect your actual target (DevTools → Inspect Element) and replace every
TODO before running this for real.

Etiquette:
- Check the target's robots.txt first.
- Delays between requests are already built in below — don't remove them.
- A realistic User-Agent is standard practice, not evasion.
- Consistently blocked? That's your Phase 0 fallback trigger — not a cue to add
  proxy rotation or CAPTCHA-solving. That crosses from scraping into circumventing
  a site's protections, which isn't worth it for a portfolio project.
"""

import json
import random
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

SITE_DOMAIN = "https://example-job-site.ph"       # TODO: your source's domain
BASE_URL = f"{SITE_DOMAIN}/jobs?q=data"            # TODO: your source's search URL
OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TARGET_COUNT = 200          # drop to 50-80 if your source is less cooperative
DELAY_RANGE = (2, 5)        # seconds between page loads


def scrape_listing_page(page, url: str) -> list[dict]:
    page.goto(url, wait_until="networkidle")

    job_cards = page.query_selector_all(".job-card")   # TODO: real container selector

    results = []
    for card in job_cards:
        title = card.query_selector(".job-title")          # TODO
        company = card.query_selector(".company-name")     # TODO
        location = card.query_selector(".job-location")    # TODO
        salary = card.query_selector(".salary-range")      # TODO — often missing, handle None
        posted = card.query_selector(".posted-date")       # TODO
        link = card.query_selector("a")                    # TODO

        href = link.get_attribute("href") if link else None
        results.append({
            "title": title.inner_text().strip() if title else None,
            "company": company.inner_text().strip() if company else None,
            "location": location.inner_text().strip() if location else None,
            "salary_raw": salary.inner_text().strip() if salary else None,
            "posted_raw": posted.inner_text().strip() if posted else None,
            "source_url": urljoin(SITE_DOMAIN, href) if href else None,
        })
    return results


def scrape_job_detail(page, url: str) -> dict:
    page.goto(url, wait_until="networkidle")
    desc_el = page.query_selector(".job-description")   # TODO: real description selector
    return {"raw_description": desc_el.inner_text().strip() if desc_el else ""}


def run():
    all_jobs = []
    page_num = 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
            )
        )
        page = context.new_page()

        while len(all_jobs) < TARGET_COUNT:
            url = f"{BASE_URL}&page={page_num}"    # TODO: your source's pagination pattern
            listing_jobs = scrape_listing_page(page, url)

            if not listing_jobs:
                print(f"No more results at page {page_num}, stopping.")
                break

            for job in listing_jobs:
                if job["source_url"]:
                    job.update(scrape_job_detail(page, job["source_url"]))
                    time.sleep(random.uniform(*DELAY_RANGE))

            all_jobs.extend(listing_jobs)
            print(f"Page {page_num}: {len(listing_jobs)} jobs (total: {len(all_jobs)})")
            page_num += 1
            time.sleep(random.uniform(*DELAY_RANGE))

        browser.close()

    out_path = OUTPUT_DIR / f"raw_jobs_{date.today().isoformat()}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_jobs[:TARGET_COUNT], f, ensure_ascii=False, indent=2)
    print(f"Saved {len(all_jobs[:TARGET_COUNT])} postings to {out_path}")


if __name__ == "__main__":
    run()
```

### Week 2 exit checklist
- [ ] `python src/scrape.py` runs end-to-end unattended
- [ ] `data/raw/` has JSON with at least 50 postings (200 if your source cooperates)
- [ ] Missing fields (no salary, no description) don't crash the run

---

## Phase 3 (Week 3) — Transform + Load

### `src/transform_load.py`
```python
"""
transform_load.py — Clean raw scraped JSON, normalize fields, load into PostgreSQL.
Run after scrape.py has produced at least one file in data/raw/.
"""

import json
import os
import re
from datetime import datetime, timedelta
from glob import glob

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DB_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}"
    f"/{os.getenv('POSTGRES_DB')}"
)
engine = create_engine(DB_URL)

# Canonical skills — extend this after eyeballing your first real scrape.
SKILL_PATTERNS = {
    r"\bsql\b": "SQL", r"\bpython\b": "Python", r"\bpandas\b": "Pandas",
    r"\bpostgres(ql)?\b": "PostgreSQL", r"\baws\b": "AWS",
    r"\bgcp\b|google cloud": "GCP", r"\bazure\b": "Azure", r"\bdocker\b": "Docker",
    r"\bairflow\b": "Airflow", r"\bspark\b": "Spark", r"\betl\b": "ETL",
    r"\bexcel\b": "Excel", r"\btableau\b": "Tableau", r"\bpower ?bi\b": "Power BI",
}

LEVEL_PATTERNS = {
    "entry": [r"\bjunior\b", r"\bentry.?level\b", r"\bfresh graduate\b", r"\bno experience\b"],
    "senior": [r"\bsenior\b", r"\blead\b", r"\bmanager\b", r"\b[5-9]\+? years\b"],
}

# Manual industry tagging for known PH employers — full NLP classification is out of
# scope for this project; a manual lookup for whichever companies actually show up
# in your data is honest, simple, and good enough for Query 4. Extend after Wk2.
INDUSTRY_LOOKUP = {
    "Accenture": "BPO/Consulting",
    "Globe Telecom": "Telco",
    "ING": "Banking",
    # add more once you see who's actually in your scraped data
}


def load_raw_files() -> pd.DataFrame:
    files = sorted(glob("data/raw/*.json"))
    if not files:
        raise FileNotFoundError("No raw JSON in data/raw/ — run scrape.py first.")
    records = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            records.extend(json.load(fh))
    df = pd.DataFrame(records)
    print(f"Loaded {len(df)} raw records from {len(files)} file(s).")
    return df


def parse_salary(raw):
    if not isinstance(raw, str):
        return None
    nums = [int(n) for n in re.findall(r"\d+", raw.replace(",", ""))]
    if not nums:
        return None   # e.g. "Negotiable" — excluded from salary queries, noted in README
    return sum(nums[:2]) / len(nums[:2])   # midpoint if a range, the value itself if single


def parse_posted_date(raw):
    """Best-effort parse of relative strings like '3 days ago'. Not required for the
    5 core queries — included for completeness. Returns None if unparseable."""
    if not isinstance(raw, str):
        return None
    raw = raw.lower().strip()
    if "today" in raw:
        return datetime.today().date()
    if (m := re.search(r"(\d+)\s*day", raw)):
        return (datetime.today() - timedelta(days=int(m.group(1)))).date()
    if (m := re.search(r"(\d+)\s*month", raw)):
        return (datetime.today() - timedelta(days=int(m.group(1)) * 30)).date()
    return None


def classify_level(row):
    blob = f"{row.get('title', '')} {row.get('raw_description', '')}".lower()
    for pattern in LEVEL_PATTERNS["entry"]:
        if re.search(pattern, blob):
            return "entry"
    for pattern in LEVEL_PATTERNS["senior"]:
        if re.search(pattern, blob):
            return "senior"
    return "mid" if "experience" in blob else "unspecified"


def extract_skills(row):
    blob = f"{row.get('title', '')} {row.get('raw_description', '')}".lower()
    return [name for pattern, name in SKILL_PATTERNS.items() if re.search(pattern, blob)]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset="source_url").copy()
    print(f"Dropped {before - len(df)} duplicate postings.")

    df = df.dropna(subset=["title", "company"])

    df["salary_monthly_php"] = df.get("salary_raw", pd.Series(dtype=object)).apply(parse_salary)
    df["posted_date"] = df.get("posted_raw", pd.Series(dtype=object)).apply(parse_posted_date)
    df["level"] = df.apply(classify_level, axis=1)
    df["skills"] = df.apply(extract_skills, axis=1)

    missing_pct = df["salary_monthly_php"].isna().mean() * 100
    print(f"{missing_pct:.1f}% of postings have no parseable salary — "
          f"note this in your README's data-quality section.")
    return df


def tag_industry(company_name: str) -> str:
    return INDUSTRY_LOOKUP.get(company_name, "Unclassified")


def load_to_postgres(df: pd.DataFrame):
    with engine.begin() as conn:
        for _, row in df.iterrows():
            company_id = conn.execute(
                text("""
                    INSERT INTO companies (name, industry)
                    VALUES (:name, :industry)
                    ON CONFLICT (name) DO UPDATE SET industry = EXCLUDED.industry
                    RETURNING company_id
                """),
                {"name": row["company"], "industry": tag_industry(row["company"])},
            ).scalar()

            job_id = conn.execute(
                text("""
                    INSERT INTO job_postings
                        (title, company_id, location, salary_monthly_php, level,
                         posted_date, source_url, raw_description)
                    VALUES
                        (:title, :company_id, :location, :salary, :level,
                         :posted_date, :source_url, :desc)
                    ON CONFLICT (source_url) DO NOTHING
                    RETURNING job_id
                """),
                {
                    "title": row["title"], "company_id": company_id,
                    "location": row.get("location"), "salary": row.get("salary_monthly_php"),
                    "level": row.get("level", "unspecified"), "posted_date": row.get("posted_date"),
                    "source_url": row.get("source_url"), "desc": row.get("raw_description"),
                },
            ).scalar()

            if job_id is None:
                continue   # already loaded in a prior run

            for skill_name in row.get("skills", []):
                skill_id = conn.execute(
                    text("""
                        INSERT INTO skills (name) VALUES (:name)
                        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                        RETURNING skill_id
                    """),
                    {"name": skill_name},
                ).scalar()
                conn.execute(
                    text("""
                        INSERT INTO job_skills (job_id, skill_id)
                        VALUES (:job_id, :skill_id) ON CONFLICT DO NOTHING
                    """),
                    {"job_id": job_id, "skill_id": skill_id},
                )
    print("Load complete.")


if __name__ == "__main__":
    raw_df = load_raw_files()
    clean_df = clean(raw_df)
    load_to_postgres(clean_df)
```

### `tests/validate_load.py`
```python
"""validate_load.py — Sanity checks after transform_load.py runs (Phase 3 exit criteria)."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DB_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}"
    f"/{os.getenv('POSTGRES_DB')}"
)
engine = create_engine(DB_URL)

CHECKS = [
    ("Row count: job_postings", "SELECT COUNT(*) FROM job_postings", lambda n: n > 0),
    ("Row count: skills", "SELECT COUNT(*) FROM skills", lambda n: n > 0),
    ("Row count: job_skills", "SELECT COUNT(*) FROM job_skills", lambda n: n > 0),
    ("No orphaned job_skills (job_id)",
     """SELECT COUNT(*) FROM job_skills js LEFT JOIN job_postings jp
        ON jp.job_id = js.job_id WHERE jp.job_id IS NULL""", lambda n: n == 0),
    ("No orphaned job_skills (skill_id)",
     """SELECT COUNT(*) FROM job_skills js LEFT JOIN skills s
        ON s.skill_id = js.skill_id WHERE s.skill_id IS NULL""", lambda n: n == 0),
    ("No null titles", "SELECT COUNT(*) FROM job_postings WHERE title IS NULL", lambda n: n == 0),
]


def run():
    passed, failed = 0, 0
    with engine.connect() as conn:
        for label, query, check in CHECKS:
            result = conn.execute(text(query)).scalar()
            ok = check(result)
            print(f"[{'PASS' if ok else 'FAIL'}] {label}: {result}")
            passed += ok
            failed += not ok
    print(f"\n{passed} passed, {failed} failed.")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
```

### Week 3 exit checklist
- [ ] `python src/transform_load.py` runs cleanly against real scraped data
- [ ] `python tests/validate_load.py` — all checks pass
- [ ] Missing-salary percentage noted somewhere for the README's data-quality section

---

## Phase 4 (Week 4) — Analyze + Visualize

### `queries/analysis.sql`
```sql
-- ============================================================
-- Query 1: Top 10 most demanded skills
-- ============================================================
SELECT s.name AS skill, COUNT(*) AS posting_count
FROM job_skills js
JOIN skills s ON s.skill_id = js.skill_id
GROUP BY s.name
ORDER BY posting_count DESC
LIMIT 10;


-- ============================================================
-- Query 2: Average salary by skill
-- ============================================================
SELECT s.name AS skill,
       ROUND(AVG(jp.salary_monthly_php), 2) AS avg_salary_php,
       COUNT(*) AS postings_with_salary
FROM job_skills js
JOIN skills s ON s.skill_id = js.skill_id
JOIN job_postings jp ON jp.job_id = js.job_id
WHERE jp.salary_monthly_php IS NOT NULL
GROUP BY s.name
ORDER BY avg_salary_php DESC
LIMIT 10;


-- ============================================================
-- Query 3: Top 10 hiring companies for data roles (CTE)
-- ============================================================
WITH data_roles AS (
    SELECT * FROM job_postings
    WHERE title ILIKE '%data%' OR title ILIKE '%analyst%'
       OR title ILIKE '%engineer%' OR title ILIKE '%scientist%'
)
SELECT c.name AS company, COUNT(*) AS data_role_postings
FROM data_roles dr
JOIN companies c ON c.company_id = dr.company_id
GROUP BY c.name
ORDER BY data_role_postings DESC
LIMIT 10;


-- ============================================================
-- Query 4: Salary rank per company within industry (window function)
-- ============================================================
WITH company_avg_salary AS (
    SELECT c.company_id, c.name AS company, c.industry,
           ROUND(AVG(jp.salary_monthly_php), 2) AS avg_salary
    FROM job_postings jp
    JOIN companies c ON c.company_id = jp.company_id
    WHERE jp.salary_monthly_php IS NOT NULL
    GROUP BY c.company_id, c.name, c.industry
)
SELECT company, industry, avg_salary,
       RANK() OVER (PARTITION BY industry ORDER BY avg_salary DESC) AS rank_in_industry
FROM company_avg_salary
ORDER BY industry, rank_in_industry;


-- ============================================================
-- Query 5: Entry-level vs mid-level skill gap (CASE WHEN pivot)
-- ============================================================
SELECT s.name AS skill,
       SUM(CASE WHEN jp.level = 'entry' THEN 1 ELSE 0 END) AS entry_postings,
       SUM(CASE WHEN jp.level = 'mid'   THEN 1 ELSE 0 END) AS mid_postings,
       SUM(CASE WHEN jp.level = 'mid'   THEN 1 ELSE 0 END)
         - SUM(CASE WHEN jp.level = 'entry' THEN 1 ELSE 0 END) AS gap
FROM job_skills js
JOIN skills s ON s.skill_id = js.skill_id
JOIN job_postings jp ON jp.job_id = js.job_id
WHERE jp.level IN ('entry', 'mid')
GROUP BY s.name
ORDER BY gap DESC;
```
A positive `gap` in Query 5 means a skill shows up more at mid-level than entry-level — a real, interpretable finding for your README ("X is a mid-career skill gate, not an entry requirement").

### `src/generate_charts.py`
```python
"""generate_charts.py — Produce the 3 README charts from the queries above."""

import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
DB_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}"
    f"/{os.getenv('POSTGRES_DB')}"
)
engine = create_engine(DB_URL)
CHARTS_DIR = Path("charts")
CHARTS_DIR.mkdir(exist_ok=True)


def chart_top_skills():
    df = pd.read_sql("""
        SELECT s.name AS skill, COUNT(*) AS postings
        FROM job_skills js JOIN skills s ON s.skill_id = js.skill_id
        GROUP BY s.name ORDER BY postings DESC LIMIT 10
    """, engine)
    plt.figure(figsize=(9, 5))
    plt.barh(df["skill"][::-1], df["postings"][::-1], color="#2563eb")
    plt.xlabel("Number of postings")
    plt.title("Top 10 Most Demanded Skills — PH Job Market")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "top_skills.png", dpi=150)
    plt.close()


def chart_avg_salary_by_skill():
    df = pd.read_sql("""
        SELECT s.name AS skill, ROUND(AVG(jp.salary_monthly_php), 0) AS avg_salary
        FROM job_skills js
        JOIN skills s ON s.skill_id = js.skill_id
        JOIN job_postings jp ON jp.job_id = js.job_id
        WHERE jp.salary_monthly_php IS NOT NULL
        GROUP BY s.name ORDER BY avg_salary DESC LIMIT 10
    """, engine)
    plt.figure(figsize=(9, 5))
    plt.barh(df["skill"][::-1], df["avg_salary"][::-1], color="#16a34a")
    plt.xlabel("Average monthly salary (PHP)")
    plt.title("Average Salary by Skill — PH Job Market")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "avg_salary_by_skill.png", dpi=150)
    plt.close()


def chart_top_companies():
    df = pd.read_sql("""
        WITH data_roles AS (
            SELECT * FROM job_postings
            WHERE title ILIKE '%data%' OR title ILIKE '%analyst%'
               OR title ILIKE '%engineer%' OR title ILIKE '%scientist%'
        )
        SELECT c.name AS company, COUNT(*) AS postings
        FROM data_roles dr JOIN companies c ON c.company_id = dr.company_id
        GROUP BY c.name ORDER BY postings DESC LIMIT 10
    """, engine)
    plt.figure(figsize=(9, 5))
    plt.barh(df["company"][::-1], df["postings"][::-1], color="#d97706")
    plt.xlabel("Data-role postings")
    plt.title("Top Hiring Companies for Data Roles — PH")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "top_companies.png", dpi=150)
    plt.close()


if __name__ == "__main__":
    chart_top_skills()
    chart_avg_salary_by_skill()
    chart_top_companies()
    print(f"Charts saved to {CHARTS_DIR}/")
```

### Week 4 exit checklist
- [ ] All 5 queries run and return sensible (non-empty, non-nonsensical) results
- [ ] 3 PNGs generated in `charts/`
- [ ] README first draft written with **real** numbers plugged in, not placeholders

---

## Phase 5 (Week 5) — Polish + Ship

### `README.md`
```markdown
# PH Tech Job Market Analytics Pipeline

An ETL pipeline that scrapes tech job postings from [your source], stores them in a
PostgreSQL data warehouse, and answers: **what skills and companies dominate the PH
data job market?**

## Key Findings
- SQL + Python appear in __% of all data job postings
- Average salary for roles requiring [skill]: ₱__,000/month
- Top hiring companies: __, __, __

## Architecture

\`\`\`mermaid
flowchart LR
    A[Job Site] -->|Playwright scraper| B[Raw JSON /data/raw]
    B -->|pandas clean + normalize| C[Transformed DataFrame]
    C -->|SQLAlchemy load| D[(PostgreSQL)]
    D -->|SQL analytics| E[Query Results]
    E -->|matplotlib| F[Charts]
\`\`\`

## Tech Stack
Python 3.12 · Playwright/BeautifulSoup · pandas · PostgreSQL · SQLAlchemy · matplotlib · Docker · Git

## Data Source & Scope
[Document your Phase 0 decision: which source, how many postings, why]

## How to Run
1. Clone the repo
2. Copy `.env.example` to `.env` and fill in credentials
3. `docker compose up -d`
4. `pip install -r requirements.txt`
5. `playwright install chromium`
6. `python src/scrape.py`
7. `python src/transform_load.py`
8. `python tests/validate_load.py`
9. `python src/generate_charts.py`
10. Open `queries/analysis.sql` in your DB client, or run each query against the running container

## Data Quality Notes
[e.g. "X% of postings had no listed salary and were excluded from salary-based queries"]

## License
MIT
```
GitHub renders Mermaid diagrams natively in README.md — no PNG export needed unless you want one for other platforms too.

### Ship commands
```bash
# Final cleanup
git checkout main && git pull
git branch                       # confirm no stale feature branches left
git add . && git commit -m "Final README polish and architecture diagram"
git push

# Tag the release
git tag -a v1.0 -m "PH Job Market Analytics Pipeline — v1.0"
git push origin v1.0
```
Then pin the repo on your GitHub profile.

### Final exit checklist
- [ ] `docker compose up -d` + the numbered run steps work on a clean clone
- [ ] README leads with real findings, has the architecture diagram, documents scope decisions
- [ ] `v1.0` tagged, repo pinned

---

## Appendix A — Troubleshooting

- **Port 5432 already in use** → another Postgres is running locally; change the host-side port in `docker-compose.yml` (e.g. `"5433:5432"`) and update `.env`.
- **`playwright` errors about missing browsers** → run `playwright install chromium`.
- **SQLAlchemy "connection refused"** → confirm `docker compose ps` shows the container running, and that `.env` values match `docker-compose.yml`'s environment block.
- **Scraper returns 0 results** → selectors are likely stale (site changed its DOM) or you're being blocked (check for 403/429 responses). Re-inspect the live page before assuming it's a code bug.
- **Schema changes not showing up** → the init script only runs once; `docker compose down -v` then `up -d` to reset the volume.

## Appendix B — Risk Reminders

- **Week 2 scraper fragility** is still the single biggest point of failure — the 3-day timebox exists to protect Week 3, not to be optional.
- **Industry field for Query 4** needs real values in `INDUSTRY_LOOKUP` — it defaults to `'Unclassified'`, which will make Query 4 boring if you forget to populate it after Week 2.
- **Salary parsing** is a heuristic (`parse_salary`), not a guarantee — spot-check a handful of rows against the raw JSON before trusting Query 2 and 4's numbers.
- **Exam-week overlap** — see the timing flag under Prerequisites. Check your actual Prelim schedule against Week 4–5 now, not during execution.
