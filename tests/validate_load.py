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
