"""
Probe additional companies for Ashby presence.

For companies we have NOT found on Lever/Greenhouse/Teamtailor yet,
check if they're on Ashby. Critical: verify content, don't trust slug match.
"""

import requests

# Companies we still need to find (from earlier probe)
CANDIDATES = {
    "King":           ["king", "king-com", "kingdotcom"],
    "Tink":           ["tink"],
    "Sana Labs":      ["sana", "sanalabs", "sana-labs", "sana-ai"],
    "Epidemic Sound": ["epidemicsound", "epidemic-sound", "epidemic"],
    "Voi":            ["voi", "voi-technology", "voitechnology"],
    "Northvolt":      ["northvolt"],
    "Einride":        ["einride"],
    "Stravito":       ["stravito"],
    "Apotea":         ["apotea"],
    "Hemnet":         ["hemnet"],
    "Bolt":           ["bolt"],
    "Paradox":        ["paradox", "paradox-interactive", "paradoxinteractive"],
    "MAG Interactive":["mag-interactive", "maginteractive"],
}


def try_ashby(slug: str) -> tuple[int | None, list[str]]:
    """
    Returns (count, sample_titles).
    sample_titles helps user verify the slug points to the right company.
    """
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        r = requests.get(url, headers={"accept": "application/json"}, timeout=10)
        if r.status_code != 200:
            return None, []
        data = r.json()
        jobs = data.get("jobs", [])
        if not jobs:
            return 0, []
        sample_titles = [j.get("title", "") for j in jobs[:3]]
        return len(jobs), sample_titles
    except requests.RequestException:
        return None, []


def main():
    print(f"{'Company':<20} {'Slug':<25} {'Count':>6}   Sample titles")
    print("-" * 90)
    
    found = []
    for name, slugs in CANDIDATES.items():
        for slug in slugs:
            count, samples = try_ashby(slug)
            if count is None:
                continue  # 404 or error
            sample_str = " | ".join(samples)[:60]
            print(f"{name:<20} {slug:<25} {count:>6}   {sample_str}")
            if count > 0:
                found.append((name, slug, count, samples))
    
    print(f"\n{'=' * 90}")
    print("CANDIDATES — verify titles match the company you expect:")
    print(f"{'=' * 90}")
    for name, slug, count, samples in found:
        print(f"\n  {name} (slug={slug!r}, {count} jobs)")
        for t in samples:
            print(f"    - {t}")


if __name__ == "__main__":
    main()