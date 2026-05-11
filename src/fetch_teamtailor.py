"""
Sweden Job Market — SECONDARY: Teamtailor RSS feeds.

Teamtailor's authenticated API requires per-company keys, but every
Teamtailor career site exposes a public RSS feed at /jobs.rss with
structured location, role, and department data.

Confirmed pattern:
  GET {base}/jobs.rss  →  RSS 2.0 XML, no auth required.

Note: Teamtailor uses a custom XML namespace
xmlns:tt="https://teamtailor.com/locations" for several fields
(locations, department, role). ElementTree shows these as
'{https://teamtailor.com/locations}tag' — we must include the prefix.
"""

import json
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "teamtailor"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Teamtailor's custom XML namespace
TT_NS = "{https://teamtailor.com/locations}"

# Teamtailor career sites (confirmed via probe_teamtailor.py)
TEAMTAILOR_SITES = {
    "Schibsted":   "https://schibsted.teamtailor.com",
    "Storytel":    "https://jobs.storytel.com",
    "Swedbank":    "https://jobs.swedbank.com",
    "Telenor SE":  "https://careers.telenor.se",
    "Cambio":      "https://cambio.teamtailor.com",
    "Noba Bank":   "https://careers.noba.bank",
    "Resurs Bank": "https://careers.resurs.com",
}

REQUEST_TIMEOUT = 30
SLEEP_BETWEEN = 0.5

HEADERS = {
    "accept": "application/rss+xml, application/xml, */*",
    "user-agent": (
        "Mozilla/5.0 (compatible; SwedenJobMarketResearch/1.0; "
        "+https://github.com/pingyan-data/sweden-data-job-market)"
    ),
}

# ---------- HTML cleanup ----------
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
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


# ---------- Fetch & parse ----------

def fetch_rss(company: str, base_url: str) -> ET.Element | None:
    url = f"{base_url}/jobs.rss"
    print(f"  GET {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    ⚠️  Request error: {e}")
        return None
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"    ⚠️  XML parse error: {e}")
        return None
    items = root.findall(".//item")
    print(f"    fetched {len(items)} total items")
    return root


def parse_locations(item: ET.Element) -> list[dict]:
    """Extract all <location> objects from an <item>'s <locations> container.
    
    Tags are in the Teamtailor namespace — we must prefix with TT_NS.
    """
    out = []
    locations_container = item.find(f"{TT_NS}locations")
    if locations_container is None:
        return out
    for loc in locations_container.findall(f"{TT_NS}location"):
        out.append({
            "name":    (loc.findtext(f"{TT_NS}name") or "").strip(),
            "address": (loc.findtext(f"{TT_NS}address") or "").strip(),
            "zip":     (loc.findtext(f"{TT_NS}zip") or "").strip(),
            "city":    (loc.findtext(f"{TT_NS}city") or "").strip(),
            "country": (loc.findtext(f"{TT_NS}country") or "").strip(),
        })
    return out


def is_in_sweden(item: ET.Element) -> bool:
    """True if any location's country contains 'sweden' (case-insensitive)."""
    for loc in parse_locations(item):
        country = loc.get("country", "").lower()
        if "sweden" in country or country == "se":
            return True
    return False


def parse_pubdate(item: ET.Element) -> str:
    raw = item.findtext("pubDate") or ""
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def normalize_item(item: ET.Element, company: str) -> dict:
    locations = parse_locations(item)
    sweden_cities = [
        loc["city"] for loc in locations
        if ("sweden" in loc.get("country", "").lower()
            or loc.get("country", "").lower() == "se")
        and loc.get("city")
    ]
    all_cities = [loc["city"] for loc in locations if loc.get("city")]
    description_html = item.findtext("description") or ""
    link = item.findtext("link") or ""
    guid = item.findtext("guid") or ""
    return {
        "id": guid or link,
        "source": "teamtailor",
        "source_company_slug": company,
        "headline": item.findtext("title"),
        "employer": company,
        "municipality": " / ".join(sweden_cities) if sweden_cities else (all_cities[0] if all_cities else None),
        "all_cities": " / ".join(all_cities) if all_cities else None,
        "team": item.findtext(f"{TT_NS}department"),
        "department": item.findtext(f"{TT_NS}department"),
        "role": item.findtext(f"{TT_NS}role"),
        "remote_status": item.findtext("remoteStatus"),
        "country": "Sweden",
        "publication_date": parse_pubdate(item),
        "description_text": html_to_text(description_html),
        "url": link,
    }


# ---------- Main ----------

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    all_sweden_items = []
    all_normalized = []
    per_company_stats = []
    
    for company, base_url in TEAMTAILOR_SITES.items():
        print(f"\n>>> Company: {company}")
        root = fetch_rss(company, base_url)
        if root is None:
            per_company_stats.append((company, 0, 0))
            continue
        items = root.findall(".//item")
        sweden_items = [it for it in items if is_in_sweden(it)]
        per_company_stats.append((company, len(items), len(sweden_items)))
        print(f"    Sweden-located: {len(sweden_items)}")
        for item in sweden_items:
            all_sweden_items.append((company, item))
            all_normalized.append(normalize_item(item, company))
        time.sleep(SLEEP_BETWEEN)
    
    all_normalized.sort(key=lambda x: x["publication_date"], reverse=True)
    norm_path = RAW_DIR / f"{today}_teamtailor_sweden_normalized.json"
    with norm_path.open("w", encoding="utf-8") as f:
        json.dump(all_normalized, f, ensure_ascii=False, indent=2)
    
    raw_records = []
    for company, item in all_sweden_items:
        record = {"_company": company}
        for child in item:
            tag = child.tag
            clean_tag = tag.split("}", 1)[-1] if "}" in tag else tag
            if clean_tag == "locations":
                record["locations"] = parse_locations(item)
            else:
                record[clean_tag] = (child.text or "").strip() if child.text else ""
        raw_records.append(record)
    raw_path = RAW_DIR / f"{today}_teamtailor_sweden_raw.json"
    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(raw_records, f, ensure_ascii=False, indent=2)
    
    # ---- Report ----
    print(f"\n{'=' * 70}")
    print(f"FETCH RESULTS")
    print(f"{'=' * 70}")
    print(f"\n--- Per company ---")
    print(f"  {'Company':<20} {'Total':>8} {'Sweden':>8}")
    for name, total, sweden in per_company_stats:
        print(f"  {name:<20} {total:>8} {sweden:>8}")
    print(f"\nTotal Sweden: {len(all_normalized)}")
    
    print(f"\n--- Sweden city distribution ---")
    cities: Counter = Counter()
    for n in all_normalized:
        for c in (n.get("municipality") or "").split(" / "):
            if c:
                cities[c] += 1
    for c, count in cities.most_common(15):
        print(f"  {count:4d}  {c}")
    
    print(f"\n--- Remote status ---")
    rs: Counter = Counter()
    for n in all_normalized:
        rs[n.get("remote_status") or "(none)"] += 1
    for s, count in rs.most_common():
        print(f"  {count:4d}  {s}")
    
    print(f"\n--- Top 15 departments ---")
    depts: Counter = Counter()
    for n in all_normalized:
        depts[n.get("department") or "(none)"] += 1
    for d, count in depts.most_common(15):
        print(f"  {count:4d}  {d}")
    
    print(f"\n--- Top 20 roles ---")
    roles: Counter = Counter()
    for n in all_normalized:
        roles[n.get("role") or "(none)"] += 1
    for r, count in roles.most_common(20):
        print(f"  {count:4d}  {r}")
    
    print(f"\n--- Possible data/AI jobs by company ---")
    DATA_KW = re.compile(
        r"\b(data|analy|machine learning|ai|ml|scientist|engineer|"
        r"bi developer|bi-utvecklare|dataingenjör|dataanalytiker|"
        r"statistik)\b",
        re.IGNORECASE,
    )
    by_co: dict = {}
    for n in all_normalized:
        if DATA_KW.search(n.get("headline") or ""):
            by_co.setdefault(n["employer"], []).append(n)
    for company in sorted(by_co):
        jobs = by_co[company]
        print(f"\n  {company} ({len(jobs)}):")
        for j in jobs:
            print(f"    [{(j.get('role') or '?'):<25}] [{(j.get('remote_status') or '?'):<8}] {j.get('headline')}")
    
    print(f"\n--- Saved files ---")
    print(f"  Raw:        {raw_path}")
    print(f"  Normalized: {norm_path}")


if __name__ == "__main__":
    main()