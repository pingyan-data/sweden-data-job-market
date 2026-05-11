"""
Sweden Job Market — SECONDARY: Klarna (via Deel careers page).

Klarna recently migrated their careers page to Deel (jobs.deel.com/klarna).
The page is JavaScript-rendered, so we use Playwright to load it,
extract job-detail links, and parse the structured raw_text.

Each Klarna job is published as ONE listing PER CITY (e.g., a role open in
Stockholm + London + NYC becomes 3 separate UUIDs). That means Sweden
filtering = unambiguous, no multi-location dedup needed.

Klarna is the only source in our dataset that publishes salary ranges
publicly — a unique signal for newsletter analysis.
"""

import asyncio
import json
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "klarna"
RAW_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://jobs.deel.com/klarna"
JOB_DETAIL_RE = re.compile(r"/klarna/job-details/([0-9a-fA-F-]{36})/overview")

# Sweden cities (same as other fetchers)
SWEDEN_LOCATION_TOKENS = (
    "stockholm", "göteborg", "goteborg", "gothenburg",
    "malmö", "malmo", "lund", "uppsala",
    "linköping", "linkoping", "västerås", "vasteras",
    "helsingborg", "örebro", "orebro", "umeå", "umea",
    "norrköping", "norrkoping", "jönköping", "jonkoping",
    "solna", "sundbyberg",
)

# Employment-type tokens that appear in raw_text (used to find the boundary
# between location and trailing salary)
COMMITMENT_TOKENS = ("Full-time", "Part-time", "Contract", "Internship", "Temporary")

# Salary pattern: matches "kr 602,251 SEK - kr 674,521 SEK" / "$120,450 USD - $151,093 USD" etc.
# Currency symbol(s) + amount + ISO code, twice separated by " - "
SALARY_RE = re.compile(
    r"(?:£|\$|€|kr\s?)[\d,]+\s*(?:GBP|USD|EUR|SEK|CAD)\s*-\s*(?:£|\$|€|kr\s?)[\d,]+\s*(?:GBP|USD|EUR|SEK|CAD)"
)


def clean_text(text: str) -> str:
    return " ".join((text or "").split())


def parse_raw_text(raw: str) -> dict:
    """
    Parse Klarna Deel raw text into structured fields.
    
    Format: "<title> <location(s)> <commitment> [<salary>]"
    
    Strategy: peel from the right.
      1. Match optional salary at the end → strip
      2. Find commitment token → boundary between location and the rest
      3. Everything before commitment = title + location;
         locations are usually capitalised city names just before commitment.
         Title is everything before the location.
    """
    raw = clean_text(raw)
    
    # Step 1: peel salary from the end
    salary = None
    salary_match = SALARY_RE.search(raw)
    if salary_match:
        salary = salary_match.group(0).strip()
        raw_no_salary = raw[:salary_match.start()].strip()
    else:
        raw_no_salary = raw
    
    # Step 2: peel commitment
    commitment = None
    title_plus_loc = raw_no_salary
    for tok in COMMITMENT_TOKENS:
        # Match commitment as last whole word
        pattern = rf"\s+{re.escape(tok)}\s*$"
        m = re.search(pattern, raw_no_salary)
        if m:
            commitment = tok
            title_plus_loc = raw_no_salary[:m.start()].strip()
            break
    
    # Step 3: split title from location
    # Klarna locations are city names. Multi-city: "Stockholm, Milan, London".
    # Heuristic: location is the LAST chunk that starts with a known city or
    # follows after the last comma-separated city sequence.
    # Robust approach: find the LAST occurrence of a known Sweden/non-Sweden city
    # word. But simpler — Klarna jobs we've seen always have location as
    # capitalised words right before commitment, no all-caps title overlap.
    #
    # We do this: take title_plus_loc and walk from the RIGHT, collecting words
    # while they look like part of a location (capitalised, or commas).
    # First lowercase/dash/parenthesis word from the right = title boundary.
    
    title, location = _split_title_location(title_plus_loc)
    
    # Check Sweden
    in_sweden = False
    for tok in SWEDEN_LOCATION_TOKENS:
        if tok in location.lower():
            in_sweden = True
            break
    
    return {
        "title": title,
        "location": location,
        "commitment": commitment,
        "salary": salary,
        "in_sweden": in_sweden,
    }


# Known city words (used by the split heuristic).
# Not exhaustive but covers Klarna's main offices.
KNOWN_CITIES = {
    # Sweden
    "stockholm", "göteborg", "malmö", "lund", "uppsala",
    # Other Klarna offices
    "london", "new", "york",  # New York → two tokens
    "berlin", "munich", "lisbon", "los", "angeles",
    "columbus", "toronto", "san", "francisco",
    "milan", "amsterdam", "paris", "madrid", "dublin",
    "hamburg", "frankfurt", "zurich", "warsaw", "tokyo",
    "sydney", "melbourne", "singapore",
    # Edge
    "remote",
}


def _split_title_location(text: str) -> tuple[str, str]:
    """
    Walk from the right. While the rightmost word looks like a city or a
    location separator (comma), keep it as part of location. When we hit
    a token that's clearly title (lowercase, has dash, special punct), stop.
    """
    tokens = text.split()
    location_tokens: list[str] = []
    
    while tokens:
        tok = tokens[-1]
        tok_lower = tok.rstrip(",").lower()
        
        if tok_lower in KNOWN_CITIES or tok.endswith(","):
            location_tokens.insert(0, tokens.pop())
        else:
            break
    
    title = " ".join(tokens).strip()
    location = " ".join(location_tokens).strip()
    
    # Edge case: nothing matched → entire string is title, no location detected
    if not location and tokens:
        title = text
        location = ""
    
    return title, location

def _detect_issues(p: dict) -> list[str]:
    """Flag known data-quality issues for downstream review."""
    flags = []
    if p["salary"] and "kr 0 SEK" in p["salary"]:
        flags.append("salary_has_zero")
    if "Success," in p.get("location", ""):
        flags.append("location_parse_suspect")
    return flags

# ---------- Scrape ----------

async def scrape_klarna() -> list[dict]:
    """Render the Deel careers page and extract all job links + raw text."""
    print(f"  GET {URL}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0 Safari/537.36"
            )
        )
        await page.goto(URL, wait_until="networkidle", timeout=60_000)
        
        # Trigger lazy load by scrolling
        for _ in range(5):
            await page.mouse.wheel(0, 2000)
            await page.wait_for_timeout(700)
        
        links = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(a => ({text: a.innerText, href: a.href}))"
        )
        await browser.close()
    
    return links


# ---------- Main ----------

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Scrape (async wrapper)
    links = asyncio.run(scrape_klarna())
    print(f"    fetched {len(links)} raw <a> tags")
    
    # 2. Dedupe by job_id, keep longest raw_text per id
    seen: dict[str, dict] = {}
    for link in links:
        href = link.get("href", "")
        text = clean_text(link.get("text", ""))
        m = JOB_DETAIL_RE.search(href)
        if not m:
            continue
        job_id = m.group(1)
        if job_id not in seen or len(text) > len(seen[job_id]["raw_text"]):
            seen[job_id] = {"job_id": job_id, "raw_text": text, "url": href}
    
    all_jobs = list(seen.values())
    print(f"    unique jobs: {len(all_jobs)}")
    
    # 3. Parse each
    parsed = []
    for j in all_jobs:
        fields = parse_raw_text(j["raw_text"])
        parsed.append({**j, **fields})
    
    sweden = [p for p in parsed if p["in_sweden"]]
    print(f"    Sweden-located: {len(sweden)}")
    
    # 4. Save raw (all jobs, all locations — for audit)
    raw_path = RAW_DIR / f"{today}_klarna_all_raw.json"
    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    
    # 5. Save normalized Sweden subset
    normalized = []
    for p in sweden:
        normalized.append({
            "id": p["job_id"],
            "source": "klarna_deel",
            "source_company_slug": "klarna",
            "headline": p["title"],
            "employer": "Klarna",
            "municipality": p["location"],
            "team": None,
            "department": None,
            "role": None,
            "commitment": p["commitment"],
            "salary_raw": p["salary"],   # Unique to Klarna! Worth preserving.
            "remote_status": None,
            "country": "Sweden",
            "publication_date": today,   # Deel page doesn't expose pubDate
            "description_text": "",      # Would need to fetch each detail page
            "url": p["url"],
            "id": p["job_id"],
            # NEW: quality flags for downstream audit
            "_quality_flags": _detect_issues(p),
        })
    
    norm_path = RAW_DIR / f"{today}_klarna_sweden_normalized.json"
    with norm_path.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
    
    # ---- Report ----
    print(f"\n{'=' * 70}")
    print(f"KLARNA FETCH RESULTS")
    print(f"{'=' * 70}")
    print(f"Total jobs:           {len(parsed)}")
    print(f"Sweden-located:       {len(sweden)}")
    print(f"With salary data:     {sum(1 for p in sweden if p['salary'])}")
    
    # Location dist (top 15)
    print(f"\n--- Location distribution (all jobs) ---")
    locs = Counter(p["location"] for p in parsed if p["location"])
    for loc, count in locs.most_common(15):
        print(f"  {count:4d}  {loc}")
    
    # Sweden subset by title
    print(f"\n--- ALL Sweden jobs (titles) ---")
    for p in sorted(sweden, key=lambda x: x["title"]):
        salary_str = f" | {p['salary']}" if p["salary"] else ""
        print(f"  [{p['location']}] {p['title']}{salary_str}")
    
    # Salary signal
    print(f"\n--- Sweden jobs WITH salary (golden newsletter data) ---")
    sweden_with_salary = [p for p in sweden if p["salary"]]
    print(f"  {len(sweden_with_salary)} of {len(sweden)} ({100*len(sweden_with_salary)/max(len(sweden), 1):.0f}%) publish salary")
    
    print(f"\n--- Saved files ---")
    print(f"  All raw:    {raw_path}")
    print(f"  Sweden:     {norm_path}")


if __name__ == "__main__":
    main()
