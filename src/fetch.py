"""Polite fetching: an honest user-agent, a timeout, a status check, a delay between real requests, and a disk cache.

Every network request goes through Fetcher.get(). During development the cache answers instead of the site, so the
site sees each page once, not once per restart.
"""
import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

USER_AGENT = "FlyRankInternship-A9/1.0 (+https://github.com/azizulabedinazmi/FlyRank_A9-Scraper)"
TIMEOUT_S = 10          # give up on a request after this long; never wait forever
MIN_DELAY_S = 0.75      # at least this long between two real requests (requirement: >= 0.5 s)
MAX_ATTEMPTS = 3        # first try + up to 2 retries, only for timeouts / 5xx / 429
BACKOFF_BASE_S = 1.0    # 1 s, 2 s, ... (+ jitter)
MAX_RETRY_AFTER_S = 30  # obey Retry-After, but never park the run longer than this


@dataclass
class Page:
    url: str
    html: str
    status: int
    fetched_at: str     # when the site actually sent it (kept from the original fetch on a cache hit)
    from_cache: bool
    size: int           # bytes


class FetchError(Exception):
    def __init__(self, url: str, reason: str, status: int | None = None):
        super().__init__(f"{reason} ({url})")
        self.url, self.reason, self.status = url, reason, status


def cache_name(url: str) -> str:
    """https://books.toscrape.com/catalogue/page-1.html -> catalogue-page-1.html"""
    path = urlparse(url).path.strip("/") or "index.html"
    return path.replace("/", "-")


class Fetcher:
    def __init__(self, cache_dir: Path, refresh: bool = False, delay: float = MIN_DELAY_S, timeout: float = TIMEOUT_S,
                 log_path: Path | None = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh          # --refresh: ignore the cache and ask the site again
        self.delay, self.timeout = delay, timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last_request = 0.0
        self.log_path = Path(log_path) if log_path else None
        self.sleep = time.sleep  # swappable in tests, so retry tests don't really wait
        self.stats = {"network_requests": 0, "pages_fetched": 0, "cache_hits": 0, "retries": 0}

    def _paths(self, url: str) -> tuple[Path, Path]:
        html = self.cache_dir / cache_name(url)
        return html, html.with_suffix(html.suffix + ".meta.json")

    def _wait_politely(self) -> None:
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _log(self, **fields) -> None:
        """Structured log: one JSON object per network attempt (url, status, attempt, timing...)."""
        if self.log_path:
            fields = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"), **fields}
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(fields) + "\n")

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        """How long to wait before the next attempt.

        If the server said Retry-After, obey it (capped, so one bad header can't park the run for an hour).
        Otherwise exponential backoff: 1 s, 2 s, 4 s ... plus up to 0.5 s of random jitter, so many clients
        that failed together don't all come back at the same instant.
        """
        if retry_after:
            try:
                return min(float(retry_after), MAX_RETRY_AFTER_S)
            except ValueError:
                try:  # Retry-After may also be an HTTP date
                    when = parsedate_to_datetime(retry_after)
                    return min(max((when - datetime.now(timezone.utc)).total_seconds(), 0), MAX_RETRY_AFTER_S)
                except (TypeError, ValueError):
                    pass
        return BACKOFF_BASE_S * 2 ** (attempt - 1) + random.uniform(0, 0.5)

    def _request(self, url: str) -> requests.Response:
        """Retry rules.
        - 200: done.
        - Timeout, connection error, 5xx, 429: maybe temporary -> wait (Retry-After or backoff) and retry,
          up to MAX_ATTEMPTS in total.
        - Any other 4xx: an answer, not an accident. 404 won't create the page and 403 means "no";
          asking again would only make us a pest. Never retried.
        """
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._wait_politely()
            self.stats["network_requests"] += 1
            t = time.monotonic()
            retry_after = None
            try:
                r = self.session.get(url, timeout=self.timeout)
            except requests.Timeout:
                err, status = FetchError(url, "timeout"), None
            except requests.RequestException as e:
                err, status = FetchError(url, f"network error: {e.__class__.__name__}"), None
            else:
                status = r.status_code
                if status == 200:  # only 200 is "here is your page"
                    self.stats["pages_fetched"] += 1
                    self._log(url=url, attempt=attempt, status=200, bytes=len(r.content),
                              ms=round((time.monotonic() - t) * 1000), outcome="ok")
                    return r
                err = FetchError(url, f"HTTP {status}", status)
                retry_after = r.headers.get("Retry-After")
            retryable = status is None or status >= 500 or status == 429
            last = attempt == MAX_ATTEMPTS or not retryable
            wait = None if last else round(self._backoff(attempt, retry_after), 2)
            self._log(url=url, attempt=attempt, status=status, error=err.reason, retry_after=retry_after,
                      ms=round((time.monotonic() - t) * 1000), outcome="give up" if last else f"retry in {wait}s")
            if last:
                raise err
            self.stats["retries"] += 1
            self.sleep(wait)
        raise err  # unreachable; keeps type checkers happy

    def get(self, url: str) -> Page:
        html_path, meta_path = self._paths(url)
        if not self.refresh and html_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.stats["cache_hits"] += 1
            html = html_path.read_text(encoding="utf-8")
            return Page(url, html, meta["status"], meta["fetched_at"], True, len(html.encode()))

        r = self._request(url)

        html = r.content.decode("utf-8")  # the site is UTF-8; don't let a charset guess turn £ into Â£
        fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        html_path.write_text(html, encoding="utf-8", newline="")  # byte-for-byte what the site sent
        meta_path.write_text(json.dumps({"url": url, "status": r.status_code, "fetched_at": fetched_at,
                                         "bytes": len(r.content)}, indent=2), encoding="utf-8")
        return Page(url, html, r.status_code, fetched_at, False, len(r.content))
