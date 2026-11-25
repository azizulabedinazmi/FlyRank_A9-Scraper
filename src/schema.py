"""Normalization (raw strings -> typed values) and the schema every stored record must pass."""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
SITE = "https://books.toscrape.com/"


class Book(BaseModel):
    """A finished record. Raw text and clean value sit side by side so every number can be traced to the page."""
    model_config = ConfigDict(extra="forbid", strict=True)

    # identity
    product_url: str = Field(description="Canonical URL: the record's identity")
    title: str = Field(min_length=1)
    # price
    price_text: str
    price_gbp: float = Field(gt=0, lt=10_000)
    # availability
    availability_text: str
    in_stock: bool
    stock_count: int | None = Field(default=None, ge=0)
    # rating
    rating_text: Literal["One", "Two", "Three", "Four", "Five"]
    rating: int = Field(ge=1, le=5)
    # optional
    description: str | None = None
    # provenance
    source_page: str
    fetched_at: datetime

    @field_validator("product_url", "source_page")
    @classmethod
    def on_the_target_site(cls, v: str) -> str:
        if not v.startswith(SITE):
            raise ValueError(f"must be an absolute https URL on {SITE}")
        return v

    @field_validator("fetched_at", mode="before")
    @classmethod
    def parse_iso(cls, v):
        return datetime.fromisoformat(v.replace("Z", "+00:00")) if isinstance(v, str) else v


PRICE = re.compile(r"^£\s*(\d{1,6}(?:\.\d{1,2})?)$")
STOCK = re.compile(r"\((\d+) available\)")


def normalize(raw: dict) -> dict:
    """Raw record -> the fields Book expects. Raises ValueError with a readable reason when a value makes no sense."""
    price_text = raw.get("price_text") or ""
    m = PRICE.match(price_text)
    if not m:
        raise ValueError(f"price_text {price_text!r} is not a £ amount")
    availability = raw.get("availability_text") or ""
    stock = STOCK.search(availability)
    rating_text = raw.get("rating_text")
    return {
        "product_url": raw["product_url"],
        "title": raw.get("title") or "",
        "price_text": price_text,
        "price_gbp": round(float(m.group(1)), 2),
        "availability_text": availability,
        "in_stock": availability.lower().startswith("in stock"),
        "stock_count": int(stock.group(1)) if stock else None,
        "rating_text": rating_text,
        "rating": RATINGS.get(rating_text, 0),
        "description": raw.get("description"),
        "source_page": raw["source_page"],
        "fetched_at": raw["fetched_at"],
    }
