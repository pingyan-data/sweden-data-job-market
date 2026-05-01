"""
Explore the structure of JobTech ads — what fields exist, how populated, what values.

We're NOT looking at job content here. We're answering:
- Which fields are present in most ads vs sparse?
- Which fields have categorical/structured values we can filter on?
- What does the schema look like for skills, occupations, etc.?
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

today = datetime.now().strftime("%Y-%m-%d")
raw_path = Path(f"data/raw/{today}_jobtech_all.json")
data = json.load(raw_path.open())
ads = list(data.values())
N = len(ads)
print(f"Loaded {N} ads from {raw_path.name}\n")


# === 1. Top-level field coverage ===
# How often is each top-level field non-empty?

print("=" * 70)
print("1. TOP-LEVEL FIELD COVERAGE")
print("=" * 70)
print(f"{'Field':<35} {'Non-null':>10} {'%':>6}")
print("-" * 55)

field_counts: Counter = Counter()
for ad in ads:
    for k, v in ad.items():
        if v not in (None, "", [], {}):
            field_counts[k] += 1

for field, count in field_counts.most_common():
    pct = 100 * count / N
    print(f"{field:<35} {count:>10} {pct:>5.0f}%")


# === 2. Inspect ONE ad in full ===
# Pick the ad with the MOST matched queries (likely high quality / well-tagged)

ads_sorted = sorted(ads, key=lambda a: -len(a.get("_matched_queries", [])))
exemplar = ads_sorted[0]

print("\n" + "=" * 70)
print("2. EXEMPLAR AD (highest match_count)")
print("=" * 70)
print(f"Headline: {exemplar.get('headline')}")
print(f"Employer: {(exemplar.get('employer') or {}).get('name')}")
print(f"Matched queries: {exemplar.get('_matched_queries')}")
print(f"\nFull structure (top-level keys and types):")
for k, v in exemplar.items():
    if isinstance(v, dict):
        print(f"  {k}: dict with keys {list(v.keys())}")
    elif isinstance(v, list):
        sample = v[0] if v else None
        print(f"  {k}: list[{len(v)}] sample={sample}")
    else:
        s = str(v)[:80]
        print(f"  {k}: {type(v).__name__} = {s}")


# === 3. Occupation field distribution ===
# This is THE most important field for our filtering question

print("\n" + "=" * 70)
print("3. OCCUPATION DISTRIBUTION")
print("=" * 70)

occupations = Counter()
occ_fields = Counter()
occ_groups = Counter()
for ad in ads:
    occ = ad.get("occupation") or {}
    occupations[occ.get("label")] += 1
    occ_field = ad.get("occupation_field") or {}
    occ_fields[occ_field.get("label")] += 1
    occ_group = ad.get("occupation_group") or {}
    occ_groups[occ_group.get("label")] += 1

print("\n--- occupation.label (specific job code) ---")
for label, count in occupations.most_common(20):
    print(f"  {count:4d}  {label}")

print("\n--- occupation_group.label ---")
for label, count in occ_groups.most_common(15):
    print(f"  {count:4d}  {label}")

print("\n--- occupation_field.label (broad area) ---")
for label, count in occ_fields.most_common(15):
    print(f"  {count:4d}  {label}")


# === 4. Skills / keywords / must_have ===

print("\n" + "=" * 70)
print("4. STRUCTURED SKILLS DATA")
print("=" * 70)

# Check what 'must_have' looks like
mh_present = sum(1 for ad in ads if ad.get("must_have"))
nh_present = sum(1 for ad in ads if ad.get("nice_to_have"))
kw_present = sum(1 for ad in ads if ad.get("keywords"))
print(f"must_have present:    {mh_present}/{N}")
print(f"nice_to_have present: {nh_present}/{N}")
print(f"keywords present:     {kw_present}/{N}")

# Look at must_have structure on the exemplar
mh = exemplar.get("must_have")
if mh:
    print(f"\nExemplar must_have keys: {list(mh.keys())}")
    for k, v in mh.items():
        if isinstance(v, list) and v:
            print(f"  {k}: {len(v)} items, sample = {v[0]}")

# Aggregate top skills across all ads
print("\n--- Top skills across all 'must_have.skills' ---")
all_skills = Counter()
for ad in ads:
    mh = ad.get("must_have") or {}
    for skill in (mh.get("skills") or []):
        label = skill.get("label") if isinstance(skill, dict) else skill
        if label:
            all_skills[label] += 1
for skill, count in all_skills.most_common(25):
    print(f"  {count:4d}  {skill}")

# Keywords (often AI-extracted)
print("\n--- 'keywords' structure on exemplar ---")
kw = exemplar.get("keywords")
if kw:
    if isinstance(kw, dict):
        print(f"  keys: {list(kw.keys())}")
        for k, v in kw.items():
            if isinstance(v, list) and v:
                print(f"    {k}: {len(v)} items, sample = {v[:3]}")


# === 5. Geography ===

print("\n" + "=" * 70)
print("5. GEOGRAPHY")
print("=" * 70)

municipalities = Counter()
regions = Counter()
remote = Counter()
for ad in ads:
    addr = ad.get("workplace_address") or {}
    municipalities[addr.get("municipality")] += 1
    regions[addr.get("region")] += 1
    remote[ad.get("remote_work")] += 1

print("\n--- Top 10 municipalities ---")
for m, c in municipalities.most_common(10):
    print(f"  {c:4d}  {m}")
print("\n--- remote_work values ---")
for r, c in remote.most_common():
    print(f"  {c:4d}  {r}")


# === 6. Description / size sanity check ===

print("\n" + "=" * 70)
print("6. DESCRIPTION FIELD")
print("=" * 70)

desc_lengths = []
for ad in ads:
    d = ad.get("description") or {}
    text = d.get("text") or ""
    desc_lengths.append(len(text))

if desc_lengths:
    desc_lengths.sort()
    print(f"  Description text length:")
    print(f"    min={desc_lengths[0]}  median={desc_lengths[len(desc_lengths)//2]}  max={desc_lengths[-1]}")
    print(f"  Empty descriptions: {sum(1 for l in desc_lengths if l == 0)}")