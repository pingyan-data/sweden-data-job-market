"""
One-off probe of Lever Postings API.

Goal: confirm endpoint works, see what schema looks like, count Spotify jobs.
We do NOT save anything yet — just look.
"""

import json
import requests

# Lever public API: https://github.com/lever/postings-api
URL = "https://api.lever.co/v0/postings/spotify?mode=json"

print(f"GET {URL}")
resp = requests.get(URL, headers={"accept": "application/json"}, timeout=30)
print(f"Status: {resp.status_code}")
print(f"Size:   {len(resp.content) / 1024:.1f} KB")

data = resp.json()
print(f"Total postings: {len(data)}")

if data:
    # Show one full posting so we see the schema
    print("\n--- ONE FULL POSTING (top-level keys) ---")
    first = data[0]
    for k, v in first.items():
        if isinstance(v, dict):
            print(f"  {k}: dict with keys {list(v.keys())}")
        elif isinstance(v, list):
            sample = v[0] if v else None
            print(f"  {k}: list[{len(v)}] sample={str(sample)[:80]}")
        else:
            s = str(v)[:80]
            print(f"  {k}: {type(v).__name__} = {s}")
    
    # Show first 10 titles + locations to eyeball
    print(f"\n--- FIRST 10 POSTINGS ---")
    for p in data[:10]:
        title = p.get("text", "")
        cats = p.get("categories") or {}
        loc = cats.get("location", "")
        team = cats.get("team", "")
        commitment = cats.get("commitment", "")
        print(f"  [{loc}] {title}  ({team} / {commitment})")
    
    # Quick filter: how many are in Stockholm or Sweden?
    print(f"\n--- LOCATION DISTRIBUTION (top 15) ---")
    from collections import Counter
    locs = Counter()
    for p in data:
        cats = p.get("categories") or {}
        locs[cats.get("location", "<none>")] += 1
    for loc, count in locs.most_common(15):
        print(f"  {count:4d}  {loc}")