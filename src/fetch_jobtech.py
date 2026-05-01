"""
Sweden Job Market — PRIMARY data source: JobTech JobSearch API.

Strategy: high-recall multi-query collection with deduplication.

- Use double-quoted phrases where they work (most queries).
- Use bare words for Swedish terms and 'mlops' (where phrase is too strict).
- Track which queries matched each ad → match_count is a confidence signal.
- Save raw + flat summary to data/raw/.

Post-processing (filtering, classification) happens in a separate step.
"""

import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

# ---------- Config ----------

BASE_URL = "https://jobsearch.api.jobtechdev.se"
SEARCH_ENDPOINT = f"{BASE_URL}/search"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Final query list — see diagnostic notes for rationale.
# Quoted = phrase match. Bare = single token (used where phrase is too strict).
QUERIES = [
    # High-quality phrase queries
    '"data scientist"',
    '"data engineer"',
    '"data analyst"',
    '"analytics engineer"',
    '"ai engineer"',
    '"machine learning engineer"',
    '"machine learning scientist"',
    '"research scientist"',
    '"decision scientist"',
    '"data platform engineer"',
    '"bi analyst"',
    '"bi developer"',
    '"bi-utvecklare"',
    # Single-token (phrase version too strict)
    "mlops",
    # Swedish — quality varies, post-filter will handle
    "dataanalytiker",
    "dataingenjör",
]

# Polite request settings
REQUEST_TIMEOUT = 30
PAGE_SIZE = 100        # API max
MAX_PAGES = 20         # API caps offset+limit at 2000
SLEEP_BETWEEN = 0.3    # seconds, between paginated requests


# ---------- API calls ----------

def search_jobs_paginated(query: str) -> list[dict]:
    """Fetch ALL hits for a query by paginating through the result set."""
    all_hits: list[dict] = []
    for page in range(MAX_PAGES):
        offset = page * PAGE_SIZE
        params = {
            "q": query,
            "limit": PAGE_SIZE,
            "offset": offset,
            "sort": "pubdate-desc",
        }
        resp = requests.get(
            SEARCH_ENDPOINT,
            params=params,
            headers={"accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", [])
        all_hits.extend(hits)

        total = data.get("total", {}).get("value", 0)
        if offset + PAGE_SIZE >= total or not hits:
            break
        time.sleep(SLEEP_BETWEEN)

    return all_hits


# ---------- Collection & deduplication ----------

def collect_all(queries: list[str]) -> tuple[dict, dict]:
    """
    Run all queries, dedupe by ad ID, track which queries matched each ad.

    Returns
    -------
    all_ads : dict[str, dict]
        ad_id -> ad object (with extra _matched_queries field)
    per_query_counts : dict[str, int]
        query -> raw hit count (before dedup)
    """
    all_ads: dict[str, dict] = {}
    per_query_counts: dict[str, int] = {}

    for q in queries:
        print(f"\n>>> Query: {q!r}")
        try:
            hits = search_jobs_paginated(q)
        except requests.HTTPError as e:
            print(f"    ⚠️  HTTP error: {e}. Skipping.")
            per_query_counts[q] = 0
            continue

        per_query_counts[q] = len(hits)
        new_count = 0
        for hit in hits:
            ad_id = hit.get("id")
            if not ad_id:
                continue
            if ad_id not in all_ads:
                hit["_matched_queries"] = [q]
                all_ads[ad_id] = hit
                new_count += 1
            else:
                all_ads[ad_id]["_matched_queries"].append(q)
        print(f"    fetched {len(hits)}, new unique: {new_count}")

    return all_ads, per_query_counts


# ---------- Persistence ----------

def save_results(all_ads: dict) -> tuple[Path, Path]:
    today = datetime.now().strftime("%Y-%m-%d")

    # Full raw — everything, for re-analysis later
    raw_path = RAW_DIR / f"{today}_jobtech_all.json"
    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(all_ads, f, ensure_ascii=False, indent=2)

    # Flat summary — for quick eyeballing
    summary = []
    for ad_id, ad in all_ads.items():
        summary.append({
            "id": ad_id,
            "headline": ad.get("headline"),
            "employer": (ad.get("employer") or {}).get("name"),
            "municipality": (ad.get("workplace_address") or {}).get("municipality"),
            "occupation": (ad.get("occupation") or {}).get("label"),
            "occupation_field": (ad.get("occupation_field") or {}).get("label"),
            "publication_date": (ad.get("publication_date") or "")[:10],
            "remote_work": ad.get("remote_work"),
            "matched_queries": ad["_matched_queries"],
            "match_count": len(ad["_matched_queries"]),
        })
    summary.sort(key=lambda x: -x["match_count"])

    summary_path = RAW_DIR / f"{today}_jobtech_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return raw_path, summary_path


# ---------- Reporting ----------

def report(all_ads: dict, per_query_counts: dict, raw_path: Path, summary_path: Path):
    print(f"\n{'=' * 70}")
    print(f"=== TOTAL UNIQUE ADS: {len(all_ads)} ===")
    print(f"{'=' * 70}")

    print(f"\n--- Per-query counts (raw, before dedup) ---")
    for q, n in per_query_counts.items():
        print(f"  {n:5d}  {q}")

    # Match-count distribution — confidence signal
    match_dist = Counter(len(ad["_matched_queries"]) for ad in all_ads.values())
    print(f"\n--- Match count distribution ---")
    print(f"  (how many distinct queries matched each ad)")
    for count in sorted(match_dist):
        print(f"  matched by {count} query(ies): {match_dist[count]:4d} ads")

    # Top employers
    employers: Counter = Counter()
    for ad in all_ads.values():
        emp = (ad.get("employer") or {}).get("name")
        if emp:
            employers[emp] += 1
    print(f"\n--- Top 15 employers ---")
    for emp, count in employers.most_common(15):
        print(f"  {count:3d}  {emp}")

    # File sizes
    print(f"\n--- Saved files ---")
    print(f"  Raw:     {raw_path}  ({raw_path.stat().st_size / 1024:.1f} KB)")
    print(f"  Summary: {summary_path}  ({summary_path.stat().st_size / 1024:.1f} KB)")


# ---------- Main ----------

if __name__ == "__main__":
    all_ads, per_query_counts = collect_all(QUERIES)
    raw_path, summary_path = save_results(all_ads)
    report(all_ads, per_query_counts, raw_path, summary_path)