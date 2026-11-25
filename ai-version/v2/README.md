# Polite Books Scraper (FlyRank A9)

A polite scraper for the practice sandbox https://books.toscrape.com/ built with
requests, BeautifulSoup and Pydantic.

## Run

```bash
pip install -r requirements.txt
python src/main.py
```

Python 3.12. Outputs go to `output/`, downloaded pages to `cache/` (both at the project root, wherever you run it from).

## What it does

1. Starts at `https://books.toscrape.com/catalogue/page-1.html` and follows only the page's own **next** link, up to 3 catalogue pages. URLs are never built or guessed. If a catalogue page fails, discovery stops and the failure goes into the report.
2. Visits every book page found (60 when all goes well) and pulls out `title`, `product_url`, `price_text`, `availability_text`, `rating_text`, `description` (null when missing), `source_page` and `fetched_at`. `price_text` is turned into the number `price_gbp`.
3. All selectors are limited to `article.product_page` / `div.product_main`. If that area is missing, the page counts as failed (`parse_error`). The scraper never falls back to searching the whole document.
4. Each record is checked by the `Book` Pydantic model. Records that pass go to `output/books.json`, keyed by `product_url` so there are no duplicates. The file is rewritten on every run, so a second run still gives 60 records. Records that fail go to `output/errors.json` with the reasons.
5. `output/run-report.json` records the start and finish time, duration, pages fetched from the network, cache hits, HTTP requests, valid and invalid record counts, and the failed pages with their kind and reason.

## Politeness

- User-Agent: `FlyRankInternship-A9/1.0 (+https://github.com/azizulabedinazmi/FlyRank_A9-Scraper)`
- 10 s timeout on every request.
- At least 0.75 s between network requests, measured from the end of the previous one. The required minimum is 0.5 s; the extra margin covers timer jitter.
- Only HTTP 200 is accepted. Redirects are not followed and count as failures.
- One retry, after a 1.5 s wait, on timeouts and 5xx responses. There is no retry on 4xx such as 403 or 404.
- Only `books.toscrape.com` URLs are requested.
- Every 200 page is cached in `cache/` (`<sha256>.html` plus `<sha256>.json` metadata). On a re-run, cached pages cause no network traffic, and `fetched_at` stays the original download time.
- One broken page is logged and skipped. It never stops the run.

Delete `cache/` to force a fresh download.

## Layout

```
src/main.py      orchestration and output files
src/config.py    URLs, user-agent, delays, paths
src/fetcher.py   polite HTTP client + disk cache
src/parser.py    scoped BeautifulSoup extraction
src/models.py    Pydantic Book model + price normalisation
```
