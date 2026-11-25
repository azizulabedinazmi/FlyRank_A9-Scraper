> Live run against the real site. **The three Run C failures in this file were a bug in my harness, not in v1**: it built the doctored page from v1's JSON cache file instead of HTML. Fixed and re-run offline in results-ai-v1.md.

## AI v1

| Check | Result | Detail |
|---|---|---|
| A: run finishes (exit 0) | PASS | exit 0 in 35s |
| A: 63 requests (3 catalogue + 60 books) | PASS | 63 |
| A: >= 0.5 s between requests (measured) | FAIL | min gap 0.49s, median 0.50s |
| A: identifying user-agent | PASS | PoliteBooksScraper/1.0 (educational scraper for books.toscrape.com; python-requests) |
| A: timeout on every request | PASS | {10} |
| A: exactly 60 records | PASS | 60 |
| A: 60 unique product_urls | PASS | 60 |
| A: every price_gbp is a number | PASS |  |
| A: every URL https | PASS |  |
| A: all 8 raw fields + price_gbp present | PASS |  |
| A: errors.json exists | PASS |  |
| A: run-report.json written | PASS | ['cache_hits', 'duration_seconds', 'failed_pages', 'invalid_records', 'pages_fetched', 'start_time', 'valid_records'] |
| B: rerun network requests | PASS | 0 requests, 2.5s |
| B: exactly 60 records | PASS | 60 |
| B: 60 unique product_urls | PASS | 60 |
| B: every price_gbp is a number | PASS |  |
| B: every URL https | PASS |  |
| B: all 8 raw fields + price_gbp present | PASS |  |
| C: could remove 3 pages from the cache | PASS | {'starving-hearts-triangular-trade-trilogy-1_990': 1, 'in-her-wake_980': 1, 'the-four-agreements-a-practical-guide-to-pe |
| C: run survives a 503 and a 404 (exit 0) | PASS | exit 0 |
| C: 503 retried (2-3 calls), then skipped | PASS | 2 calls |
| C: 404 not retried (1 call), skipped | PASS | 1 calls |
| C: the other 58 records survive | FAIL | 57 |
| C: report says failed_pages = 2 | PASS | 2 |
| C: missing description stored as null | FAIL | record missing |
| C: decoy £999.99 ignored, real price kept | FAIL | record missing |

**22/26 passed**
