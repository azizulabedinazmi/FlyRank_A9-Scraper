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
