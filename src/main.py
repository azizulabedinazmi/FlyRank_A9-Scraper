"""The polite scraper: Books to Scrape, first 3 catalogue pages, 60 books -> clean, validated JSON.

Run from the repo root:
    python src/main.py                      # normal run (reads the cache, fetches only what's missing)
    python src/main.py --refresh            # ignore the cache and fetch everything again
    python src/main.py --with-broken-url    # add one made-up book URL to prove a bad page is skipped
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fetch import MIN_DELAY_S, TIMEOUT_S, USER_AGENT, Fetcher, FetchError
from parse import ParseError, parse_book, parse_catalogue
from store import store, validate, write_json

ROOT = Path(__file__).resolve().parent.parent
START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3
# Made up on purpose: a book page that doesn't exist. One request, one 404, never retried.
BROKEN_URL = "https://books.toscrape.com/catalogue/this-book-does-not-exist_99999/index.html"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def log(event: str, url: str, **fields) -> None:
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    print(f"{event:<10} {url} {extra}".rstrip(), flush=True)


def fetch_logged(fetcher: Fetcher, url: str):
    page = fetcher.get(url)
    log("CACHE HIT" if page.from_cache else "FETCH", page.url, status=page.status, bytes=page.size)
    return page


def discover(fetcher: Fetcher, failed: list[dict]) -> tuple[int, list[tuple[str, str]]]:
    """Walk the catalogue by following the site's own "next" link, stopping after MAX_CATALOGUE_PAGES.

    Returns (catalogue pages read, [(book_url, catalogue page it was found on), ...]).
    """
    url, pages, found = START_URL, 0, []
    while url and pages < MAX_CATALOGUE_PAGES:
        try:
            page = fetch_logged(fetcher, url)
        except FetchError as e:  # without this page there's no "next" link to follow: stop discovering, keep going
            log("FAILED", e.url, reason=e.reason)
            failed.append({"url": e.url, "stage": "catalogue", "reason": e.reason})
            break
        books, url = parse_catalogue(page.html, page.url)
        found += [(b, page.url) for b in books]
        pages += 1
    return pages, found


def unique(found: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop repeated book URLs, keeping the first page each one was seen on."""
    seen, out = set(), []
    for url, src in found:
        if url not in seen:
            seen.add(url)
            out.append((url, src))
    return out


def main() -> int:
    started_at, t0 = now(), time.monotonic()
    fetcher = Fetcher(ROOT / "cache", refresh="--refresh" in sys.argv)
    failed: list[dict] = []

    pages, found = discover(fetcher, failed)
    books = unique(found)
    if "--with-broken-url" in sys.argv:
        books.append((BROKEN_URL, START_URL))
    print(f"catalogue_pages={pages}, discovered={len(found)}, unique_urls={len(books)}")

    raw = []
    for url, source_page in books:  # each page on its own: one bad page is logged and skipped
        try:
            page = fetch_logged(fetcher, url)
            raw.append(parse_book(page.html, url, source_page, page.fetched_at))
        except FetchError as e:
            log("FAILED", e.url, reason=e.reason)
            failed.append({"url": e.url, "stage": "detail", "reason": e.reason})
        except ParseError as e:
            log("FAILED", url, reason=str(e))
            failed.append({"url": url, "stage": "parse", "reason": str(e)})

    good, bad = validate(raw)
    store(ROOT / "output", good, bad)

    report = {
        "started_at": started_at,
        "finished_at": now(),
        "duration_s": round(time.monotonic() - t0, 2),
        "catalogue_pages": pages,
        "book_urls_discovered": len(found),
        "book_urls_unique": len(books),
        "detail_pages_parsed": len(raw),
        "pages_fetched": fetcher.stats["pages_fetched"],
        "network_requests": fetcher.stats["network_requests"],
        "retries": fetcher.stats["retries"],
        "cache_hits": fetcher.stats["cache_hits"],
        "valid_records": len(good),
        "invalid_records": len(bad),
        "failed_pages": len(failed),
        "failures": failed,
        "politeness": {"user_agent": USER_AGENT, "min_delay_s": MIN_DELAY_S, "timeout_s": TIMEOUT_S},
    }
    write_json(ROOT / "output" / "run-report.json", report)
    print(f"valid_records={len(good)}, invalid_records={len(bad)}, failed_pages={len(failed)}, "
          f"network_requests={report['network_requests']}, cache_hits={report['cache_hits']}, "
          f"duration_s={report['duration_s']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
