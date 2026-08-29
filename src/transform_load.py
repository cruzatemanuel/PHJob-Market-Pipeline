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
