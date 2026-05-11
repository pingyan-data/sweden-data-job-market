import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


JOB_DETAIL_RE = re.compile(
    r"/klarna/job-details/([0-9a-fA-F-]{36})/overview"
)


def extract_job_id(url: str) -> str | None:
    match = JOB_DETAIL_RE.search(url)
    if not match:
        return None
    return match.group(1)


def clean_text(text: str) -> str:
    return " ".join((text or "").split())


async def scrape_klarna_jobs(
    url: str = "https://jobs.deel.com/klarna",
    output_path: str = "data/raw/klarna_jobs.json",
) -> list[dict]:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0 Safari/537.36"
            )
        )

        await page.goto(url, wait_until="networkidle", timeout=60_000)

        # Scroll a bit in case the page lazy-renders job cards.
        for _ in range(5):
            await page.mouse.wheel(0, 2000)
            await page.wait_for_timeout(700)

        links = await page.eval_on_selector_all(
            "a[href]",
            """
            els => els.map(a => ({
                text: a.innerText,
                href: a.href
            }))
            """,
        )

        await browser.close()

    seen = {}
    scraped_at = datetime.now(timezone.utc).isoformat()

    for link in links:
        href = link.get("href", "")
        text = clean_text(link.get("text", ""))

        job_id = extract_job_id(href)

        if not job_id:
            continue

        # De-duplicate by job_id.
        # If the same job appears twice, keep the longer text version,
        # because it usually contains title + location + employment type + salary.
        current = seen.get(job_id)

        candidate = {
            "source": "deel",
            "company": "Klarna",
            "job_id": job_id,
            "url": href,
            "raw_text": text,
            "scraped_at": scraped_at,
            "is_active": True,
        }

        if current is None or len(text) > len(current["raw_text"]):
            seen[job_id] = candidate

    jobs = sorted(seen.values(), key=lambda x: x["raw_text"])

    Path(output_path).write_text(
        json.dumps(jobs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return jobs


async def main():
    jobs = await scrape_klarna_jobs()

    print(f"Unique jobs found: {len(jobs)}")

    for job in jobs[:20]:
        print(job["job_id"], job["raw_text"][:120], "->", job["url"])


if __name__ == "__main__":
    asyncio.run(main())