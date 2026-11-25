"""Pydantic model every record must pass before it is stored."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BASE_URL = "https://books.toscrape.com/"
PRICE_RE = re.compile(r"^£\s*(\d+(?:\.\d{1,2})?)$")


def parse_price(price_text: str) -> float:
    """'£51.77' -> 51.77. Raises ValueError if the text isn't a GBP price."""
    match = PRICE_RE.match(price_text.strip())
    if not match:
        raise ValueError(f"unrecognised price format: {price_text!r}")
    return float(match.group(1))


class Book(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1)
    product_url: str
    price_text: str
    price_gbp: float = Field(ge=0)
    availability_text: str = Field(min_length=1)
    rating_text: Literal["One", "Two", "Three", "Four", "Five"]
    description: Optional[str] = None
    source_page: str
    fetched_at: datetime

    @field_validator("product_url", "source_page")
    @classmethod
    def _absolute_site_url(cls, v: str) -> str:
        if not v.startswith(BASE_URL):
            raise ValueError(f"must be an absolute URL under {BASE_URL}")
        return v

    @field_validator("description")
    @classmethod
    def _empty_description_is_null(cls, v: Optional[str]) -> Optional[str]:
        return v or None

    @model_validator(mode="after")
    def _price_matches_text(self) -> "Book":
        if abs(parse_price(self.price_text) - self.price_gbp) > 1e-9:
            raise ValueError("price_gbp does not match price_text")
        return self
