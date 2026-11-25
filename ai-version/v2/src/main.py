"""Entry point: python src/main.py

1. Walk the first MAX_CATALOGUE_PAGES catalogue pages, following only the
   page's own "next" link. If a catalogue page fails, discovery stops.
2. Visit every book page discovered, extract fields, validate with Pydantic.
3. Write output/books.json, output/errors.json and output/run-report.json.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

import config
from fetcher import FetchError, PoliteFetcher
from models import Book, normalize_price
from parser import ParseError, parse_book, parse_catalogue

log = logging.getLogger("scraper")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def failure(url: str, stage: str, kind: str, reason: str) -> dict:
    return {"url": url, "stage": stage, "kind": kind, "reason": reason}


def discover_books(fetcher: PoliteFetcher, failed_pages: list[dict]) -> list[tuple[str, str]]:
    """Return (book_url, source_page) pairs in discovery order, de-duplicated."""
    found: dict[str, str] = {}
    url: str | None = config.START_URL
    pages_seen = 0

    while url and pages_seen < config.MAX_CATALOGUE_PAGES:
        pages_seen += 1
        try:
            page = fetcher.fetch(url)
            catalogue = parse_catalogue(page.html, page.url)
        except FetchError as exc:
            log.error("catalogue page failed, stopping discovery: %s (%s)", url, exc)
            failed_pages.append(failure(url, "catalogue", exc.kind, exc.message))
            break
        except ParseError as exc:
            log.error("catalogue page unparsable, stopping discovery: %s (%s)", url, exc)
            failed_pages.append(failure(url, "catalogue", "parse_error", str(exc)))
            break

        for book_url in catalogue.book_urls:
            found.setdefault(book_url, page.url)
        log.info("catalogue %s -> %d books", page.url, len(catalogue.book_urls))
        url = catalogue.next_url  # only ever the page's own "next" link

    return list(found.items())


def scrape_book(
    fetcher: PoliteFetcher, book_url: str, source_page: str
) -> tuple[Book | None, dict | None]:
    """Fetch + parse + validate one book. Returns (book, error_entry).

    Raises FetchError / ParseError for page-level failures.
    """
    page = fetcher.fetch(book_url)
    fields = parse_book(page.html)
    raw = {
        "title": fields["title"],
        "product_url": page.url,
        "price_text": fields["price_text"],
        "price_gbp": normalize_price(fields["price_text"]),
        "availability_text": fields["availability_text"],
        "rating_text": fields["rating_text"],
        "description": fields["description"],
        "source_page": source_page,
        "fetched_at": page.fetched_at,  # original download time, even on cache hit
    }
    try:
        return Book.model_validate(raw), None
    except ValidationError as exc:
        reasons = [
            f"{'.'.join(str(p) for p in err['loc']) or 'record'}: {err['msg']}"
            for err in exc.errors()
        ]
        return None, {"product_url": book_url, "source_page": source_page,
                      "reasons": reasons, "record": raw}


def run() -> int:
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()

    fetcher = PoliteFetcher()
    failed_pages: list[dict] = []
    books: dict[str, dict] = {}  # keyed by product_url -> no duplicates
    errors: list[dict] = []

    log.info("User-Agent: %s", config.USER_AGENT)
    targets = discover_books(fetcher, failed_pages)
    log.info("discovered %d book pages", len(targets))

    for book_url, source_page in targets:
        try:
            book, error = scrape_book(fetcher, book_url, source_page)
        except FetchError as exc:
            log.error("skipping book page %s (%s)", book_url, exc)
            failed_pages.append(failure(book_url, "book", exc.kind, exc.message))
            continue
        except ParseError as exc:
            log.error("skipping book page %s (parse error: %s)", book_url, exc)
            failed_pages.append(failure(book_url, "book", "parse_error", str(exc)))
            continue
        except Exception as exc:  # never let one page crash the run
            log.exception("unexpected error on %s", book_url)
            failed_pages.append(failure(book_url, "book", "unexpected_error", repr(exc)))
            continue

        if book is not None:
            books[book.product_url] = book.model_dump(mode="json")
        else:
            log.warning("invalid record %s: %s", book_url, "; ".join(error["reasons"]))
            errors.append(error)

    # Full rewrite each run (not append): re-running yields the same 60 records.
    write_json(config.BOOKS_FILE, list(books.values()))
    write_json(config.ERRORS_FILE, errors)

    duration = time.monotonic() - t0
    report = {
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(duration, 3),
        "user_agent": config.USER_AGENT,
        "pages_fetched": fetcher.stats.pages_fetched,
        "cache_hits": fetcher.stats.cache_hits,
        "http_requests": fetcher.stats.http_requests,
        "valid_records": len(books),
        "invalid_records": len(errors),
        "failed_pages_count": len(failed_pages),
        "failed_pages": failed_pages,
    }
    write_json(config.REPORT_FILE, report)

    log.info(
        "done in %.1fs: %d valid, %d invalid, %d failed pages, %d fetched, %d cache hits",
        duration, len(books), len(errors), len(failed_pages),
        fetcher.stats.pages_fetched, fetcher.stats.cache_hits,
    )
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    sys.exit(run())


if __name__ == "__main__":
    main()
