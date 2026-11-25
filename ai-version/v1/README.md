# Polite books.toscrape.com scraper

Scrapes the first 3 catalogue pages of https://books.toscrape.com/ (a practice
sandbox) and every book they list (60 books).

## Run

```
pip install -r requirements.txt
python src/main.py
```

Python 3.12.

## Output

- `output/books.json`: valid records (title, product_url, price_text, price_gbp,
  availability_text, rating_text, description, source_page, fetched_at).
- `output/errors.json`: records that failed Pydantic validation, with the reason.
- `output/run-report.json`: start time, duration, pages fetched, cache hits,
  valid/invalid record counts, failed pages.

All three files are rewritten on each run, and records are keyed by
`product_url`, so a re-run still gives 60 records with no duplicates.

## Politeness

- User-Agent identifies the scraper; 10 s timeout; at least 0.5 s between requests.
- Only HTTP 200 is accepted. Timeouts, connection errors and 5xx get one retry;
  404/403 and other 4xx are never retried.
- Every page is cached in `cache/` (one JSON file per URL, including the original
  fetch time). Re-runs read from the cache and make no requests. Delete `cache/`
  to fetch fresh data.
- A page that fails to fetch or parse is logged, listed under `failed_pages`, and skipped.

## Layout

- `src/main.py`: entry point and run orchestration
- `src/fetcher.py`: HTTP, cache, delay, retry rules
- `src/parser.py`: BeautifulSoup extraction
- `src/models.py`: Pydantic `Book` model and price normalisation
