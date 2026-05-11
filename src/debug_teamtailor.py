"""
Debug: take ONE Storytel item and run our parse_locations on it.
Print what each step returns, so we see where the bug is.
"""

import requests
import xml.etree.ElementTree as ET

URL = "https://jobs.storytel.com/jobs.rss"
resp = requests.get(URL, timeout=30, headers={"user-agent": "Mozilla/5.0"})
root = ET.fromstring(resp.content)


items = root.findall(".//item")
item = items[0]
print("Tags of all children of first item:")
for child in item:
    print(f"  {child.tag!r}")
print(f"Total items: {len(items)}")

item = items[0]
print(f"\nFirst item title: {item.findtext('title')}")

# Step 1: find <locations> container
locations_container = item.find("locations")
print(f"\nlocations_container: {locations_container}")
print(f"  is None? {locations_container is None}")

if locations_container is not None:
    # Step 2: list children of <locations>
    print(f"  children of <locations>:")
    for child in locations_container:
        print(f"    tag={child.tag!r}  text={(child.text or '').strip()[:30]!r}")
    
    # Step 3: try findall("location")
    locs = locations_container.findall("location")
    print(f"\n  findall('location') returned: {len(locs)} items")
    
    # Step 4: for each location, get city + country
    for i, loc in enumerate(locs):
        print(f"\n  Location {i}:")
        # list ALL children of <location>
        for child in loc:
            print(f"    <{child.tag}> text={(child.text or '').strip()[:50]!r}")
        # Now use findtext like our real code does
        city = loc.findtext("city")
        country = loc.findtext("country")
        print(f"    findtext('city')    -> {city!r}")
        print(f"    findtext('country') -> {country!r}")