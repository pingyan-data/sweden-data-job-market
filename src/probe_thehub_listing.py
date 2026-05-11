"""See what info each job's anchor on the LISTING page carries."""

import requests
import re
from bs4 import BeautifulSoup

URL = "https://thehub.io/jobs/location/sweden"
HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    ),
}

JOB_URL_RE = re.compile(r"^/jobs/([0-9a-f]{24})$")

resp = requests.get(URL, headers=HEADERS, timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")

print("--- All real job anchors (with surrounding context) ---")
count = 0
for a in soup.find_all("a", href=True):
    href = a["href"]
    m = JOB_URL_RE.match(href)
    if not m:
        continue
    count += 1
    
    # Anchor's own text
    inner = " ".join(a.get_text(" ", strip=True).split())
    
    # Walk up to find parent card — maybe location is in a sibling
    parent = a.parent
    parent_text = " ".join(parent.get_text(" ", strip=True).split())[:300]
    
    print(f"\nJob {count}: {href}")
    print(f"  anchor text:  {inner!r}")
    print(f"  parent text:  {parent_text!r}")
    
    if count >= 5:
        break