"""Polite fetching: an honest user-agent, a timeout, a status check, a delay between real requests, and a disk cache.

Every network request goes through Fetcher.get(). During development the cache answers instead of the site, so the
site sees each page once, not once per restart.
"""
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

USER_AGENT = "FlyRankInternship-A9/1.0 (+https://github.com/azizulabedinazmi/FlyRank_A9-Scraper)"
TIMEOUT_S = 10          # give up on a request after this long; never wait forever
MIN_DELAY_S = 0.75      # at least this long between two real requests (requirement: >= 0.5 s)


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
    def __init__(self, cache_dir: Path, refresh: bool = False, delay: float = MIN_DELAY_S, timeout: float = TIMEOUT_S):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh          # --refresh: ignore the cache and ask the site again
        self.delay, self.timeout = delay, timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last_request = 0.0
        self.stats = {"network_requests": 0, "cache_hits": 0}

    def _paths(self, url: str) -> tuple[Path, Path]:
        html = self.cache_dir / cache_name(url)
        return html, html.with_suffix(html.suffix + ".meta.json")

    def _wait_politely(self) -> None:
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def get(self, url: str) -> Page:
        html_path, meta_path = self._paths(url)
        if not self.refresh and html_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.stats["cache_hits"] += 1
            html = html_path.read_text(encoding="utf-8")
            return Page(url, html, meta["status"], meta["fetched_at"], True, len(html.encode()))

        self._wait_politely()
        self.stats["network_requests"] += 1
        try:
            r = self.session.get(url, timeout=self.timeout)
        except requests.Timeout:
            raise FetchError(url, "timeout")
        except requests.RequestException as e:
            raise FetchError(url, f"network error: {e.__class__.__name__}")
        if r.status_code != 200:  # only 200 is "here is your page"; anything else is a failed fetch, not HTML to parse
            raise FetchError(url, f"HTTP {r.status_code}", r.status_code)

        html = r.content.decode("utf-8")  # the site is UTF-8; don't let a charset guess turn £ into Â£
        fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        html_path.write_text(html, encoding="utf-8", newline="")  # byte-for-byte what the site sent
        meta_path.write_text(json.dumps({"url": url, "status": r.status_code, "fetched_at": fetched_at,
                                         "bytes": len(r.content)}, indent=2), encoding="utf-8")
        return Page(url, html, r.status_code, fetched_at, False, len(r.content))
