"""Polite scraper for https://books.toscrape.com/ (practice sandbox).

Usage:  python src/main.py
"""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from fetcher import FetchError, PoliteFetcher
from models import Book, parse_price
from parser import parse_book, parse_catalogue

START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"

log = logging.getLogger("scraper")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def build_record(raw: dict, product_url: str, source_page: str, fetched_at: str) -> dict:
    record = dict(raw)
    record.update(product_url=product_url, source_page=source_page, fetched_at=fetched_at)
    try:
        record["price_gbp"] = parse_price(raw["price_text"]) if raw.get("price_text") else None
    except ValueError:
        record["price_gbp"] = None  # let Pydantic report it as invalid
    return record


def run() -> int:
    started = time.monotonic()
    start_time = datetime.now(timezone.utc).isoformat()
    fetcher = PoliteFetcher(CACHE_DIR)

    failed_pages: list[dict] = []
    errors: list[dict] = []
    books: dict[str, dict] = {}  # product_url -> record; guarantees no duplicates

    # 1) Catalogue pages: start at page 1, follow "next", stop after 3.
    to_visit: list[tuple[str, str]] = []  # (book_url, source_page)
    seen_book_urls: set[str] = set()
    page_url: str | None = START_URL
    catalogue_count = 0
    while page_url and catalogue_count < MAX_CATALOGUE_PAGES:
        catalogue_count += 1
        try:
            page = fetcher.get(page_url)
            book_urls, next_url = parse_catalogue(page.html, page_url)
        except FetchError as exc:
            log.error("Skipping catalogue page %s: %s", page_url, exc)
            failed_pages.append({"url": page_url, "reason": str(exc)})
            # Without the page we can't read its "next" link; guess the next one.
            next_url = START_URL.replace("page-1", f"page-{catalogue_count + 1}")
            book_urls = []
        except Exception as exc:  # parsing failure must not crash the run
            log.exception("Could not parse catalogue page %s", page_url)
            failed_pages.append({"url": page_url, "reason": f"parse error: {exc}"})
            next_url = START_URL.replace("page-1", f"page-{catalogue_count + 1}")
            book_urls = []

        for url in book_urls:
            if url not in seen_book_urls:
                seen_book_urls.add(url)
                to_visit.append((url, page_url))
        page_url = next_url

    log.info("Found %d book links on %d catalogue pages", len(to_visit), catalogue_count)

    # 2) Book pages.
    for book_url, source_page in to_visit:
        try:
            page = fetcher.get(book_url)
            raw = parse_book(page.html)
        except FetchError as exc:
            log.error("Skipping book page %s: %s", book_url, exc)
            failed_pages.append({"url": book_url, "reason": str(exc)})
            continue
        except Exception as exc:
            log.exception("Could not parse book page %s", book_url)
            failed_pages.append({"url": book_url, "reason": f"parse error: {exc}"})
            continue

        record = build_record(raw, book_url, source_page, page.fetched_at)
        try:
            book = Book.model_validate(record)
        except ValidationError as exc:
            reason = "; ".join(
                f"{'.'.join(str(p) for p in err['loc']) or 'record'}: {err['msg']}"
                for err in exc.errors()
            )
            log.warning("Invalid record %s: %s", book_url, reason)
            errors.append({"product_url": book_url, "reason": reason, "record": record})
            continue
        books[book.product_url] = book.model_dump(mode="json")

    # 3) Outputs (overwritten every run, so re-runs never duplicate).
    write_json(OUTPUT_DIR / "books.json", list(books.values()))
    write_json(OUTPUT_DIR / "errors.json", errors)
    report = {
        "start_time": start_time,
        "duration_seconds": round(time.monotonic() - started, 3),
        "pages_fetched": fetcher.pages_fetched,
        "cache_hits": fetcher.cache_hits,
        "valid_records": len(books),
        "invalid_records": len(errors),
        "failed_pages": failed_pages,
    }
    write_json(OUTPUT_DIR / "run-report.json", report)

    log.info(
        "Done: %d valid, %d invalid, %d failed pages, %d fetched, %d cache hits",
        len(books), len(errors), len(failed_pages), fetcher.pages_fetched, fetcher.cache_hits,
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
