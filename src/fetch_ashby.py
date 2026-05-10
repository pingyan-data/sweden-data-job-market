"""
Sweden Job Market — SECONDARY: Ashby Job Postings API.

Public API: GET https://api.ashbyhq.com/posting-api/job-board/{clientname}
No authentication required. Returns clean JSON.

Ashby is a newer ATS (founded 2021), used by many tech startups
including Lovable.dev.
"""

import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "ashby"
RAW_DIR.mkdir(parents=True, exist_ok=True)

ASHBY_COMPANIES = {
    "Lovable": "lovable",
    # More to be added after probe step
}

SWEDEN_LOCATION_TOKENS = (
    "sweden", "sverige",
    "stockholm",
    "göteborg", "goteborg", "gothenburg",
    "malmö", "malmo",
    "lund", "uppsala",
    "linköping", "linkoping",
    "västerås", "vasteras",
    "helsingborg",
    "örebro", "orebro",
    "umeå", "umea",
    "norrköping", "norrkoping",
    "jönköping", "jonkoping",
    "solna",
)

REQUEST_TIMEOUT = 30
SLEEP_BETWEEN = 0.5


def fetch_company(company_name: str, client_slug: str) -> list[dict]:
    """Fetch all postings for one Ashby client."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{client_slug}"
    print(f"  GET {url}")
    try:
        resp = requests.get(url, headers={"accept": "application/json"}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"    ⚠️  HTTP error: {e}. Skipping.")
        return []
    except requests.RequestException as e:
        print(f"    ⚠️  Request error: {e}. Skipping.")
        return []
    
    data = resp.json()
    jobs = data.get("jobs", [])
    print(f"    fetched {len(jobs)} total jobs")
    
    for job in jobs:
        job["_company"] = company_name
        job["_source"] = "ashby"
    
    return jobs


def is_in_sweden(job: dict) -> bool:
    """
    Check if job is in Sweden. Ashby gives us several location-related fields:
    - location: primary city as free text
    - secondaryLocations: list of {location, address} objects
    - address.postalAddress.addressCountry
    
    Strategy: any of these contains a Sweden token → keep.
    """
    candidates = []
    
    # Primary location
    candidates.append((job.get("location") or "").lower())
    
    # Secondary locations
    for sec in job.get("secondaryLocations") or []:
        candidates.append((sec.get("location") or "").lower())
        addr = sec.get("address") or {}
        candidates.append((addr.get("addressCountry") or "").lower())
        candidates.append((addr.get("addressLocality") or "").lower())
    
    # Primary address
    primary_addr = (job.get("address") or {}).get("postalAddress") or {}
    candidates.append((primary_addr.get("addressCountry") or "").lower())
    candidates.append((primary_addr.get("addressLocality") or "").lower())
    
    haystack = " ".join(c for c in candidates if c)
    return any(tok in haystack for tok in SWEDEN_LOCATION_TOKENS)


def normalize_ashby(job: dict) -> dict:
    """Convert Ashby job → unified schema."""
    pub_iso = job.get("publishedAt") or ""
    pub_date = pub_iso[:10] if pub_iso else ""
    
    # Location: primary + secondaries combined
    locs = [job.get("location")]
    for sec in job.get("secondaryLocations") or []:
        if sec.get("location"):
            locs.append(sec["location"])
    locs = [l for l in locs if l]
    municipality = " / ".join(locs) if locs else None
    
    return {
        "id": job.get("jobUrl", "").split("/")[-1] or job.get("title"),
        "source": "ashby",
        "source_company_slug": job.get("_company"),
        "headline": job.get("title"),
        "employer": job.get("_company"),
        "municipality": municipality,
        "team": job.get("team"),
        "department": job.get("department"),
        "commitment": job.get("employmentType"),
        "workplace_type": job.get("workplaceType"),     # "Remote" / "Hybrid" / "On-Site"
        "is_remote": job.get("isRemote"),
        "country": (job.get("address") or {}).get("postalAddress", {}).get("addressCountry"),
        "publication_date": pub_date,
        "description_text": job.get("descriptionPlain", ""),
        "url": job.get("jobUrl"),
    }


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    
    all_sweden = []
    per_company_stats = []
    
    for company_name, slug in ASHBY_COMPANIES.items():
        print(f"\n>>> Company: {company_name} (slug={slug!r})")
        jobs = fetch_company(company_name, slug)
        if not jobs:
            per_company_stats.append((company_name, 0, 0))
            continue
        
        sweden_jobs = [j for j in jobs if is_in_sweden(j)]
        all_sweden.extend(sweden_jobs)
        per_company_stats.append((company_name, len(jobs), len(sweden_jobs)))
        print(f"    Sweden-located: {len(sweden_jobs)}")
        
        time.sleep(SLEEP_BETWEEN)
    
    # Save raw
    raw_path = RAW_DIR / f"{today}_ashby_sweden_raw.json"
    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(all_sweden, f, ensure_ascii=False, indent=2)
    
    # Save normalized
    normalized = [normalize_ashby(j) for j in all_sweden]
    normalized.sort(key=lambda x: x["publication_date"], reverse=True)
    norm_path = RAW_DIR / f"{today}_ashby_sweden_normalized.json"
    with norm_path.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
    
    # Report
    print(f"\n{'=' * 70}")
    print(f"FETCH RESULTS")
    print(f"{'=' * 70}")
    print(f"\n--- Per company ---")
    print(f"  {'Company':<20} {'Total':>8} {'Sweden':>8}")
    for name, total, sweden in per_company_stats:
        print(f"  {name:<20} {total:>8} {sweden:>8}")
    print(f"\nTotal Sweden: {len(all_sweden)}")
    
    # Workplace type
    print(f"\n--- Workplace type ---")
    wt: Counter = Counter()
    for j in all_sweden:
        wt[j.get("workplaceType") or "(none)"] += 1
    for w, count in wt.most_common():
        print(f"  {count:4d}  {w}")
    
    # All postings by company
    print(f"\n--- ALL Sweden postings by company ---")
    by_co: dict = {}
    for j in all_sweden:
        by_co.setdefault(j["_company"], []).append(j)
    for company in sorted(by_co):
        jobs = by_co[company]
        print(f"\n  {company} ({len(jobs)}):")
        for j in jobs:
            loc = j.get("location") or "?"
            wt = j.get("workplaceType") or ""
            dept = j.get("department") or ""
            print(f"    [{loc:<25}] [{wt:<10}] [{dept:<25}] {j.get('title')}")
    
    print(f"\n--- Saved files ---")
    print(f"  Raw:        {raw_path}")
    print(f"  Normalized: {norm_path}")


if __name__ == "__main__":
    main()