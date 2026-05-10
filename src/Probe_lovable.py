"""Quick probe of Lovable Greenhouse output to see why Sweden filter found 0."""
import requests
from collections import Counter

URL = "https://boards-api.greenhouse.io/v1/boards/lovable/jobs"
data = requests.get(URL, headers={"accept": "application/json"}, timeout=30).json()
jobs = data.get("jobs", [])

print(f"Total jobs: {len(jobs)}\n")

# Show first 10 jobs with their location and offices
print("--- First 10 jobs (full location info) ---")
for j in jobs[:10]:
    title = j.get("title", "")
    location = j.get("location") or {}
    location_name = location.get("name", "")
    offices = j.get("offices") or []
    office_names = [o.get("name") for o in offices]
    print(f"  Title:    {title}")
    print(f"  location: {location_name!r}")
    print(f"  offices:  {office_names}")
    print()

# All location.name values
print("--- All location.name values (frequency) ---")
locs = Counter()
for j in jobs:
    locs[(j.get("location") or {}).get("name", "<empty>")] += 1
for loc, count in locs.most_common():
    print(f"  {count:3d}  {loc!r}")

# All office names
print("\n--- All office names (frequency) ---")
all_offices = Counter()
for j in jobs:
    for o in (j.get("offices") or []):
        all_offices[o.get("name", "<empty>")] += 1
for o, count in all_offices.most_common():
    print(f"  {count:3d}  {o!r}")