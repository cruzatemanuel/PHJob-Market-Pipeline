#!/usr/bin/env python3
"""
PH Job Market Chart & Insights Visualization Engine
---------------------------------------------------
Queries PostgreSQL or SQLite database for aggregated market statistics and 
generates publication-ready PNG graphics in charts/.

Usage:
    python src/generate_charts.py [--outdir charts]
"""

import argparse
import logging
import os
import sqlite3
import sys
from typing import Tuple

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

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
logger = logging.getLogger("generate_charts")


# Styling Theme setup
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
COLOR_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]


def get_db_connection() -> Tuple[object, str]:
    """Connects to PostgreSQL or falls back to SQLite."""
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "ph_job_market")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres_pass")
    sqlite_db = "ph_job_market.db"

    try:
        import psycopg2
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password,
            connect_timeout=2
        )
        return conn, "postgres"
    except Exception:
        if os.path.exists(sqlite_db):
            conn = sqlite3.connect(sqlite_db)
            return conn, "sqlite"
        else:
            raise FileNotFoundError("Neither PostgreSQL server nor 'ph_job_market.db' fallback was found.")


def generate_top_skills_chart(conn, outdir: str):
    """Generates bar chart of top demanded skills."""
    query = """
        SELECT s.skill_name, s.category, COUNT(js.job_id) as job_count
        FROM skills s
        JOIN job_skills js ON s.skill_id = js.skill_id
        GROUP BY s.skill_name, s.category
        ORDER BY job_count DESC
        LIMIT 12;
    """
    df = pd.read_sql_query(query, conn)
    
    if df.empty:
        logger.warning("No data found for top skills chart.")
        return

    plt.figure(figsize=(10, 6))
    ax = sns.barplot(
        data=df, 
        x="job_count", 
        y="skill_name", 
        hue="category", 
        dodge=False, 
        palette="crest"
    )
    plt.title("Top Demanded Skills in Philippine Job Postings", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Number of Job Postings", fontsize=11)
    plt.ylabel("Skill / Technology", fontsize=11)
    
    # Add data labels
    for p in ax.patches:
        width = p.get_width()
        if width > 0:
            ax.annotate(
                f"{int(width)}", 
                (width + 0.2, p.get_y() + p.get_height() / 2.0),
                ha="left", va="center", fontsize=10, fontweight="semibold"
            )

    plt.tight_layout()
    chart_path = os.path.join(outdir, "top_demanded_skills.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    logger.info(f"Generated chart: '{chart_path}'")


def generate_salary_experience_chart(conn, outdir: str):
    """Generates chart showing average monthly PHP salary by experience level."""
    query = """
        SELECT experience_level, AVG(salary_php_equiv) as avg_salary_php, COUNT(*) as count
        FROM jobs
        WHERE salary_php_equiv IS NOT NULL
        GROUP BY experience_level
        ORDER BY avg_salary_php ASC;
    """
    df = pd.read_sql_query(query, conn)
    
    if df.empty:
        logger.warning("No salary data available for salary experience chart.")
        return

    plt.figure(figsize=(9, 5))
    ax = sns.barplot(
        data=df, 
        x="experience_level", 
        y="avg_salary_php", 
        hue="experience_level",
        legend=False,
        palette="Blues_d"
    )
    plt.title("Average Monthly Salary by Experience Level (PHP Equivalent)", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Experience Level", fontsize=11)
    plt.ylabel("Average Monthly Salary (₱ PHP)", fontsize=11)

    for p in ax.patches:
        height = p.get_height()
        if height > 0:
            ax.annotate(
                f"₱{height:,.0f}", 
                (p.get_x() + p.get_width() / 2.0, height + 1500),
                ha="center", va="bottom", fontsize=10, fontweight="bold"
            )

    plt.tight_layout()
    chart_path = os.path.join(outdir, "salary_by_role_experience.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    logger.info(f"Generated chart: '{chart_path}'")


def generate_work_setup_chart(conn, outdir: str):
    """Generates donut chart of work setup distribution (Remote vs Hybrid vs On-site)."""
    query = """
        SELECT work_setup, COUNT(*) as count
        FROM jobs
        GROUP BY work_setup
        ORDER BY count DESC;
    """
    df = pd.read_sql_query(query, conn)

    if df.empty:
        logger.warning("No data found for work setup distribution.")
        return

    plt.figure(figsize=(7, 7))
    colors = ["#2b5c8f", "#4695d6", "#87ceeb", "#c0c0c0"]
    plt.pie(
        df["count"], 
        labels=df["work_setup"], 
        autopct="%1.1f%%", 
        startangle=140, 
        colors=colors[:len(df)],
        wedgeprops=dict(width=0.4, edgecolor="w")
    )
    plt.title("Philippine Tech Job Setup Breakdown (Remote vs On-site)", fontsize=14, fontweight="bold", pad=15)

    plt.tight_layout()
    chart_path = os.path.join(outdir, "work_setup_distribution.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    logger.info(f"Generated chart: '{chart_path}'")


def generate_hiring_hubs_chart(conn, outdir: str):
    """Generates bar chart of job distribution across PH Regions."""
    query = """
        SELECT region, COUNT(*) as job_count
        FROM jobs
        GROUP BY region
        ORDER BY job_count DESC;
    """
    df = pd.read_sql_query(query, conn)

    if df.empty:
        logger.warning("No data found for regional hiring hubs.")
        return

    plt.figure(figsize=(9, 5))
    ax = sns.barplot(
        data=df, 
        x="job_count", 
        y="region", 
        hue="region",
        legend=False,
        palette="viridis"
    )
    plt.title("Job Listing Volume by Philippine Hiring Region", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Number of Job Listings", fontsize=11)
    plt.ylabel("Region / Location Hub", fontsize=11)

    for p in ax.patches:
        width = p.get_width()
        if width > 0:
            ax.annotate(
                f"{int(width)}", 
                (width + 0.1, p.get_y() + p.get_height() / 2.0),
                ha="left", va="center", fontsize=10, fontweight="bold"
            )

    plt.tight_layout()
    chart_path = os.path.join(outdir, "hiring_hubs_map.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    logger.info(f"Generated chart: '{chart_path}'")


def main():
    parser = argparse.ArgumentParser(description="PH Job Market Visualization Engine")
    parser.add_argument("--outdir", type=str, default="charts", help="Output directory for PNG charts")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    conn, db_type = get_db_connection()
    logger.info(f"Generating market analytics charts using '{db_type}' connection...")

    generate_top_skills_chart(conn, args.outdir)
    generate_salary_experience_chart(conn, args.outdir)
    generate_work_setup_chart(conn, args.outdir)
    generate_hiring_hubs_chart(conn, args.outdir)

    conn.close()
    logger.info("All chart visual assets successfully generated in directory 'charts/'.")


if __name__ == "__main__":
    main()
