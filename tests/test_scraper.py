"""Offline tests: fixtures instead of the network. Run with:  python -m pytest -q"""
from pathlib import Path

import pytest
import requests

import extras
from fetch import Fetcher, FetchError
from main import unique
from parse import ParseError, parse_book, parse_catalogue
from schema import normalize
from store import validate

FIX = Path(__file__).parent / "fixtures"
PAGE2 = "https://books.toscrape.com/catalogue/page-2.html"
PROVENANCE = {"source_page": "https://books.toscrape.com/catalogue/page-1.html", "fetched_at": "2026-11-25T10:00:00Z"}


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def raw_record(**over) -> dict:
    base = {"title": "T", "product_url": "https://books.toscrape.com/catalogue/t_1/index.html", "price_text": "£51.77",
            "availability_text": "In stock (22 available)", "rating_text": "Three", "description": None, **PROVENANCE}
    return {**base, **over}


# ---------------------------------------------------------------- normalization
@pytest.mark.parametrize("text,expected", [("£51.77", 51.77), ("£0.99", 0.99), ("£ 7", 7.0), ("£100.5", 100.5)])
def test_price_normalization(text, expected):
    assert normalize(raw_record(price_text=text))["price_gbp"] == expected


@pytest.mark.parametrize("text", ["51.77", "$51.77", "£51.777", "Free", "", None, "£-3.00", "£1,000.00"])
def test_bad_prices_are_rejected_not_guessed(text):
    good, bad = validate([raw_record(price_text=text)])
    assert good == [] and len(bad) == 1 and "price_text" in bad[0]["reason"]


def test_availability_and_rating():
    rec = normalize(raw_record(availability_text="In stock (22 available)", rating_text="Four"))
    assert (rec["in_stock"], rec["stock_count"], rec["rating"]) == (True, 22, 4)
    rec = normalize(raw_record(availability_text="Out of stock"))
    assert (rec["in_stock"], rec["stock_count"]) == (False, None)


# ---------------------------------------------------------------- URLs
def test_relative_links_become_absolute():
    books, nxt = parse_catalogue(fixture("catalogue.html"), PAGE2)
    assert books == ["https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
                     "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html"]  # ../ resolved too
    assert nxt == "https://books.toscrape.com/catalogue/page-3.html"
    assert all(u.startswith("https://") for u in books)


def test_last_page_has_no_next():
    html = fixture("catalogue.html").replace('<li class="next"><a href="page-3.html">next</a></li>', "")
    assert parse_catalogue(html, PAGE2)[1] is None


# ---------------------------------------------------------------- extraction
def test_missing_description_is_null_and_all_eight_keys_present():
    rec = parse_book(fixture("book_no_description.html"), "https://books.toscrape.com/catalogue/q_1/index.html", **PROVENANCE)
    assert set(rec) == {"title", "product_url", "price_text", "availability_text", "rating_text", "description",
                        "source_page", "fetched_at"}
    assert rec["description"] is None  # never invented


def test_price_comes_from_the_product_area_not_the_first_match():
    rec = parse_book(fixture("book_no_description.html"), "https://books.toscrape.com/catalogue/q_1/index.html", **PROVENANCE)
    assert rec["price_text"] == "£12.50"  # not the £999.99 decoy that appears first in the document


def test_extra_whitespace_is_collapsed():
    rec = parse_book(fixture("book_messy_whitespace.html"), "https://books.toscrape.com/catalogue/s_2/index.html", **PROVENANCE)
    assert rec["title"] == "A Spaced Out Title"
    assert rec["price_text"] == "£7.05"
    assert rec["availability_text"] == "Out of stock"
    assert rec["rating_text"] == "Five"
    assert rec["description"] == "First line. Second line. Tabbed."
    assert validate([rec])[0][0].price_gbp == 7.05


def test_malformed_page_raises_parse_error():
    with pytest.raises(ParseError):
        parse_book(fixture("malformed.html"), "https://books.toscrape.com/catalogue/x/index.html", **PROVENANCE)


# ---------------------------------------------------------------- duplicates
def test_duplicate_urls_are_dropped_in_discovery_and_storage():
    a, b = "https://books.toscrape.com/catalogue/a_1/index.html", "https://books.toscrape.com/catalogue/b_2/index.html"
    assert unique([(a, "p1"), (b, "p1"), (a, "p2")]) == [(a, "p1"), (b, "p1")]
    good, bad = validate([raw_record(product_url=a), raw_record(product_url=b), raw_record(product_url=a, title="again")])
    assert [g.product_url for g in good] == [a, b] and good[0].title == "T" and bad == []


def test_off_site_or_http_urls_fail_validation():
    good, bad = validate([raw_record(product_url="http://books.toscrape.com/catalogue/t_1/index.html")])
    assert good == [] and "product_url" in bad[0]["reason"]


# ---------------------------------------------------------------- retry rules (fake session, no network, no waiting)
class FakeResponse:
    def __init__(self, status, headers=None, body=b"<html>ok</html>"):
        self.status_code, self.headers, self.content = status, headers or {}, body


class FakeSession:
    def __init__(self, *outcomes):
        self.outcomes, self.calls, self.headers = list(outcomes), 0, {}

    def get(self, url, timeout):
        self.calls += 1
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def fetcher_with(tmp_path, *outcomes) -> tuple[Fetcher, list[float]]:
    f = Fetcher(tmp_path, delay=0, log_path=tmp_path / "log.jsonl")
    f.session = FakeSession(*outcomes)
    waits: list[float] = []
    f.sleep = waits.append
    return f, waits


@pytest.mark.parametrize("status", [404, 403, 410])
def test_4xx_is_never_retried(tmp_path, status):
    f, waits = fetcher_with(tmp_path, FakeResponse(status))
    with pytest.raises(FetchError) as e:
        f.get("https://books.toscrape.com/x")
    assert f.session.calls == 1 and waits == [] and e.value.status == status


def test_5xx_is_retried_with_backoff_then_succeeds(tmp_path):
    f, waits = fetcher_with(tmp_path, FakeResponse(503), FakeResponse(200))
    page = f.get("https://books.toscrape.com/y")
    assert page.status == 200 and f.session.calls == 2 and f.stats["retries"] == 1
    assert 1.0 <= waits[0] <= 1.5  # 1 s base + up to 0.5 s jitter


def test_retry_after_header_is_obeyed(tmp_path):
    f, waits = fetcher_with(tmp_path, FakeResponse(429, {"Retry-After": "7"}), FakeResponse(200))
    f.get("https://books.toscrape.com/z")
    assert waits == [7.0]


def test_timeouts_give_up_after_three_attempts(tmp_path):
    f, waits = fetcher_with(tmp_path, *[requests.Timeout()] * 3)
    with pytest.raises(FetchError, match="timeout"):
        f.get("https://books.toscrape.com/slow")
    assert f.session.calls == 3 and len(waits) == 2 and waits[1] > waits[0]  # exponential: ~1 s, then ~2 s
    log = (tmp_path / "log.jsonl").read_text().splitlines()
    assert len(log) == 3 and '"outcome": "give up"' in log[-1]


def test_second_get_is_a_cache_hit(tmp_path):
    f, _ = fetcher_with(tmp_path, FakeResponse(200, body="<p>£1</p>".encode()))
    first, second = f.get("https://books.toscrape.com/c"), f.get("https://books.toscrape.com/c")
    assert (first.from_cache, second.from_cache, f.session.calls) == (False, True, 1)
    assert second.fetched_at == first.fetched_at and second.html == "<p>£1</p>"  # provenance survives the cache


# ---------------------------------------------------------------- change detection
def test_changes_since_last_run():
    a = {"product_url": "a", "title": "A", "price_gbp": 1.0, "fetched_at": "t1"}
    b = {"product_url": "b", "title": "B", "price_gbp": 2.0, "fetched_at": "t1"}
    c = {"product_url": "c", "title": "C", "price_gbp": 3.0, "fetched_at": "t1"}
    now = [dict(a, fetched_at="t2"), dict(b, price_gbp=2.5), {"product_url": "d", "title": "D", "price_gbp": 4.0}]
    diff = extras.changes([a, b, c], now)
    assert (diff["new"], diff["changed"], diff["unchanged"], diff["gone"]) == (["d"], ["b"], 1, ["c"])
