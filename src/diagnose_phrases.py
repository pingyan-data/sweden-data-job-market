"""Verify phrase matching works correctly across multiple queries."""
import requests

BASE_URL = "https://jobsearch.api.jobtechdev.se/search"

queries = [
    '"data scientist"',
    '"data engineer"',
    '"machine learning engineer"',
    '"ai engineer"',
    '"analytics engineer"',
    '"analytical engineer"',
    '"mlops engineer"',
    '"research scientist"',
    'mlops',
    'dataanalytiker',
    'dataingenjör',
]

print(f"{'Query':<35} {'Total':>6}   Sample headline")
print("-" * 90)
for q in queries:
    params = {"q": q, "limit": 1, "sort": "pubdate-desc"}
    resp = requests.get(BASE_URL, params=params,
                        headers={"accept": "application/json"}, timeout=30)
    data = resp.json()
    total = data.get("total", {}).get("value", 0)
    hits = data.get("hits", [])
    sample = hits[0].get("headline", "")[:50] if hits else "(no hits)"
    print(f"{q:<35} {total:>6}   {sample}")