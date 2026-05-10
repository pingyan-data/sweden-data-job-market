"""
Sweden Job Market — SECONDARY: Lever Postings API.

Lever is the public ATS API used by many companies including Spotify.
Endpoint: GET https://api.lever.co/v0/postings/{slug}?mode=json
No authentication required.

Strategy:
- Fetch all postings per company.
- Filter by location → Sweden cities only.
- Save raw + normalized view (compatible with JobTech summary schema).
"""

import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "lever"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Companies on Lever ----------
# Format: {display_name: lever_slug}
# Add more as we confirm them.
LEVER_COMPANIES = {
    "Spotify": "spotify",
    # Add others as we verify they're on Lever
}

# ---------- Sweden location filter ----------
# Lever's `categories.location` is a free-text city name.
# Match if any of these tokens appear (case-insensitive).
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


# ---------- Fetch ----------

def fetch_company(company_name: str, slug: str) -> list[dict]:
    """Fetch all postings for one company from Lever public API."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
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
    print(f"    fetched {len(data)} total postings")
    
    # Tag each posting with the source company name (in case slug != display name)
    for posting in data:
        posting["_company"] = company_name
        posting["_source"] = "lever"
    
    return data


def is_in_sweden(posting: dict) -> bool:
    """Check if a posting's location is in Sweden."""
    cats = posting.get("categories") or {}
    location = (cats.get("location") or "").lower()
    if not location:
        return False
    return any(tok in location for tok in SWEDEN_LOCATION_TOKENS)


# ---------- Normalize ----------
# Map Lever schema → unified schema (compatible with JobTech summary fields)

def normalize_lever(posting: dict) -> dict:
    """Convert one Lever posting into our unified schema."""
    cats = posting.get("categories") or {}
    
    # Convert Unix ms → ISO date
    created_ms = posting.get("createdAt", 0)
    if created_ms:
        pub_date = datetime.fromtimestamp(created_ms / 1000).strftime("%Y-%m-%d")
    else:
        pub_date = ""
    
    return {
        "id": posting.get("id"),
        "source": "lever",                     # 'jobtech' vs 'lever' vs 'greenhouse' ...
        "source_company_slug": posting.get("_company"),   # which company this came from
        "headline": posting.get("text"),       # ~ JobTech's headline
        "employer": posting.get("_company"),   # in Lever the company IS the source
        "municipality": cats.get("location"),
        "team": cats.get("team"),              # Lever-specific, useful signal
        "department": cats.get("department"),
        "commitment": cats.get("commitment"),
        "workplace_type": posting.get("workplaceType"),  # remote / hybrid / on-site
        "country": posting.get("country"),
        "publication_date": pub_date,
        "description_text": posting.get("descriptionPlain", ""),
        "url": posting.get("hostedUrl"),
        # Original full data preserved at the source file; this is just a flat view.
    }


# ---------- Main ----------

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    
    all_raw = []          # all Lever postings, all locations
    all_sweden = []       # only Sweden-located
    per_company_stats = []
    
    for company_name, slug in LEVER_COMPANIES.items():
        print(f"\n>>> Company: {company_name} (slug={slug!r})")
        postings = fetch_company(company_name, slug)
        if not postings:
            per_company_stats.append((company_name, 0, 0))
            continue
        
        sweden_postings = [p for p in postings if is_in_sweden(p)]
        all_raw.extend(postings)
        all_sweden.extend(sweden_postings)
        per_company_stats.append((company_name, len(postings), len(sweden_postings)))
        print(f"    Sweden-located: {len(sweden_postings)}")
        
        time.sleep(SLEEP_BETWEEN)
    
    # ---- Save raw (Sweden only — we don't need NY postings cluttering disk) ----
    raw_path = RAW_DIR / f"{today}_lever_sweden_raw.json"
    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(all_sweden, f, ensure_ascii=False, indent=2)
    
    # ---- Save normalized view ----
    normalized = [normalize_lever(p) for p in all_sweden]
    normalized.sort(key=lambda x: x["publication_date"], reverse=True)
    
    norm_path = RAW_DIR / f"{today}_lever_sweden_normalized.json"
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
    
    print(f"\nTotal Sweden-located postings: {len(all_sweden)}")
    
    # Location breakdown for Sweden subset
    print(f"\n--- Sweden location distribution ---")
    locs: Counter = Counter()
    for p in all_sweden:
        cats = p.get("categories") or {}
        locs[cats.get("location", "?")] += 1
    for loc, count in locs.most_common():
        print(f"  {count:4d}  {loc}")
    
    # Team / department signal — Lever's data category for Spotify is "Data"
    print(f"\n--- Team breakdown (top 15) ---")
    teams: Counter = Counter()
    for p in all_sweden:
        cats = p.get("categories") or {}
        teams[cats.get("team", "?")] += 1
    for team, count in teams.most_common(15):
        print(f"  {count:4d}  {team}")
    
    # Workplace type — Lever fills this!
    print(f"\n--- Workplace type ---")
    wt: Counter = Counter()
    for p in all_sweden:
        wt[p.get("workplaceType", "?")] += 1
    for w, count in wt.most_common():
        print(f"  {count:4d}  {w}")
    
    # All Sweden headlines so we can eyeball quality
    print(f"\n--- ALL Sweden postings ({len(all_sweden)}) ---")
    for p in all_sweden:
        cats = p.get("categories") or {}
        print(f"  [{cats.get('location'):<15}] [{cats.get('team', ''):<25}] {p.get('text')}")
    
    print(f"\n--- Saved files ---")
    print(f"  Raw:        {raw_path}")
    print(f"  Normalized: {norm_path}")


if __name__ == "__main__":
    main()