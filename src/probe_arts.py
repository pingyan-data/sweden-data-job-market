"""
ATS detection probe.

For each company in CANDIDATES, try the public APIs of
Lever, Greenhouse, and Teamtailor and see which (if any) responds with data.

This is a one-off lookup, not part of the daily pipeline.
"""

import requests
from typing import Optional


# Candidates: companies we want to detect.
# Each entry is a list of slug variants to try (lowercase, no spaces).
CANDIDATES = {
    "Klarna":         ["klarna"],
    "King":           ["king", "king-com", "kingdotcom"],
    "Tink":           ["tink"],
    "Lovable":        ["lovable", "lovable-labs", "lovablelabs"],
    "Sana Labs":      ["sana", "sanalabs", "sana-labs"],
    "Epidemic Sound": ["epidemicsound", "epidemic-sound"],
    "Storytel":       ["storytel"],
    "Mentimeter":     ["mentimeter"],
    "Voi":            ["voi", "voi-technology", "voitechnology"],
    "Wolt":           ["wolt"],
    "Truecaller":     ["truecaller"],
    "Northvolt":      ["northvolt"],
    "Einride":        ["einride"],
    "Stravito":       ["stravito"],
    "Apotea":         ["apotea"],
    "Schibsted":      ["schibsted"],
    "Hemnet":         ["hemnet"],
    "Bolt":           ["bolt"],
    "Paradox":        ["paradox", "paradox-interactive", "paradoxinteractive"],
    "MAG Interactive":["mag-interactive", "maginteractive"],
}


def try_lever(slug: str) -> Optional[int]:
    """Return number of postings if Lever has this slug, else None."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        r = requests.get(url, headers={"accept": "application/json"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return len(data)
    except requests.RequestException:
        pass
    return None


def try_greenhouse(slug: str) -> Optional[int]:
    """Return number of postings if Greenhouse has this board_token."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        r = requests.get(url, headers={"accept": "application/json"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and "jobs" in data:
                return len(data["jobs"])
    except requests.RequestException:
        pass
    return None


def try_teamtailor(slug: str) -> Optional[int]:
    """
    Teamtailor's public structure: each company has {slug}.teamtailor.com.
    The JSON endpoint structure is different from Lever/Greenhouse —
    we'll just check if the careers subdomain returns 200 for now,
    and dig into the API in a separate script.
    """
    # Try the careers page, not the API yet
    url = f"https://{slug}.teamtailor.com/jobs"
    try:
        r = requests.get(url, timeout=10, allow_redirects=True)
        if r.status_code == 200 and "teamtailor" in r.url.lower():
            return -1  # signal "exists but count unknown yet"
    except requests.RequestException:
        pass
    return None


def probe_company(name: str, slugs: list[str]) -> dict:
    """For one company, try all slug variants on all three ATS."""
    findings = []
    for slug in slugs:
        for ats_name, fn in [("Lever", try_lever),
                              ("Greenhouse", try_greenhouse),
                              ("Teamtailor", try_teamtailor)]:
            count = fn(slug)
            if count is not None:
                findings.append((ats_name, slug, count))
    return findings


def main():
    print(f"{'Company':<20} {'ATS':<12} {'Slug':<25} {'Count':>8}")
    print("-" * 72)
    
    summary = {"Lever": [], "Greenhouse": [], "Teamtailor": [], "NotFound": []}
    
    for name, slugs in CANDIDATES.items():
        findings = probe_company(name, slugs)
        if not findings:
            print(f"{name:<20} {'(none)':<12} {'-':<25} {'-':>8}")
            summary["NotFound"].append(name)
        else:
            for ats, slug, count in findings:
                count_str = "?" if count == -1 else str(count)
                print(f"{name:<20} {ats:<12} {slug:<25} {count_str:>8}")
                summary[ats].append((name, slug, count))
    
    print(f"\n{'=' * 72}")
    print("SUMMARY")
    print(f"{'=' * 72}")
    for ats in ["Lever", "Greenhouse", "Teamtailor"]:
        print(f"\n  {ats}: {len(summary[ats])} companies")
        for name, slug, count in summary[ats]:
            count_str = "?" if count == -1 else f"{count} postings"
            print(f"    - {name} ({slug}, {count_str})")
    print(f"\n  Not found anywhere: {len(summary['NotFound'])} companies")
    for name in summary["NotFound"]:
        print(f"    - {name}")


if __name__ == "__main__":
    main()