"""
Sweden Job Market — SECONDARY: The Hub (Nordic startup job board).

The Hub (thehub.io) covers Nordic startup jobs that often DON'T appear on
Platsbanken. Coverage check confirmed: 222 Sweden jobs listed.

Strategy:
- Listing pages (/jobs/location/sweden?page=N) give us URL + parent text
  (which contains title + company + location + commitment, but unstructured).
- Detail pages give us a clean og:title in the format
    "The Hub | {title} | {company}"
- Location is extracted from listing parent text using a known city list,
  since detail pages have no structured location field.
"""

import json
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "thehub"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://thehub.io"
ENTRY_URL = f"{BASE_URL}/jobs/location/sweden"

# Job ID is 24-char hex (MongoDB ObjectID style)
JOB_URL_RE = re.compile(r"^/jobs/([0-9a-f]{24})$")

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    ),
}

REQUEST_TIMEOUT = 30
SLEEP_BETWEEN = 0.5

# Sweden cities — also "Remote" since The Hub job is listed on Sweden page
KNOWN_LOCATIONS = (
    "Stockholm", "Göteborg", "Gothenburg", "Malmö", "Malmo",
    "Lund", "Uppsala", "Linköping", "Linkoping", "Västerås", "Vasteras",
    "Helsingborg", "Örebro", "Orebro", "Umeå", "Umea",
    "Norrköping", "Norrkoping", "Jönköping", "Jonkoping",
    "Solna", "Sundbyberg", "Sweden",
    "Remote",  # very common on TheHub
)

COMMITMENT_TOKENS = ("Full-time", "Part-time", "Contract", "Internship", "Freelance")
EXTRA_TOKENS = ("Freelance", "Cofounder", "Student", "Advisory board")


def clean(s: str | None) -> str:
    return " ".join((s or "").split())


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


# ---------- Listing page parsing ----------

def extract_max_page(soup: BeautifulSoup) -> int:
    """Find the largest page number in pagination links."""
    max_page = 1
    for a in soup.find_all("a", href=True):
        text = clean(a.get_text())
        if text.isdigit():
            max_page = max(max_page, int(text))
    return max_page


def parse_listing(html: str) -> list[dict]:
    """Return list of {url, job_id, parent_text} from one listing page."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen_ids = set()
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = JOB_URL_RE.match(href)
        if not m:
            continue
        job_id = m.group(1)
        if job_id in seen_ids:
            continue
        
        # Anchor itself is empty; walk up to the parent card
        parent = a.parent
        parent_text = clean(parent.get_text(" ", strip=True)) if parent else ""
        
        seen_ids.add(job_id)
        out.append({
            "job_id": job_id,
            "url": urljoin(BASE_URL, href),
            "parent_text": parent_text,
        })
    return out


def parse_parent_text(text: str) -> dict:
    """
    Extract location + commitment + extra from listing parent text.
    
    Format: "Title CompanyName Location Commitment [Extra]"
    
    We only try to find location and commitment (reliable).
    Title + company we get from detail page's og:title.
    """
    found_location = None
    for loc in KNOWN_LOCATIONS:
        # Match as whole word (avoid "Stockholm" matching inside "Stockholmsvägen")
        if re.search(rf"\b{re.escape(loc)}\b", text, re.IGNORECASE):
            found_location = loc
            break
    
    found_commitment = None
    for c in COMMITMENT_TOKENS:
        if re.search(rf"\b{re.escape(c)}\b", text, re.IGNORECASE):
            found_commitment = c
            break
    
    found_extras = []
    for e in EXTRA_TOKENS:
        if re.search(rf"\b{re.escape(e)}\b", text, re.IGNORECASE):
            found_extras.append(e)
    
    return {
        "location": found_location,
        "commitment": found_commitment,
        "extras": found_extras,
    }


# ---------- Detail page parsing ----------

def parse_detail(url: str) -> dict:
    """
    Fetch detail page, return {title, company, description} from og:* tags.
    
    og:title format: "The Hub | {title} | {company}"
    """
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    
    title_str = og_title.get("content", "") if og_title else ""
    desc_str = og_desc.get("content", "") if og_desc else ""
    
    # Split "The Hub | Job Title | Company"
    parts = [p.strip() for p in title_str.split("|")]
    if len(parts) >= 3 and parts[0].lower() == "the hub":
        title = parts[1]
        company = parts[2]
    elif len(parts) == 2:
        title = parts[1]
        company = None
    else:
        title = title_str
        company = None
    
    return {
        "title": title,
        "company": company,
        "description_text": desc_str,
    }


# ---------- Main ----------

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Step 1: get page 1 + detect total pages
    print(f"GET {ENTRY_URL}")
    first_html = fetch_html(ENTRY_URL)
    first_soup = BeautifulSoup(first_html, "html.parser")
    max_page = extract_max_page(first_soup)
    print(f"  Detected {max_page} pages\n")
    
    # Step 2: scrape all listing pages
    all_listings: dict[str, dict] = {}
    
    first_jobs = parse_listing(first_html)
    for j in first_jobs:
        all_listings[j["job_id"]] = j
    print(f"  Page  1: {len(first_jobs)} jobs")
    
    for page in range(2, max_page + 1):
        url = f"{ENTRY_URL}?page={page}"
        try:
            html = fetch_html(url)
        except requests.HTTPError as e:
            print(f"  Page {page:>2}: HTTP error {e}, skipping")
            continue
        jobs = parse_listing(html)
        new = 0
        for j in jobs:
            if j["job_id"] not in all_listings:
                all_listings[j["job_id"]] = j
                new += 1
        print(f"  Page {page:>2}: {len(jobs)} jobs ({new} new)")
        time.sleep(SLEEP_BETWEEN)
    
    print(f"\n  Total unique jobs from listings: {len(all_listings)}\n")
    
    # Step 3: parse parent_text for location/commitment
    for j in all_listings.values():
        j.update(parse_parent_text(j["parent_text"]))
    
    # Step 4: fetch detail page for each (this is the slow part)
    print(f"Fetching {len(all_listings)} detail pages...")
    parsed_jobs = []
    failures = 0
    for i, j in enumerate(all_listings.values(), 1):
        if i % 25 == 0:
            print(f"  ... {i}/{len(all_listings)}")
        try:
            detail = parse_detail(j["url"])
            j.update(detail)
        except Exception as e:
            print(f"  ⚠️  Detail fetch failed for {j['url']}: {e}")
            j.update({"title": None, "company": None, "description_text": None})
            failures += 1
        parsed_jobs.append(j)
        time.sleep(SLEEP_BETWEEN)
    
    print(f"  Done. {failures} failures.\n")
    
    # Step 5: Sweden filter
    # Since we're scraping /jobs/location/sweden, almost all should be Sweden
    # (or Remote with Sweden-based company). Keep everything except confirmed
    # non-Sweden locations (none expected here).
    sweden = parsed_jobs  # all of TheHub Sweden page counts
    
    # Save raw
    raw_path = RAW_DIR / f"{today}_thehub_raw.json"
    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(sweden, f, ensure_ascii=False, indent=2)
    
    # Save normalized
    normalized = []
    for j in sweden:
        normalized.append({
            "id": j["job_id"],
            "source": "thehub",
            "source_company_slug": j.get("company"),
            "headline": j.get("title"),
            "employer": j.get("company"),
            "municipality": j.get("location"),
            "team": None,
            "department": None,
            "role": None,
            "commitment": j.get("commitment"),
            "remote_status": "fully" if j.get("location") == "Remote" else None,
            "country": "Sweden",
            "publication_date": today,
            "description_text": j.get("description_text") or "",
            "url": j["url"],
        })
    norm_path = RAW_DIR / f"{today}_thehub_sweden_normalized.json"
    with norm_path.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
    
    # ---- Report ----
    print(f"{'=' * 70}")
    print(f"THE HUB FETCH RESULTS")
    print(f"{'=' * 70}")
    print(f"Total jobs:       {len(sweden)}")
    print(f"Detail fails:     {failures}")
    
    # Location dist
    print(f"\n--- Location distribution ---")
    locs = Counter(j.get("location") or "(unknown)" for j in sweden)
    for loc, c in locs.most_common():
        print(f"  {c:4d}  {loc}")
    
    # Commitment dist
    print(f"\n--- Commitment distribution ---")
    cmts = Counter(j.get("commitment") or "(unknown)" for j in sweden)
    for c, n in cmts.most_common():
        print(f"  {n:4d}  {c}")
    
    # Top companies
    print(f"\n--- Top 15 companies ---")
    cos = Counter(j.get("company") or "(unknown)" for j in sweden)
    for co, n in cos.most_common(15):
        print(f"  {n:4d}  {co}")
    
    # Sample of data/AI jobs
    print(f"\n--- Possible data/AI jobs (headline keyword scan) ---")
    DATA_KW = re.compile(
        r"\b(data|analy|machine learning|ai|ml|scientist|engineer|"
        r"bi developer|dataingenjör|dataanalytiker|statistik)\b",
        re.IGNORECASE,
    )
    matched = [j for j in sweden if DATA_KW.search(j.get("title") or "")]
    print(f"  {len(matched)} matched out of {len(sweden)}")
    for j in matched[:30]:
        print(f"  [{(j.get('location') or '?'):<12}] [{(j.get('company') or '?'):<25}] {j.get('title')}")
    
    print(f"\n--- Saved files ---")
    print(f"  Raw:        {raw_path}")
    print(f"  Normalized: {norm_path}")


if __name__ == "__main__":
    main()