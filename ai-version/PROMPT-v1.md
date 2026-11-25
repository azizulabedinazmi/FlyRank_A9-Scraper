# Prompt v1 (bonus: AI rematch)

Sent to a fresh AI session (Claude) with no access to this repo.

```text
Write a polite web scraper in Python (requests + BeautifulSoup + Pydantic) for https://books.toscrape.com/, a practice
sandbox.

- Scope: only the first 3 catalogue pages (start at https://books.toscrape.com/catalogue/page-1.html and follow the
  "next" link), then visit every book page they list: 60 books.
- For each book, extract: title, product_url (absolute), price_text (e.g. "£51.77"), availability_text,
  rating_text (One..Five), description (null if missing), source_page (the catalogue page it was found on),
  fetched_at (ISO timestamp).
- Normalize price_text to a number price_gbp. Validate every record with a Pydantic model before storing it;
  records that fail go to output/errors.json with the reason.
- Write the valid records to output/books.json. Running the scraper twice must still give 60 records, no duplicates.
- Be polite: send a user-agent that identifies the scraper, use a timeout, wait at least 0.5 s between requests,
  only accept status 200, and cache every page to a cache/ folder so re-runs don't hit the site again.
- One broken page must not crash the run: log it and skip it. Retry once on timeouts and 5xx errors, never on 404/403.
- At the end write output/run-report.json with start time, duration, pages fetched, cache hits, valid records,
  invalid records and failed pages.
- Entry point: python src/main.py
```
