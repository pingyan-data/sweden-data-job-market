"""Inspect today's fetched data — look at what we got."""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

today = datetime.now().strftime("%Y-%m-%d")
p = Path(f"data/raw/{today}_jobtech_summary.json")
data = json.load(p.open())

print(f"Loaded {len(data)} ads from {p}")

# === Check 1: Confidence breakdown ===
print(f"\n=== Confidence breakdown ===")
high = [a for a in data if a["match_count"] >= 3]
medium = [a for a in data if a["match_count"] == 2]
low = [a for a in data if a["match_count"] == 1]
print(f"  High   (≥3 queries matched): {len(high):4d}")
print(f"  Medium (2 queries matched):  {len(medium):4d}")
print(f"  Low    (1 query  matched):   {len(low):4d}")

# === Check 2: Sample low-confidence (where false positives hide) ===
print(f"\n=== Sample of LOW confidence ads (1-query matches) ===")
print("(grouped by which query matched them)")
by_query = {}
for ad in low:
    q = ad["matched_queries"][0]
    by_query.setdefault(q, []).append(ad)

for q in sorted(by_query.keys()):
    ads = by_query[q]
    print(f"\n  [{q}]  ({len(ads)} ads, showing first 5)")
    for a in ads[:5]:
        print(f"    - {a['headline']}  @  {a['employer']}")

# === Check 3: Target company coverage ===
targets = ["klarna", "spotify", "storytel", "king", "embark", "kry",
           "sana", "mentimeter", "tink", "voi", "epidemic sound",
           "qasa", "bankid", "hexagon", "tacton", "neko", "alva",
           "swedbank", "seb", "handelsbanken", "avanza", "lendo",
           "schibsted", "ica", "volvo", "stena", "stegra"]

print(f"\n=== Target company coverage ===")
for t in sorted(targets):
    matches = [a for a in data if a["employer"] and t in a["employer"].lower()]
    if matches:
        print(f"  {t:20s}: {len(matches)} ads")
        for m in matches[:3]:
            print(f"      - {m['headline']}")
    else:
        print(f"  {t:20s}: 0")