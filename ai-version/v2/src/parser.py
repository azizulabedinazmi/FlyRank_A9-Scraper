"""HTML parsing for catalogue pages and book pages.

Every selector is scoped to a known container. If the container is missing the
page is treated as a parse error -- we never fall back to searching the whole
document. URLs are only ever taken from links on the page (resolved against
the page URL), never constructed or guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

RATING_WORDS = ("One", "Two", "Three", "Four", "Five")


class ParseError(Exception):
    pass


@dataclass
class CataloguePage:
    book_urls: list[str]
    next_url: str | None


def _text(node: Tag | None) -> str | None:
    if node is None:
        return None
    text = node.get_text(" ", strip=True)
    return text or None


def parse_catalogue(html: str, page_url: str) -> CataloguePage:
    soup = BeautifulSoup(html, "html.parser")
    # The listing area of a catalogue page.
    listing = soup.select_one("div.col-sm-8.col-md-9 section")
    if listing is None:
        raise ParseError("catalogue listing area (div.col-sm-8.col-md-9 section) not found")

    pods = listing.select("article.product_pod")
    if not pods:
        raise ParseError("no article.product_pod entries in listing area")

    book_urls: list[str] = []
    for pod in pods:
        link = pod.select_one("h3 > a[href]")
        if link is None:
            continue
        url = urljoin(page_url, link["href"])
        if url not in book_urls:
            book_urls.append(url)

    next_link = listing.select_one("ul.pager li.next > a[href]")
    next_url = urljoin(page_url, next_link["href"]) if next_link else None
    return CataloguePage(book_urls=book_urls, next_url=next_url)


def parse_book(html: str) -> dict:
    """Return raw extracted fields. Validation happens in the Pydantic model."""
    soup = BeautifulSoup(html, "html.parser")
    product_page = soup.select_one("article.product_page")
    if product_page is None:
        raise ParseError("product area article.product_page not found")
    product_main = product_page.select_one("div.product_main")
    if product_main is None:
        raise ParseError("product area div.product_main not found")

    rating_text = None
    rating = product_main.select_one("p.star-rating")
    if rating is not None:
        for cls in rating.get("class", []):
            if cls in RATING_WORDS:
                rating_text = cls
                break

    # Description: the <p> right after #product_description, inside the product area.
    description = _text(product_page.select_one("#product_description + p"))

    return {
        "title": _text(product_main.select_one("h1")),
        "price_text": _text(product_main.select_one("p.price_color")),
        "availability_text": _text(product_main.select_one("p.availability")),
        "rating_text": rating_text,
        "description": description,
    }
