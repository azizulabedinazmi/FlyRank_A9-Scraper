"""The polite scraper: Books to Scrape, first 3 catalogue pages, 60 books -> clean, validated JSON.

Run from the repo root:  python src/main.py
"""
import sys
from pathlib import Path

from fetch import Fetcher, FetchError
from parse import parse_book, parse_catalogue
from store import store, validate

ROOT = Path(__file__).resolve().parent.parent
START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3


def log(event: str, url: str, **fields) -> None:
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    print(f"{event:<10} {url} {extra}".rstrip(), flush=True)


def discover(fetcher: Fetcher) -> tuple[int, list[tuple[str, str]]]:
    """Walk the catalogue by following the site's own "next" link, stopping after MAX_CATALOGUE_PAGES.

    Returns (pages walked, [(book_url, catalogue_page_it_was_found_on), ...]) in discovery order.
    """
    url, pages, found = START_URL, 0, []
    while url and pages < MAX_CATALOGUE_PAGES:
        page = fetcher.get(url)
        log("CACHE HIT" if page.from_cache else "FETCH", page.url, status=page.status, bytes=page.size)
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
    fetcher = Fetcher(ROOT / "cache", refresh="--refresh" in sys.argv)
    try:
        pages, found = discover(fetcher)
    except FetchError as e:
        log("FAILED", e.url, reason=e.reason)
        return 1
    books = unique(found)
    print(f"catalogue_pages={pages}, discovered={len(found)}, unique_urls={len(books)}")

    raw = []
    for url, source_page in books:
        page = fetcher.get(url)
        log("CACHE HIT" if page.from_cache else "FETCH", page.url, status=page.status, bytes=page.size)
        raw.append(parse_book(page.html, url, source_page, page.fetched_at))
    print(f"detail_pages={len(raw)}, without_description={sum(r['description'] is None for r in raw)}")

    good, bad = validate(raw)
    store(ROOT / "output", good, bad)
    print(f"valid_records={len(good)}, invalid_records={len(bad)} -> output/books.json, output/errors.json")
    print(f"network_requests={fetcher.stats['network_requests']}, cache_hits={fetcher.stats['cache_hits']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
