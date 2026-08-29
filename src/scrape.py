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
