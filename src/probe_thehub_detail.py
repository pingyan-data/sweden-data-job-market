"""Inspect one The Hub job detail page to see what structured data is available."""

import requests
from bs4 import BeautifulSoup

# Pick the first 24-hex job URL from the listing probe
URL = "https://thehub.io/jobs/69cccd37270eb8094f71d845"

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

# JSON-LD (schema.org)
print("\n--- JSON-LD blocks ---")
ld_scripts = soup.find_all("script", type="application/ld+json")
for i, s in enumerate(ld_scripts):
    text = (s.string or "")
    print(f"\nBlock {i} ({len(text)} chars):")
    print(text[:1000])
    print("..." if len(text) > 1000 else "")

# Page title (often "Job Title | Company | The Hub")
print(f"\n--- <title> ---")
title_tag = soup.find("title")
print(f"  {title_tag.string if title_tag else '(none)'}")

# h1 (usually the job title)
print(f"\n--- <h1> ---")
h1 = soup.find("h1")
if h1:
    print(f"  {h1.get_text(' ', strip=True)}")

# Look for common meta tags
print(f"\n--- meta og:* tags ---")
for meta in soup.find_all("meta"):
    prop = meta.get("property") or meta.get("name") or ""
    if "og:" in prop or "twitter:" in prop or prop in ["description"]:
        content = meta.get("content", "")[:150]
        print(f"  {prop:<30}  {content}")