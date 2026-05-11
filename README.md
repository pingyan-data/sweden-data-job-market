# Sweden Data Job Market Indicator

A weekly tracker of data, ML, and AI job postings across Sweden.

**Why this exists.** Most "Sweden tech job market" reports rely on a single source (LinkedIn or one job board) and stop at title counts. This project aggregates **6 independent sources**, applies a transparent filtering pipeline, and produces a dataset suitable for trend analysis.

**Status.** Data collection pipeline complete. ~560 unique Sweden ads in latest snapshot. Analysis and weekly newsletter in progress.

---

## Coverage today

| Source | Type | Companies | Sweden ads |
|---|---|---:|---:|
| Arbetsförmedlingen JobTech API | Government aggregator | ~150 employers | 224 |
| Lever | Public ATS API | 1 (Spotify) | 19 |
| Greenhouse | Public ATS API | 2 (Mentimeter, Wolt) | 47 |
| Ashby | Public ATS API | 1 (Lovable) | 45 |
| Teamtailor RSS | Public RSS feed | 7 (incl. Swedbank, Schibsted, Storytel) | 113 |
| Klarna (Deel) | JS-rendered scrape | 1 (Klarna, w/ salary data) | 56 |
| The Hub | HTML + meta scrape | ~40 startups | 60 |
| **Total** | | **~200** | **~560** |

**Coverage gaps (known):** LinkedIn-exclusive postings, Workday-based ATS (large enterprise), custom corporate career sites. Not pursued because the marginal effort vs. coverage gain is poor.

---

## Repo layout

```
src/
├── fetch_jobtech.py       PRIMARY: JobTech API (multi-query, dedup)
├── filter_ads.py          PRIMARY: headline-first filter pipeline (v4)
├── fetch_lever.py         SECONDARY: Lever Postings API
├── fetch_greenhouse.py    SECONDARY: Greenhouse Job Board API
├── fetch_ashby.py         SECONDARY: Ashby Posting API
├── fetch_teamtailor.py    SECONDARY: Teamtailor RSS feeds (XML namespaces)
├── fetch_klarna.py        SECONDARY: Klarna via Deel (Playwright)
├── fetch_thehub.py        SECONDARY: The Hub scrape (BeautifulSoup)
├── probe_*.py             One-off ATS/schema discovery scripts
└── explore_schema.py      One-off field-coverage exploration
data/
├── raw/                   Per-source JSON dumps (gitignored, regenerable)
│   ├── jobtech/
│   ├── lever/
│   ├── greenhouse/
│   ├── ashby/
│   ├── teamtailor/
│   ├── klarna/
│   └── thehub/
└── processed/             After filtering & tagging

```

## Running it

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # required for fetch_klarna.py

# Each fetcher writes to data/raw/<source>/YYYY-MM-DD_*.json
python src/fetch_jobtech.py
python src/fetch_lever.py
python src/fetch_greenhouse.py
python src/fetch_ashby.py
python src/fetch_teamtailor.py
python src/fetch_klarna.py
python src/fetch_thehub.py

python src/filter_ads.py      # applies filtering to PRIMARY data
```

---

## Development log

### 2026-05-01 — Session 1: PRIMARY data source (JobTech API)

- Surveyed candidate data sources: Indeed (blocked), LinkedIn (ToS), various Swedish job boards.
- Chose **Arbetsförmedlingen JobTech API** as PRIMARY: open, well-documented, no key required, covers most of the Swedish job market via Platsbanken.
- Implemented multi-query fetcher with 16 English + Swedish phrases (`"data scientist"`, `"data engineer"`, `dataingenjör`, etc.) and deduplication by ad ID.
- **Bug fix iteration**: discovered the API's `q=` parameter does AND-matching on individual tokens, not phrase matching. Query `data scientist` returned 87 ads but included false positives like "Data Steward" because both `data` and `scientist` appeared in unrelated fields. Switched to quoted phrase queries (`'"data scientist"'`) — false positives dropped 99%.
- Built a 4-stage filter pipeline (`filter_ads.py` v4) using a **headline-first strategy**: cleaner than relying on `occupation.label`, which recruiters often mis-tag (e.g. an `Applikationskonsult` listing that is actually a Data Scientist role).
- Final PRIMARY dataset: 224 clean Sweden ads from 241 raw.
- Notable finding: ~48% of Platsbanken data ads are posted by consultancies, not product companies. Tagged each ad with `_employer_type` (public / consultancy / company) for downstream filtering.

### 2026-05-09 — Session 2: SECONDARY part 1 — Lever, Greenhouse, Ashby

- Goal: cover product companies that bypass Platsbanken (Spotify, Klarna, banks, etc.).
- Built `probe_ats.py` to detect which ATS each target company uses.
- **Slug collision incident**: the Greenhouse board token `lovable` returned 51 jobs, but inspection revealed they were all Italian retail jobs (`Adv_Bergamo`, etc.) — a different company also called Lovable had registered that slug first. Lesson: verify content (job titles), not just HTTP status. The real Lovable.dev uses Ashby (`api.ashbyhq.com/posting-api/job-board/lovable`).
- Findings on ATS landscape in Sweden:
  - Lever: virtually only Spotify (1 of 20 candidates checked)
  - Greenhouse: 3 hits — Mentimeter, Wolt, Truecaller (Truecaller had 0 active postings)
  - Ashby: only Lovable (it's a newer ATS, used by US-style startups)
- Total SECONDARY added: 4 companies, 111 Sweden ads. Klarna and banks still not covered.

### 2026-05-10 — Session 3: SECONDARY part 2 — Teamtailor, Klarna, The Hub

- **Teamtailor** is the most popular ATS for Swedish-headquartered companies. Their authenticated API requires per-company keys, but each Teamtailor career site exposes a public **RSS feed** at `/jobs.rss`.
- Confirmed 7 Teamtailor career sites: Schibsted, Storytel, Swedbank (!), Telenor SE, Cambio, Noba Bank, Resurs Bank.
- **XML namespace bug**: my first parser returned 0 ads from all 7 sites despite RSS clearly containing `<city>Stockholm</city>`. Root cause: Teamtailor uses a custom XML namespace `xmlns:tt="https://teamtailor.com/locations"` for several fields (`<tt:locations>`, `<tt:department>`, `<tt:role>`). Python's ElementTree exposes namespaced tags as `{https://teamtailor.com/locations}locations`, not just `locations`. After adding namespace prefixes to `find()` calls, Sweden total went from 0 → 113.
- **Klarna** migrated their careers page to Deel (`jobs.deel.com/klarna`). The page is JavaScript-rendered, requiring Playwright. Klarna is the **only source in this dataset that publishes salary ranges publicly** — 52 of 56 Sweden roles include compensation. Their data has a unit ambiguity worth a newsletter post on its own (some ranges look monthly, others annual, no labeling).
- **The Hub** (Nordic startup board) covers many companies that don't appear on Platsbanken (Innovx, Waitwhile, Devolens, Voi, GeoGuessr, Depict). Job IDs are 24-char hex (MongoDB ObjectIDs). Location is extracted heuristically from listing card text because detail pages have no JSON-LD or structured location field.

### Next sessions (planned)

- Unified schema merge across all 7 sources into a single `clean.json` (date-stamped weekly).
- Apply PRIMARY-style filtering to SECONDARY data (headline-first; same patterns).
- Weekly snapshot diffing to detect new openings vs. closures.
- Keyword extraction from descriptions (Snowflake, dbt, Spark, etc.) for trend reporting.
- First newsletter issue.

---

## Notes & design choices

- **Data files are gitignored.** Every fetcher is deterministic given the live API state; raw JSONs would just bloat the repo. Regenerate by running the scripts.
- **Each fetcher writes a `_raw` and `_normalized` JSON.** Raw preserves the full source schema for re-analysis; normalized is a flat view with consistent field names (`headline`, `employer`, `municipality`, `description_text`, etc.) for downstream merging.
- **No `requirements.txt` pin tightness.** This is a personal weekly tool, not a library.
