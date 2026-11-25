"""Extraction: HTML in, raw strings out. No cleaning here; that's normalize.py's job."""
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def parse_catalogue(html: str, page_url: str) -> tuple[list[str], str | None]:
    """Return (absolute book URLs on this page, absolute URL of the next page or None).

    Each book card links to its page twice (cover image and title); the title link is the one we take.
    Links are relative ("a-light-in-the-attic_1000/index.html"), so urljoin resolves them against the page they
    appeared on, never by gluing strings together.
    """
    soup = BeautifulSoup(html, "html.parser")
    books = [urljoin(page_url, a["href"]) for a in soup.select("article.product_pod h3 a[href]")]
    nxt = soup.select_one("ul.pager li.next a[href]")
    return books, (urljoin(page_url, nxt["href"]) if nxt else None)


RATING_WORDS = {"One", "Two", "Three", "Four", "Five"}


def _text(node) -> str | None:
    """Visible text with runs of whitespace collapsed, or None if the node isn't there or is empty."""
    if node is None:
        return None
    text = " ".join(node.get_text(" ", strip=True).split())
    return text or None


class ParseError(Exception):
    """The page arrived but isn't a book page we understand (layout changed, wrong page...)."""


def parse_book(html: str, product_url: str, source_page: str, fetched_at: str) -> dict:
    """Raw record: exactly eight keys, values as they appear on the page (strings or None).

    Every selector is scoped to the product area (div.product_main / article.product_page), never the whole
    document: the "Product Information" table below repeats the price three times, and "the first thing that looks
    like a price" is exactly the bug this avoids.
    """
    soup = BeautifulSoup(html, "html.parser")
    product = soup.select_one("article.product_page")
    main = product.select_one("div.product_main") if product else None
    if main is None:
        raise ParseError("no div.product_main on the page")

    rating_el = main.select_one("p.star-rating")
    rating = next((c for c in (rating_el.get("class", []) if rating_el else []) if c in RATING_WORDS), None)
    # The description is the <p> straight after the "Product Description" header. Some books have no header at all.
    desc_header = product.select_one("#product_description")
    desc_p = desc_header.find_next_sibling("p") if desc_header else None

    return {
        "title": _text(main.select_one("h1")),
        "product_url": product_url,
        "price_text": _text(main.select_one("p.price_color")),
        "availability_text": _text(main.select_one("p.availability")),
        "rating_text": rating,
        "description": _text(desc_p),
        "source_page": source_page,
        "fetched_at": fetched_at,
    }
