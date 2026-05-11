"""
Look at one Teamtailor RSS feed in full to understand the schema.
We need to know what fields are available per <item> before writing a fetcher.
"""

import requests
import xml.etree.ElementTree as ET

URL = "https://jobs.storytel.com/jobs.rss"  # smallest feed, faster to inspect

resp = requests.get(URL, timeout=30, headers={
    "user-agent": "Mozilla/5.0 (compatible; SwedenJobMarketResearch/1.0)"
})
print(f"Status: {resp.status_code}")
print(f"Size:   {len(resp.content)} bytes")

# Parse XML
root = ET.fromstring(resp.content)

# Show namespaces (Teamtailor uses tt: namespace for extra fields)
print("\n--- Namespaces declared in root ---")
for k, v in root.attrib.items():
    print(f"  {k}: {v}")

# Find all <item> elements
items = root.findall(".//item")
print(f"\nTotal <item> elements: {len(items)}")

if items:
    print(f"\n--- FIRST ITEM (recursive, all descendants) ---")
    
    def walk(elem, depth=0):
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        text = (elem.text or "").strip()[:150]
        prefix = "  " * depth
        # Build attrib string
        attrib_str = ""
        if elem.attrib:
            attrib_str = f"  attribs={dict(elem.attrib)}"
        print(f"{prefix}<{tag}>{attrib_str}")
        if text:
            print(f"{prefix}  text: {text!r}")
        for child in elem:
            walk(child, depth + 1)
    
    first = items[0]
    walk(first)
    
    # Also check item 2 to compare (Storytel only has 3 items, but
    # we want to confirm the pattern)
    if len(items) > 1:
        print(f"\n--- SECOND ITEM (recursive) ---")
        walk(items[1])