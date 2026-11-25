# Prompt v2 (rematch)

v1 passed 26/27 checks but set its delay to exactly 0.5 s (some measured gaps came out at 0.499 s), sent a user-agent
with no contact link, guessed catalogue URLs (`page-N+1`) when a page failed, and fell back to parsing the *whole
document* when the product area was missing, which turned an error page into "a book" titled "Something went wrong"
at £1.00. v2 = v1 + the NEW block. Sent to a fresh AI session.

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

NEW:
- The user-agent must name the project and include a contact URL, e.g.
  "FlyRankInternship-A9/1.0 (+https://github.com/<you>/<repo>)".
- 0.5 s is a floor, not a target: use 0.75 s between requests so timer jitter can never take a gap below 0.5 s.
- Never construct or guess URLs. Pagination comes only from the page's own "next" link; if a catalogue page fails,
  stop discovering and record the failure.
- Scope every selector to the product area (article.product_page / div.product_main). If that area is missing, the
  page is a failed page (a parse error in the report), never parsed from the whole document.
- Wait a moment before the retry (about 1-2 s), not just the normal delay.
- On a cache hit, fetched_at must stay the time the page was originally downloaded.
```
