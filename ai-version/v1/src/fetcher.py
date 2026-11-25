"""Polite HTTP fetching with an on-disk cache.

- Identifying User-Agent, request timeout.
- At least MIN_DELAY seconds between real network requests.
- Only status 200 is accepted.
- One retry on timeouts / connection errors / 5xx; never on 4xx (404, 403, ...).
- Every successful page is cached in cache/ so re-runs don't hit the site.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)

USER_AGENT = (
    "PoliteBooksScraper/1.0 (educational scraper for books.toscrape.com; "
    "python-requests)"
)
TIMEOUT = 10  # seconds
MIN_DELAY = 0.5  # seconds between network requests
MAX_ATTEMPTS = 2  # first try + one retry


class FetchError(Exception):
    """Raised when a page cannot be fetched (after any allowed retry)."""


@dataclass
class Page:
    url: str
    html: str
    fetched_at: str  # ISO 8601, UTC; when the page was actually downloaded
    from_cache: bool


class PoliteFetcher:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._last_request = 0.0
        self.pages_fetched = 0  # real network fetches that returned 200
        self.cache_hits = 0

    # ---------- cache ----------
    def _cache_path(self, url: str) -> Path:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, url: str) -> Page | None:
        path = self._cache_path(url)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Page(url=url, html=data["html"], fetched_at=data["fetched_at"], from_cache=True)
        except (OSError, ValueError, KeyError) as exc:
            log.warning("Ignoring corrupt cache file %s: %s", path.name, exc)
            return None

    def _write_cache(self, page: Page) -> None:
        payload = {"url": page.url, "fetched_at": page.fetched_at, "html": page.html}
        tmp = self._cache_path(page.url).with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._cache_path(page.url))

    # ---------- network ----------
    def _wait_politely(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < MIN_DELAY:
            time.sleep(MIN_DELAY - elapsed)
        self._last_request = time.monotonic()

    def _download(self, url: str) -> Page:
        last_error = "unknown error"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._wait_politely()
            try:
                resp = self.session.get(url, timeout=TIMEOUT)
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                log.warning("Attempt %d/%d for %s failed: %s", attempt, MAX_ATTEMPTS, url, last_error)
                continue
            except requests.RequestException as exc:
                raise FetchError(f"{type(exc).__name__}: {exc}") from exc

            if resp.status_code == 200:
                # The site serves UTF-8 without a charset header; decode explicitly
                # so "£" doesn't become "Â£".
                html = resp.content.decode("utf-8", errors="replace")
                return Page(
                    url=url,
                    html=html,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                    from_cache=False,
                )
            if resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}"
                log.warning("Attempt %d/%d for %s failed: %s", attempt, MAX_ATTEMPTS, url, last_error)
                continue
            # 4xx (404, 403, ...) and any other non-200: never retry.
            raise FetchError(f"HTTP {resp.status_code}")
        raise FetchError(f"gave up after {MAX_ATTEMPTS} attempts ({last_error})")

    def get(self, url: str) -> Page:
        cached = self._read_cache(url)
        if cached is not None:
            self.cache_hits += 1
            log.debug("Cache hit: %s", url)
            return cached
        log.info("Fetching %s", url)
        page = self._download(url)
        self.pages_fetched += 1
        self._write_cache(page)
        return page
