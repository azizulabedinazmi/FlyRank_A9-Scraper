"""The polite scraper: Books to Scrape, first 3 catalogue pages, 60 books -> clean, validated JSON.

Run from the repo root:  python src/main.py
"""
import sys
from pathlib import Path

from fetch import Fetcher, FetchError

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://books.toscrape.com/"
START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3


def log(event: str, url: str, **fields) -> None:
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    print(f"{event:<10} {url} {extra}".rstrip(), flush=True)


def main() -> int:
    fetcher = Fetcher(ROOT / "cache", refresh="--refresh" in sys.argv)
    try:
        page = fetcher.get(START_URL)
    except FetchError as e:
        log("FAILED", e.url, reason=e.reason)
        return 1
    log("CACHE HIT" if page.from_cache else "FETCH", page.url, status=page.status, bytes=page.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
