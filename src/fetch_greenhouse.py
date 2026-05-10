"""
Sweden Job Market — SECONDARY: Greenhouse Job Board API.

Public API: GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
No authentication required.

Returns a list of jobs with location, departments, and content (description HTML).

Strategy:
- Fetch all jobs per company.
- Filter by location text → Sweden cities only.
- Save raw + normalized view (compatible with JobTech + Lever schemas).
"""

import json
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "greenhouse"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Companies on Greenhouse ----------
GREENHOUSE_COMPANIES = {
    # Removed: "Lovable" (slug pointed to an Italian retail company,
    # not Lovable.dev. Lovable.dev uses Ashby — see fetch_ashby.py)
    "Mentimeter": "mentimeter",
    "Wolt":       "wolt",
    # Truecaller had 0, skipping
}

# ---------- Sweden filter ----------
SWEDEN_LOCATION_TOKENS = (
    "sweden",
    "sverige",
    "stockholm",
    "göteborg", "goteborg", "gothenburg",
    "malmö", "malmo",
    "lund",
    "uppsala",
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


# ---------- HTML cleanup ----------
# Greenhouse returns description as HTML. We want plain text for downstream.
HTML_TAG_RE = re.compile(r"<[^>]+>")
HTML_ENTITY_MAP = {
    "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&quot;": '"', "&#39;": "'", "&rsquo;": "'", "&lsquo;": "'",
    "&rdquo;": '"', "&ldquo;": '"', "&ndash;": "–", "&mdash;": "—",
}


def html_to_text(html: str) -> str:
    if not html:
        return ""
    txt = HTML_TAG_RE.sub(" ", html)
    for entity, replacement in HTML_ENTITY_MAP.items():
        txt = txt.replace(entity, replacement)
    # Collapse whitespace
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


# ---------- Fetch ----------

def fetch_company(company_name: str, board_token: str) -> list[dict]:
    """Fetch all jobs for one company from Greenhouse public API."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
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
    # Greenhouse returns {"jobs": [...], "meta": {...}}
    jobs = data.get("jobs", [])
    print(f"    fetched {len(jobs)} total jobs")
    
    # Tag with source
    for job in jobs:
        job["_company"] = company_name
        job["_source"] = "greenhouse"
    
    return jobs


def is_in_sweden(job: dict) -> bool:
    """Check if a job's location is in Sweden."""
    location = (job.get("location") or {})
    location_name = (location.get("name") or "").lower()
    if not location_name:
        return False
    # Some jobs use "offices" for multi-location, but "location.name" usually has it
    return any(tok in location_name for tok in SWEDEN_LOCATION_TOKENS)


# ---------- Normalize to unified schema ----------

def normalize_greenhouse(job: dict) -> dict:
    """Convert one Greenhouse job into our unified schema."""
    location = (job.get("location") or {})
    
    # Parse departments — list of dicts
    depts = job.get("departments") or []
    dept_names = [d.get("name") for d in depts if d.get("name")]
    
    # Parse offices — list of dicts (multi-location possible)
    offices = job.get("offices") or []
    office_names = [o.get("name") for o in offices if o.get("name")]
    
    # publication date
    pub_iso = job.get("updated_at") or job.get("first_published") or ""
    pub_date = pub_iso[:10] if pub_iso else ""
    
    # Description: HTML → plain text
    description_html = job.get("content", "")
    description_text = html_to_text(description_html)
    
    return {
        "id": str(job.get("id")),
        "source": "greenhouse",
        "source_company_slug": job.get("_company"),
        "headline": job.get("title"),
        "employer": job.get("_company"),
        "municipality": location.get("name"),
        "team": " / ".join(dept_names) if dept_names else None,
        "department": dept_names[0] if dept_names else None,
        "offices": " / ".join(office_names) if office_names else None,
        "commitment": None,                    # Greenhouse doesn't expose this consistently
        "workplace_type": None,                # Greenhouse doesn't have this field by default
        "country": None,                       # Have to parse from location.name
        "publication_date": pub_date,
        "description_text": description_text,
        "url": job.get("absolute_url"),
    }


# ---------- Main ----------

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    
    all_sweden = []
    per_company_stats = []
    
    for company_name, board_token in GREENHOUSE_COMPANIES.items():
        print(f"\n>>> Company: {company_name} (board={board_token!r})")
        jobs = fetch_company(company_name, board_token)
        if not jobs:
            per_company_stats.append((company_name, 0, 0))
            continue
        
        sweden_jobs = [j for j in jobs if is_in_sweden(j)]
        all_sweden.extend(sweden_jobs)
        per_company_stats.append((company_name, len(jobs), len(sweden_jobs)))
        print(f"    Sweden-located: {len(sweden_jobs)}")
        
        time.sleep(SLEEP_BETWEEN)
    
    # Save raw (Sweden subset)
    raw_path = RAW_DIR / f"{today}_greenhouse_sweden_raw.json"
    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(all_sweden, f, ensure_ascii=False, indent=2)
    
    # Save normalized
    normalized = [normalize_greenhouse(j) for j in all_sweden]
    normalized.sort(key=lambda x: x["publication_date"], reverse=True)
    
    norm_path = RAW_DIR / f"{today}_greenhouse_sweden_normalized.json"
    with norm_path.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
    
    # ---- Report ----
    print(f"\n{'=' * 70}")
    print(f"FETCH RESULTS")
    print(f"{'=' * 70}")
    print(f"\n--- Per company ---")
    print(f"  {'Company':<20} {'Total':>8} {'Sweden':>8}")
    for name, total, sweden in per_company_stats:
        print(f"  {name:<20} {total:>8} {sweden:>8}")
    
    print(f"\nTotal Sweden-located: {len(all_sweden)}")
    
    # Location dist
    print(f"\n--- Sweden location distribution ---")
    locs: Counter = Counter()
    for j in all_sweden:
        loc = (j.get("location") or {}).get("name", "?")
        locs[loc] += 1
    for loc, count in locs.most_common():
        print(f"  {count:4d}  {loc}")
    
    # Department breakdown
    print(f"\n--- Department breakdown (top 15) ---")
    depts: Counter = Counter()
    for j in all_sweden:
        for d in (j.get("departments") or []):
            depts[d.get("name", "?")] += 1
    for d, count in depts.most_common(15):
        print(f"  {count:4d}  {d}")
    
    # All Sweden headlines, grouped by company
    print(f"\n--- ALL Sweden postings by company ---")
    by_co: dict[str, list] = {}
    for j in all_sweden:
        by_co.setdefault(j["_company"], []).append(j)
    for company in sorted(by_co):
        jobs = by_co[company]
        print(f"\n  {company} ({len(jobs)} jobs):")
        for j in jobs:
            loc = (j.get("location") or {}).get("name", "?")
            depts = " / ".join((d.get("name") or "") for d in (j.get("departments") or []))
            print(f"    [{loc:<20}] [{depts:<25}] {j.get('title')}")
    
    print(f"\n--- Saved files ---")
    print(f"  Raw:        {raw_path}")
    print(f"  Normalized: {norm_path}")


if __name__ == "__main__":
    main()