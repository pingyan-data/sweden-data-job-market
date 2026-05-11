"""
Probe Teamtailor career sites for public feeds.

Goal: find a non-HTML JSON/XML/RSS endpoint that exposes jobs.
We try common patterns; for each:
  - GET it
  - Print status, content-type, size, first 500 chars
That lets us judge if it's useful before writing a scraper.
"""

import requests
from urllib.parse import urlparse

# Teamtailor companies confirmed so far
CAREER_SITES = {
    "Klarna":    "https://jobs.deel.com/klarna",
    "Schibsted": "https://schibsted.teamtailor.com",
    "Storytel":  "https://jobs.storytel.com",       # custom domain
    "Swedbank": "https://jobs.swedbank.com/",
    "Telenor": "https://careers.telenor.se", 
    "Cambio": "https://cambio.teamtailor.com",
    "Northmill": "https://careers.northmill.com/jobs",
    "Noba Bank": "https://careers.noba.bank/",
    "Resurs Bank": "https://careers.resurs.com/"
    # "NexterGroup": "https://techtalent.nexergroup.com/jobs", 
    # "Fortnox": "https://fortnoxab.teamtailor.com/jobs"
}

# Candidate endpoint patterns
PATTERNS = [
    # Basic pages
    "/",
    "/jobs",
    "/jobs/",
    "/careers",
    "/careers/jobs",
    "/en/jobs",
    "/en/careers",

    # Common data feeds
    "/jobs.json",
    "/jobs.xml",
    "/jobs.atom",
    "/jobs.rss",
    "/jobs/feed",
    "/feed.xml",
    "/rss.xml",
    "/atom.xml",

    # Sitemap discovery
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemaps.xml",
    "/jobs/sitemap.xml",
    "/sitemap-jobs.xml",
    "/sitemap_jobs.xml",
    "/careers/sitemap.xml",

    # API guesses
    "/api/jobs",
    "/api/v1/jobs",
    "/api/careers/jobs",
    "/api/job-postings",
    "/api/positions",
    "/api/openings",

    # Widget/embed
    "/widget/jobs",
    "/widgets/jobs",
    "/jobs/widget",
    "/job-list",
    "/job-list.js",

    # Common ATS-like variants
    "/positions",
    "/positions.json",
    "/openings",
    "/openings.json",
    "/vacancies",
    "/vacancies.json",
]

HEADERS = {
    "accept": "application/json, application/xml, text/xml, */*",
    # Some sites filter out clearly-bot user agents. We use a generic browser UA.
    "user-agent": "Mozilla/5.0 (compatible; SwedenJobMarketResearch/1.0; +https://github.com/pingyan-data/sweden-data-job-market)",
}


def probe(url: str) -> dict:
    """GET url, return summary dict. Don't follow redirects beyond 3 hops."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        return {
            "url": url,
            "status": r.status_code,
            "content_type": r.headers.get("content-type", "?"),
            "size": len(r.content),
            "final_url": r.url,
            "preview": r.text[:500] if r.status_code < 400 else "",
        }
    except requests.RequestException as e:
        return {"url": url, "error": str(e)}


def main():
    for company, base in CAREER_SITES.items():
        print(f"\n{'=' * 72}")
        print(f"  {company}  →  {base}")
        print('=' * 72)
        
        for pattern in PATTERNS:
            url = base + pattern
            result = probe(url)
            
            if "error" in result:
                print(f"  ❌ {pattern:<25}  ERROR: {result['error'][:50]}")
                continue
            
            status = result["status"]
            ctype = result["content_type"][:40]
            size = result["size"]
            
            # Mark interesting hits
            interesting = (
                status == 200 
                and size > 100 
                and not ctype.startswith("text/html")
            )
            marker = "⭐" if interesting else "  "
            
            print(f"  {marker} {pattern:<25}  status={status}  type={ctype:<40}  size={size}")
            
            if interesting:
                # Print first 300 chars of body so we can see what schema is
                preview = result["preview"][:300].replace("\n", " ")
                print(f"     preview: {preview}")
            elif status == 200 and ctype.startswith("text/html"):
                # HTML at 200 is the careers page itself — not a feed
                pass
            elif status == 301 or status == 302:
                print(f"     redirected to: {result['final_url']}")


if __name__ == "__main__":
    main()