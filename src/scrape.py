"""Collect Philippine job-posting snapshots for the pipeline.

Use ``--mode mock`` for a reproducible offline dataset. Live collection is
source-agnostic: pass a JSON configuration file with a listing URL template and
the selectors calibrated for one job board. Do not use live mode until you have
checked that source's access rules and terms.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


DEFAULT_OUTPUT_DIR = Path("data/raw")
DEFAULT_COUNT = 50
DEFAULT_TIMEOUT_MS = 30_000
DEFAULT_USER_AGENT = "PHJobMarketPipeline/1.0 (educational data project)"
REQUIRED_SELECTORS = ("job_card", "title", "company", "link")


@dataclass(frozen=True)
class LiveScraperConfig:
    """Settings that vary by job board and are supplied after selector calibration."""

    source_name: str
    listing_url_template: str
    selectors: dict[str, str]
    timeout_ms: int = DEFAULT_TIMEOUT_MS

    def url_for_page(self, page_number: int) -> str:
        return self.listing_url_template.format(page=page_number)


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def text_or_none(locator: Any) -> str | None:
    """Return normalized locator text without allowing a missing field to stop a run."""
    if locator is None:
        return None
    try:
        value = locator.inner_text(timeout=1_000).strip()
    except Exception:  # An optional or changed page element is expected during scraping.
        return None
    return value or None


def attribute_or_none(locator: Any, attribute: str) -> str | None:
    if locator is None:
        return None
    try:
        return locator.get_attribute(attribute, timeout=1_000)
    except Exception:
        return None


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
    # A fixed collection time keeps mock-mode output reproducible for tests and demos.
    timestamp = "2024-01-01T00:00:00Z"
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
                "scraped_at": timestamp,
            }
        )
    return jobs


def load_live_config(config_path: Path) -> LiveScraperConfig:
    """Load and validate the source-specific configuration kept outside the scraper."""
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Scraper config not found: {config_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Scraper config is not valid JSON: {error}") from error

    if not isinstance(payload, dict):
        raise ValueError("Scraper config must be a JSON object.")

    source_name = payload.get("source_name")
    listing_url_template = payload.get("listing_url_template")
    selectors = payload.get("selectors")
    timeout_ms = payload.get("timeout_ms", DEFAULT_TIMEOUT_MS)

    if not isinstance(source_name, str) or not source_name.strip():
        raise ValueError("Scraper config requires a non-empty 'source_name'.")
    if not isinstance(listing_url_template, str) or "{page}" not in listing_url_template:
        raise ValueError("'listing_url_template' must include a '{page}' placeholder.")
    if not isinstance(selectors, dict):
        raise ValueError("Scraper config requires a 'selectors' object.")

    missing = [name for name in REQUIRED_SELECTORS if not isinstance(selectors.get(name), str)]
    if missing:
        raise ValueError(f"Scraper config is missing required selectors: {', '.join(missing)}")
    if not isinstance(timeout_ms, int) or timeout_ms < 1_000:
        raise ValueError("'timeout_ms' must be an integer of at least 1000.")

    clean_selectors = {
        name: selector.strip()
        for name, selector in selectors.items()
        if isinstance(selector, str) and selector.strip()
    }
    return LiveScraperConfig(
        source_name=source_name.strip(),
        listing_url_template=listing_url_template.strip(),
        selectors=clean_selectors,
        timeout_ms=timeout_ms,
    )


def element_text(card: Any, selector: str | None) -> str | None:
    return text_or_none(card.locator(selector).first) if selector else None


def scrape_listing_page(page: Any, config: LiveScraperConfig, page_number: int) -> list[dict[str, str | None]]:
    """Extract valid listing records from one result page without fetching details."""
    url = config.url_for_page(page_number)
    page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
    try:
        cards = page.locator(config.selectors["job_card"])
        cards.first.wait_for(state="attached", timeout=config.timeout_ms)
        card_count = cards.count()
    except Exception as error:
        print(f"Could not read listing page {page_number}: {error}", file=sys.stderr)
        return []

    records: list[dict[str, str | None]] = []
    for index in range(card_count):
        card = cards.nth(index)
        title = element_text(card, config.selectors.get("title"))
        company = element_text(card, config.selectors.get("company"))
        if not title or not company:
            continue

        link_selector = config.selectors.get("link")
        link = card.locator(link_selector).first if link_selector else None
        href = attribute_or_none(link, "href")
        if not href:
            continue
        records.append(
            {
                "title": title,
                "company": company,
                "location": element_text(card, config.selectors.get("location")),
                "salary_raw": element_text(card, config.selectors.get("salary")),
                "posted_raw": element_text(card, config.selectors.get("posted")),
                "source_url": urljoin(page.url, href),
                "raw_description": "",
                "source": config.source_name,
                "scraped_at": utc_timestamp(),
            }
        )
    return records


def scrape_job_detail(page: Any, source_url: str, config: LiveScraperConfig) -> str:
    """Fetch an optional job description, returning an empty string on a page error."""
    description_selector = config.selectors.get("description")
    if not description_selector:
        return ""
    try:
        page.goto(source_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
        return text_or_none(page.locator(description_selector).first) or ""
    except Exception as error:
        print(f"Could not fetch detail page {source_url}: {error}", file=sys.stderr)
        return ""


def run_live(config: LiveScraperConfig, count: int, min_delay: float, max_delay: float, headless: bool) -> list[dict[str, str | None]]:
    """Run the configured source scraper with modest, non-circumvention delays."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "Live mode requires Playwright. Install dependencies with "
            "'.venv/bin/python -m pip install -r requirements.txt'."
        ) from error

    jobs: list[dict[str, str | None]] = []
    seen_urls: set[str] = set()
    page_number = 1

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=DEFAULT_USER_AGENT)
        page = context.new_page()
        try:
            while len(jobs) < count:
                try:
                    listing_jobs = scrape_listing_page(page, config, page_number)
                except PlaywrightError as error:
                    print(f"Could not fetch listing page {page_number}: {error}", file=sys.stderr)
                    break

                if not listing_jobs:
                    print(f"No usable listings found on page {page_number}; stopping.")
                    break

                added = 0
                for job in listing_jobs:
                    source_url = job.get("source_url")
                    if source_url and source_url in seen_urls:
                        continue
                    if source_url:
                        seen_urls.add(source_url)
                        job["raw_description"] = scrape_job_detail(page, source_url, config)
                        time.sleep(random.uniform(min_delay, max_delay))
                    jobs.append(job)
                    added += 1
                    if len(jobs) >= count:
                        break

                print(f"Page {page_number}: added {added} posting(s) (total: {len(jobs)})")
                if added == 0:
                    print("Page only contained duplicate listings; stopping.")
                    break
                page_number += 1
                if len(jobs) < count:
                    time.sleep(random.uniform(min_delay, max_delay))
        finally:
            context.close()
            browser.close()
    return jobs


def write_snapshot(jobs: list[dict[str, str | None]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    output_path = output_dir / f"raw_jobs_{timestamp}.json"
    output_path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect a raw PH job-market JSON snapshot.")
    parser.add_argument("--mode", choices=("mock", "live"), default="mock", help="Use reproducible mock data or a configured live source (default: mock).")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help=f"Maximum records to collect (default: {DEFAULT_COUNT}).")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"Snapshot directory (default: {DEFAULT_OUTPUT_DIR}).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for mock data (default: 42).")
    parser.add_argument("--config", type=Path, help="Source-specific JSON configuration; required for --mode live.")
    parser.add_argument("--min-delay", type=float, default=2.0, help="Minimum live-mode pause in seconds (default: 2).")
    parser.add_argument("--max-delay", type=float, default=5.0, help="Maximum live-mode pause in seconds (default: 5).")
    parser.add_argument("--show-browser", action="store_true", help="Show Chromium while using live mode.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.count < 1:
        raise SystemExit("--count must be at least 1")
    if args.min_delay < 0 or args.max_delay < args.min_delay:
        raise SystemExit("Delay values must be non-negative and --max-delay must be at least --min-delay.")

    if args.mode == "mock":
        jobs = generate_mock_jobs(args.count, args.seed)
    else:
        if args.config is None:
            raise SystemExit("--config is required when --mode live.")
        try:
            config = load_live_config(args.config)
            jobs = run_live(config, args.count, args.min_delay, args.max_delay, not args.show_browser)
        except (RuntimeError, ValueError) as error:
            raise SystemExit(str(error)) from error

    output_path = write_snapshot(jobs, args.output_dir)
    print(f"Saved {len(jobs)} posting(s) to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
