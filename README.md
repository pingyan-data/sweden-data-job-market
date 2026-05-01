# Sweden Data Job Market Indicator

Weekly tracker of data, ML, and AI job postings in Sweden.

**Status**: in development (PRIMARY data source: ingestion + filtering done)

## Data sources

- **PRIMARY**: Arbetsförmedlingen JobTech JobSearch API (open, public)
- **SECONDARY** (planned): Teamtailor / Greenhouse careers pages of Swedish tech companies

## What works today

- `src/fetch_jobtech.py` — multi-query fetch with deduplication
- `src/filter_ads.py` — headline-first filtering pipeline (v4)
- `src/explore_schema.py` — one-off field-coverage exploration
