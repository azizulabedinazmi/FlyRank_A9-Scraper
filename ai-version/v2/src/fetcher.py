"""Polite HTTP fetching with an on-disk cache.

Rules enforced here:
- identifying User-Agent, timeout on every request
- at least REQUEST_DELAY seconds between any two network requests
- only HTTP 200 is accepted (redirects are not followed, so a 3xx is a failure)
- one retry on timeout / 5xx after RETRY_WAIT seconds; never on 4xx (404/403)
- every successful page is cached; a cache hit makes no network request and
  keeps the original download time as fetched_at
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

import config

log = logging.getLogger(__name__)


class FetchError(Exception):
    """A page could not be fetched. `kind` is a short machine-readable tag."""

    def __init__(self, url: str, kind: str, message: str):
        super().__init__(f"{kind}: {message}")
        self.url = url
        self.kind = kind
        self.message = message


@dataclass
class Page:
    url: str
    html: str
    fetched_at: str  # ISO-8601 UTC timestamp of the original download
    from_cache: bool


@dataclass
class FetchStats:
    pages_fetched: int = 0  # pages downloaded from the network with status 200
    cache_hits: int = 0
    http_requests: int = 0  # every request sent, including retries


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class PoliteFetcher:
    def __init__(self, cache_dir: Path = config.CACHE_DIR):
        assert config.REQUEST_DELAY >= config.MIN_DELAY_FLOOR
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            }
        )
        self.stats = FetchStats()
        self._last_request_end: float | None = None

    # ------------------------------------------------------------------ cache
    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.html", self.cache_dir / f"{key}.json"

    def _read_cache(self, url: str) -> Page | None:
        html_path, meta_path = self._cache_paths(url)
        if not (html_path.exists() and meta_path.exists()):
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("url") != url or meta.get("status") != 200:
                return None
            html = html_path.read_bytes().decode("utf-8", errors="replace")
            return Page(url=url, html=html, fetched_at=meta["fetched_at"], from_cache=True)
        except (OSError, ValueError, KeyError) as exc:
            log.warning("Ignoring unreadable cache entry for %s (%s)", url, exc)
            return None

    def _write_cache(self, url: str, body: bytes, fetched_at: str) -> None:
        html_path, meta_path = self._cache_paths(url)
        _atomic_write_bytes(html_path, body)
        meta = {"url": url, "status": 200, "fetched_at": fetched_at}
        _atomic_write_bytes(meta_path, json.dumps(meta, indent=2).encode("utf-8"))

    # ---------------------------------------------------------------- network
    def _wait_politely(self, minimum: float) -> None:
        """Sleep so that at least `minimum` seconds pass since the last request ended."""
        if self._last_request_end is None:
            return
        remaining = minimum - (time.monotonic() - self._last_request_end)
        if remaining > 0:
            time.sleep(remaining)

    def _request_once(self, url: str, wait: float) -> requests.Response:
        self._wait_politely(wait)
        self.stats.http_requests += 1
        try:
            return self.session.get(
                url, timeout=config.REQUEST_TIMEOUT, allow_redirects=False
            )
        finally:
            self._last_request_end = time.monotonic()

    def fetch(self, url: str) -> Page:
        host = urlparse(url).hostname
        if host != config.ALLOWED_HOST:
            raise FetchError(url, "out_of_scope", f"host {host!r} is not {config.ALLOWED_HOST}")

        cached = self._read_cache(url)
        if cached is not None:
            self.stats.cache_hits += 1
            log.info("cache hit  %s", url)
            return cached

        attempts = 1 + config.MAX_RETRIES
        last_error: FetchError | None = None
        for attempt in range(1, attempts + 1):
            # Normal polite gap for the first try; longer back-off for the retry.
            wait = config.REQUEST_DELAY if attempt == 1 else max(config.RETRY_WAIT, config.REQUEST_DELAY)
            if attempt > 1:
                log.info("retrying  %s in ~%.1fs (attempt %d/%d)", url, wait, attempt, attempts)
            try:
                resp = self._request_once(url, wait)
            except requests.Timeout as exc:
                last_error = FetchError(url, "timeout", str(exc))
                continue  # retryable
            except requests.RequestException as exc:
                raise FetchError(url, "network_error", str(exc)) from exc

            if resp.status_code == 200:
                fetched_at = datetime.now(timezone.utc).isoformat()
                body = resp.content
                self._write_cache(url, body, fetched_at)
                self.stats.pages_fetched += 1
                log.info("fetched    %s", url)
                return Page(
                    url=url,
                    html=body.decode("utf-8", errors="replace"),
                    fetched_at=fetched_at,
                    from_cache=False,
                )
            if 500 <= resp.status_code < 600:
                last_error = FetchError(url, "http_error", f"status {resp.status_code}")
                continue  # retryable
            # 4xx (incl. 403/404), 3xx and anything else: no retry.
            raise FetchError(url, "http_error", f"status {resp.status_code}")

        assert last_error is not None
        raise last_error
