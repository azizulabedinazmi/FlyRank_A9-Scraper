"""HTML parsing for catalogue pages and book pages."""
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

RATINGS = {"One", "Two", "Three", "Four", "Five"}


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    return " ".join(text.split())


def parse_catalogue(html: str, page_url: str) -> tuple[list[str], str | None]:
    """Return (absolute book URLs on this page, absolute next-page URL or None)."""
    soup = BeautifulSoup(html, "html.parser")
    book_urls: list[str] = []
    for a in soup.select("article.product_pod h3 a[href]"):
        url = urljoin(page_url, a["href"])
        if url not in book_urls:
            book_urls.append(url)
    next_a = soup.select_one("li.next a[href]")
    next_url = urljoin(page_url, next_a["href"]) if next_a else None
    return book_urls, next_url


def parse_book(html: str) -> dict:
    """Extract raw fields from a book page. Missing fields come back as None;
    validation (not parsing) decides whether the record is acceptable."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("div.product_main") or soup

    title_el = main.select_one("h1")
    price_el = main.select_one("p.price_color")
    avail_el = main.select_one("p.availability")

    rating = None
    rating_el = main.select_one("p.star-rating")
    if rating_el:
        rating = next((c for c in rating_el.get("class", []) if c in RATINGS), None)

    description = None
    desc_header = soup.select_one("#product_description")
    if desc_header:
        p = desc_header.find_next_sibling("p")
        if p:
            description = _clean(p.get_text()) or None

    return {
        "title": _clean(title_el.get_text()) if title_el else None,
        "price_text": _clean(price_el.get_text()) if price_el else None,
        "availability_text": _clean(avail_el.get_text()) if avail_el else None,
        "rating_text": rating,
        "description": description,
    }
