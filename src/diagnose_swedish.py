"""Look at all hits for Swedish queries to judge quality."""
import requests

BASE_URL = "https://jobsearch.api.jobtechdev.se/search"

for q in ["dataanalytiker", "dataingenjör"]:
    print(f"\n{'='*70}\nQuery: {q}\n{'='*70}")
    params = {"q": q, "limit": 30, "sort": "pubdate-desc"}
    resp = requests.get(BASE_URL, params=params,
                        headers={"accept": "application/json"}, timeout=30)
    data = resp.json()
    print(f"Total: {data.get('total', {}).get('value', 0)}")
    for h in data.get("hits", []):
        headline = h.get("headline", "")
        employer = (h.get("employer") or {}).get("name", "")
        print(f"  - {headline}  @  {employer}")