"""
Probe: see what real job URLs look like on thehub.io.

We need to know the actual URL pattern of a job posting before we can
write a scraper. The earlier attempt regex'd /jobs/<id> too greedily
and matched the listing page itself.
"""

import requests
from bs4 import BeautifulSoup
from collections import Counter
from urllib.parse import urlparse

URL = "https://thehub.io/jobs/location/sweden"
HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    ),
}

resp = requests.get(URL, headers=HEADERS, timeout=30)
print(f"Status: {resp.status_code}")
print(f"Size: {len(resp.content)} bytes")
soup = BeautifulSoup(resp.text, "html.parser")

# Collect ALL anchor hrefs, count by path pattern
paths_by_depth = Counter()
sample_by_pattern = {}

for a in soup.find_all("a", href=True):
    href = a["href"]
    if href.startswith("http") and "thehub.io" not in href:
        continue  # external
    
    parsed = urlparse(href)
    path = parsed.path
    
    # Classify by first 2 path segments
    parts = [p for p in path.split("/") if p]
    if len(parts) == 0:
        key = "/"
    elif len(parts) == 1:
        key = f"/{parts[0]}"
    else:
        key = f"/{parts[0]}/{parts[1]}"
    
    paths_by_depth[key] += 1
    if key not in sample_by_pattern:
        sample_by_pattern[key] = href

print("\n--- Unique URL patterns on page (top 20) ---")
for pattern, count in paths_by_depth.most_common(20):
    sample = sample_by_pattern[pattern]
    print(f"  {count:4d}  {pattern:<35}  e.g. {sample}")

# Now: see if there's structured data (JSON-LD) on the page
print("\n--- Looking for embedded structured data ---")
for script in soup.find_all("script", type="application/ld+json"):
    text = (script.string or "")[:300]
    print(f"  JSON-LD found ({len(script.string or '')} chars):")
    print(f"    {text}")
    print()

# Look for Next.js data — sites built on Next.js dump everything in __NEXT_DATA__
nextdata = soup.find("script", id="__NEXT_DATA__")
if nextdata:
    text = (nextdata.string or "")[:500]
    print(f"\n--- __NEXT_DATA__ found ({len(nextdata.string or '')} chars total) ---")
    print(f"  First 500 chars:")
    print(f"    {text}")