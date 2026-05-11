"""
Scrape The Hub jobs for whole Sweden and print top 20 in Klarna-like format.

Target:
    https://thehub.io/jobs/location/sweden

Output:
    Unique jobs found: XXX
    job_id title | company | location | description_preview -> url

No JSON file is saved.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://thehub.io"
ENTRY_URL = "https://thehub.io/jobs/location/sweden"

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "user-agent": (
        "SwedenJobMarketResearch/1.0 "
        "(public job market monitoring; "
        "https://github.com/pingyan-data/sweden-data-job-market)"
    ),
}

REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_REQUESTS = 0.7

JOB_URL_RE = re.compile(r"^/jobs/([a-zA-Z0-9]+)")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def fetch_html(url: str) -> str:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.text


def page_url(page: int) -> str:
    if page <= 1:
        return ENTRY_URL
    return f"{ENTRY_URL}?page={page}"


def extract_job_id(url: str) -> str | None:
    parsed = urlparse(url)
    match = JOB_URL_RE.match(parsed.path)
    if not match:
        return None
    return match.group(1)


def extract_filtered_count(soup: BeautifulSoup) -> int | None:
    text = soup.get_text(" ", strip=True)
    match = re.search(r"Showing:\s*([\d,]+)\s+filtered jobs", text)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def extract_max_page(soup: BeautifulSoup) -> int:
    max_page = 1

    for a in soup.find_all("a", href=True):
        href = a["href"]
        visible_text = clean_text(a.get_text(" ", strip=True))

        full_url = urljoin(BASE_URL, href)
        query = parse_qs(urlparse(full_url).query)

        if "page" in query:
            try:
                page_num = int(query["page"][0])
                max_page = max(max_page, page_num)
            except ValueError:
                pass

        if visible_text.isdigit():
            max_page = max(max_page, int(visible_text))

    return max_page


def extract_jobs_from_listing_page(html: str, listing_url: str) -> tuple[list[dict], dict]:
    soup = BeautifulSoup(html, "html.parser")

    jobs_by_id = {}

    for a in soup.find_all("a", href=True):
        full_url = urljoin(BASE_URL, a["href"])
        job_id = extract_job_id(full_url)

        if not job_id:
            continue

        raw_text = clean_text(a.get_text(" ", strip=True))

        if not raw_text:
            continue

        candidate = {
            "job_id": job_id,
            "raw_text": raw_text,
            "url": full_url,
            "listing_url": listing_url,
        }

        current = jobs_by_id.get(job_id)

        # Duplicate anchors may exist. Keep the longer text.
        if current is None or len(raw_text) > len(current["raw_text"]):
            jobs_by_id[job_id] = candidate

    meta = {
        "filtered_count": extract_filtered_count(soup),
        "max_page": extract_max_page(soup),
    }

    return list(jobs_by_id.values()), meta


def parse_detail_page(job: dict) -> dict:
    """
    Fetch one The Hub job detail page and extract cleaner fields.

    The Hub HTML can change, so this parser is intentionally defensive.
    If exact fields are hard to locate, it falls back to useful text snippets.
    """
    url = job["url"]
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    page_text = clean_text(soup.get_text(" ", strip=True))

    # Title: try h1 first, otherwise fallback to listing raw_text.
    h1 = soup.find("h1")
    title = clean_text(h1.get_text(" ", strip=True)) if h1 else job["raw_text"]

    # Try common metadata patterns from page text.
    # These are fallback heuristics.
    company = None
    location = None

    # The listing raw text often contains title/company/location, but may be flat.
    # Detail page usually has company name close to title, but not always easy to parse.
    # We keep unknowns as None rather than inventing values.
    possible_locations = [
        "Stockholm",
        "Gothenburg",
        "Göteborg",
        "Malmö",
        "Uppsala",
        "Lund",
        "Linköping",
        "Västerås",
        "Örebro",
        "Helsingborg",
        "Sweden",
        "Remote",
    ]

    for loc in possible_locations:
        if loc.lower() in page_text.lower():
            location = loc
            break

    # Description preview:
    # Remove very common navigation/footer noise by taking text after title when possible.
    description_text = page_text

    if title and title in page_text:
        description_text = page_text.split(title, 1)[-1].strip()

    description_preview = description_text[:500]

    job.update(
        {
            "title": title,
            "company": company,
            "location": location,
            "description_preview": description_preview,
        }
    )

    return job


def scrape_thehub_sweden(max_pages: int | None = None) -> list[dict]:
    first_url = page_url(1)
    first_html = fetch_html(first_url)
    first_jobs, meta = extract_jobs_from_listing_page(first_html, first_url)

    detected_max_page = meta["max_page"]
    filtered_count = meta["filtered_count"]

    if max_pages is None:
        max_pages = detected_max_page

    print(f"Detected filtered_count: {filtered_count}")
    print(f"Detected max_page: {detected_max_page}")
    print(f"Scraping pages: 1..{max_pages}")

    all_jobs = {}

    for job in first_jobs:
        all_jobs[job["job_id"]] = job

    print(f"Page 1: found {len(first_jobs)} unique job links")

    for page in range(2, max_pages + 1):
        url = page_url(page)
        html = fetch_html(url)
        jobs, _ = extract_jobs_from_listing_page(html, url)

        for job in jobs:
            all_jobs[job["job_id"]] = job

        print(f"Page {page}: found {len(jobs)} unique job links")
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    return list(all_jobs.values())


def main() -> None:
    # For full Sweden, use max_pages=None.
    # For fast testing, use max_pages=2.
    jobs = scrape_thehub_sweden(max_pages=None)

    print()
    print(f"Unique jobs found: {len(jobs)}")

    print("\nTop 20 jobs:\n")

    for job in jobs[:20]:
        try:
            enriched = parse_detail_page(job)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
        except Exception as e:
            enriched = job
            enriched["title"] = job["raw_text"]
            enriched["company"] = None
            enriched["location"] = None
            enriched["description_preview"] = f"DETAIL_FETCH_ERROR: {str(e)}"

        title = clean_text(enriched.get("title"))
        company = clean_text(enriched.get("company")) or "Unknown company"
        location = clean_text(enriched.get("location")) or "Unknown location"
        description = clean_text(enriched.get("description_preview"))

        print(
            f"{enriched['job_id']} "
            f"{title} | {company} | {location} | {description} "
            f"-> {enriched['url']}"
        )


if __name__ == "__main__":
    main()