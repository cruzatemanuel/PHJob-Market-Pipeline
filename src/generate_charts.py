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
