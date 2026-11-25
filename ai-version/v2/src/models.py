"""Pydantic model that every book record must pass before it is stored."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import config

PRICE_RE = re.compile(r"^£\s*(\d+(?:\.\d{1,2})?)$")


def normalize_price(price_text: str | None) -> float | None:
    """'£51.77' -> 51.77. Returns None if the text is not a GBP price."""
    if not price_text:
        return None
    match = PRICE_RE.match(price_text.strip())
    if not match:
        return None
    try:
        return float(Decimal(match.group(1)))
    except InvalidOperation:
        return None


def _check_site_url(value: str, field: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or parsed.hostname != config.ALLOWED_HOST:
        raise ValueError(f"{field} must be an absolute URL on {config.ALLOWED_HOST}")
    return value


class Book(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1)
    product_url: str
    price_text: str = Field(pattern=r"^£\d+\.\d{2}$")
    price_gbp: float = Field(gt=0)
    availability_text: str = Field(min_length=1)
    rating_text: Literal["One", "Two", "Three", "Four", "Five"]
    description: Optional[str] = None
    source_page: str
    fetched_at: datetime

    @field_validator("product_url")
    @classmethod
    def _product_url(cls, v: str) -> str:
        return _check_site_url(v, "product_url")

    @field_validator("source_page")
    @classmethod
    def _source_page(cls, v: str) -> str:
        return _check_site_url(v, "source_page")

    @field_validator("description")
    @classmethod
    def _empty_description_is_null(cls, v: Optional[str]) -> Optional[str]:
        return v or None

    @field_validator("fetched_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("fetched_at must include a timezone")
        return v

    @model_validator(mode="after")
    def _price_consistent(self) -> "Book":
        expected = normalize_price(self.price_text)
        if expected is None or abs(expected - self.price_gbp) > 1e-9:
            raise ValueError("price_gbp does not match price_text")
        return self
