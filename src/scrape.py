"""Collect Philippine job-posting snapshots from Jooble's official REST API.

Mock mode creates deterministic data for local testing. Jooble mode sends polite,
bounded API requests and saves raw, schema-compatible job records for the ETL
pipeline. The API key stays in ``.env`` and is never written to output or logs.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # Mock mode still works before the full requirements install finishes.
    load_dotenv = None
else:
    load_dotenv()


DEFAULT_OUTPUT_DIR = Path("data/raw")
DEFAULT_COUNT = 50
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RESULTS_PER_PAGE = 20
DEFAULT_MAX_PAGES_PER_QUERY = 3
DEFAULT_REQUEST_DELAY = 0.5
DEFAULT_API_BASE_URL = "https://ph.jooble.org/api"
DEFAULT_KEYWORDS = "data analyst,data engineer,business intelligence,software engineer"
DEFAULT_LOCATIONS = "Philippines,Metro Manila,Cebu"


class JoobleApiError(RuntimeError):
    """Raised for a failed Jooble request without leaking the API key."""


@dataclass(frozen=True)
class JoobleConfig:
    api_key: str
    api_base_url: str
    keywords: tuple[str, ...]
    locations: tuple[str, ...]
    results_per_page: int
    max_pages_per_query: int
    timeout_seconds: int
    request_delay: float

    @property
    def endpoint(self) -> str:
        return f"{self.api_base_url.rstrip('/')}/{quote(self.api_key, safe='')}"


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_csv(value: str, name: str) -> tuple[str, ...]:
    values = tuple(item.strip() for item in value.split(",") if item.strip())
    if not values:
        raise ValueError(f"{name} must contain at least one value.")
    return values


def env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error


def env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number.") from error


def generate_mock_jobs(count: int, seed: int) -> list[dict[str, str | None]]:
    """Create deterministic, schema-compatible records for local pipeline testing."""
    if count < 1:
        raise ValueError("count must be at least 1")

    rng = random.Random(seed)
    roles = [
        ("Data Analyst", "SQL, Python, Excel, Tableau, and Power BI."),
        ("Data Engineer", "Python, SQL, Airflow, AWS, Docker, and Spark."),
        ("Business Intelligence Analyst", "SQL, Excel, Power BI, and Tableau."),
        ("Cloud Data Engineer", "Python, PostgreSQL, GCP, ETL, and Docker."),
    ]
    companies = ["Northstar PH", "Bayan Analytics", "Manila Data Works", "Cebu Cloud Labs"]
    locations = ["Makati, Philippines", "Taguig, Philippines", "Cebu City, Philippines", "Remote, Philippines"]
    levels = ["Entry Level", "Mid-level", "Senior", "Mid-level"]
    jobs: list[dict[str, str | None]] = []

    for index in range(1, count + 1):
        role, skills = roles[(index - 1) % len(roles)]
        level = levels[(index - 1) % len(levels)]
        low_salary = 30_000 + ((index - 1) % 6) * 10_000
        high_salary = low_salary + 20_000
        jobs.append(
            {
                "title": role,
                "company": companies[(index - 1) % len(companies)],
                "location": locations[(index - 1) % len(locations)],
                "salary_raw": f"PHP {low_salary:,} - PHP {high_salary:,} per month",
                "posted_raw": f"{rng.randint(1, 28)} days ago",
                "source_url": f"mock://ph-job-market/{index:04d}",
                "raw_description": f"{level} {role} role. Requires {skills}",
                "source": "Synthetic mock data",
                "scraped_at": "2024-01-01T00:00:00Z",
            }
        )
    return jobs


def jooble_payload(keyword: str, location: str, page: int, results_per_page: int) -> dict[str, str | int | bool]:
    """Build one documented Jooble request payload."""
    return {
        "keywords": keyword,
        "location": location,
        "page": page,
        "ResultOnPage": results_per_page,
        "companysearch": False,
    }


def request_jooble_page(
    session: requests.Session,
    config: JoobleConfig,
    keyword: str,
    location: str,
    page: int,
) -> dict[str, Any]:
    """Request one Jooble page and return its JSON object without exposing credentials."""
    try:
        response = session.post(
            config.endpoint,
            json=jooble_payload(keyword, location, page, config.results_per_page),
            headers={"Accept": "application/json"},
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else "unknown"
        raise JoobleApiError(f"Jooble API returned HTTP {status}. Check the regional key and API quota.") from error
    except requests.RequestException as error:
        raise JoobleApiError(f"Jooble API request failed ({type(error).__name__}). Check the network connection.") from error

    try:
        payload = response.json()
    except ValueError as error:
        raise JoobleApiError("Jooble API returned invalid JSON.") from error
    if not isinstance(payload, dict):
        raise JoobleApiError("Jooble API returned an unexpected response format.")
    return payload


def string_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def normalize_jooble_job(job: Any, query_keyword: str, query_location: str) -> dict[str, str | None] | None:
    """Map a Jooble job object to the raw-record contract used by transform_load.py."""
    if not isinstance(job, dict):
        return None

    title = string_or_none(job.get("title"))
    company = string_or_none(job.get("company"))
    source_url = string_or_none(job.get("link"))
    if not title or not company or not source_url:
        return None

    source = string_or_none(job.get("source")) or "Jooble"
    return {
        "title": title,
        "company": company,
        "location": string_or_none(job.get("location")),
        "salary_raw": string_or_none(job.get("salary")),
        "posted_raw": string_or_none(job.get("updated")),
        "source_url": source_url,
        "raw_description": string_or_none(job.get("snippet")) or "",
        "source": f"Jooble / {source}",
        "source_job_id": str(job["id"]) if job.get("id") is not None else None,
        "job_type": string_or_none(job.get("type")),
        "query_keyword": query_keyword,
        "query_location": query_location,
        "scraped_at": utc_timestamp(),
    }


def collect_jooble_jobs(
    config: JoobleConfig,
    max_records: int,
    session: requests.Session | None = None,
) -> list[dict[str, str | None]]:
    """Collect a bounded, de-duplicated Jooble snapshot across the configured scope."""
    owns_session = session is None
    session = session or requests.Session()
    jobs: list[dict[str, str | None]] = []
    seen_urls: set[str] = set()
    request_count = 0

    try:
        for keyword in config.keywords:
            for location in config.locations:
                for page in range(1, config.max_pages_per_query + 1):
                    payload = request_jooble_page(session, config, keyword, location, page)
                    request_count += 1
                    raw_jobs = payload.get("jobs", [])
                    if not isinstance(raw_jobs, list):
                        raise JoobleApiError("Jooble API response field 'jobs' must be a list.")

                    added = 0
                    for raw_job in raw_jobs:
                        job = normalize_jooble_job(raw_job, keyword, location)
                        if job is None or job["source_url"] in seen_urls:
                            continue
                        seen_urls.add(job["source_url"])
                        jobs.append(job)
                        added += 1
                        if len(jobs) >= max_records:
                            break

                    print(
                        f"{keyword!r} in {location!r}, page {page}: "
                        f"{added} new posting(s) (total: {len(jobs)})."
                    )
                    if len(jobs) >= max_records:
                        print(f"Jooble API requests used in this run: {request_count}.")
                        return jobs
                    total_count = payload.get("totalCount")
                    is_last_page = (
                        not raw_jobs
                        or len(raw_jobs) < config.results_per_page
                        or (isinstance(total_count, int) and page * config.results_per_page >= total_count)
                    )
                    if is_last_page:
                        break
                    if config.request_delay:
                        time.sleep(config.request_delay)
    finally:
        if owns_session:
            session.close()

    print(f"Jooble API requests used in this run: {request_count}.")
    return jobs


def write_snapshot(jobs: list[dict[str, str | None]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    output_path = output_dir / f"raw_jobs_{timestamp}.json"
    output_path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def jooble_config_from_args(args: argparse.Namespace) -> JoobleConfig:
    api_key = os.getenv("JOOBLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("JOOBLE_API_KEY is required for --mode jooble. Add your Philippines-specific key to .env.")

    keywords = parse_csv(args.keywords or os.getenv("JOOBLE_KEYWORDS", DEFAULT_KEYWORDS), "keywords")
    locations = parse_csv(args.locations or os.getenv("JOOBLE_LOCATIONS", DEFAULT_LOCATIONS), "locations")
    results_per_page = args.results_per_page or env_int("JOOBLE_RESULTS_PER_PAGE", DEFAULT_RESULTS_PER_PAGE)
    max_pages = args.max_pages_per_query or env_int("JOOBLE_MAX_PAGES_PER_QUERY", DEFAULT_MAX_PAGES_PER_QUERY)
    request_delay = args.request_delay if args.request_delay is not None else env_float("JOOBLE_REQUEST_DELAY", DEFAULT_REQUEST_DELAY)

    if results_per_page < 1 or max_pages < 1:
        raise ValueError("Jooble page-size and page-limit values must be at least 1.")
    if request_delay < 0:
        raise ValueError("JOOBLE_REQUEST_DELAY must not be negative.")

    return JoobleConfig(
        api_key=api_key,
        api_base_url=os.getenv("JOOBLE_API_BASE_URL", DEFAULT_API_BASE_URL).strip(),
        keywords=keywords,
        locations=locations,
        results_per_page=results_per_page,
        max_pages_per_query=max_pages,
        timeout_seconds=args.timeout_seconds,
        request_delay=request_delay,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect a raw PH job-market JSON snapshot.")
    parser.add_argument("--mode", choices=("mock", "jooble"), default="mock", help="Use reproducible mock data or the Jooble API (default: mock).")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help=f"Maximum records to write (default: {DEFAULT_COUNT}).")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"Snapshot directory (default: {DEFAULT_OUTPUT_DIR}).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for mock data (default: 42).")
    parser.add_argument("--keywords", help="Comma-separated Jooble keywords; overrides JOOBLE_KEYWORDS.")
    parser.add_argument("--locations", help="Comma-separated Jooble locations; overrides JOOBLE_LOCATIONS.")
    parser.add_argument("--results-per-page", type=int, help="Jooble results per request; overrides JOOBLE_RESULTS_PER_PAGE.")
    parser.add_argument("--max-pages-per-query", type=int, help="Jooble page cap per keyword/location; overrides JOOBLE_MAX_PAGES_PER_QUERY.")
    parser.add_argument("--request-delay", type=float, help="Seconds between Jooble requests; overrides JOOBLE_REQUEST_DELAY.")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS, help=f"HTTP request timeout (default: {DEFAULT_TIMEOUT_SECONDS}).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.count < 1:
        raise SystemExit("--count must be at least 1")
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be at least 1")

    try:
        jobs = generate_mock_jobs(args.count, args.seed) if args.mode == "mock" else collect_jooble_jobs(jooble_config_from_args(args), args.count)
    except (JoobleApiError, ValueError) as error:
        raise SystemExit(str(error)) from error

    output_path = write_snapshot(jobs, args.output_dir)
    print(f"Saved {len(jobs)} posting(s) to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
