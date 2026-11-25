"""Validate, deduplicate by canonical URL, and write JSON atomically."""
import json
import os
from pathlib import Path

from pydantic import ValidationError

from schema import Book, normalize


def validate(raw_records: list[dict]) -> tuple[list[Book], list[dict]]:
    """Every raw record goes through normalize() and the Book schema. Failures are kept with the reason."""
    good: dict[str, Book] = {}  # keyed by canonical URL: the same book twice counts once
    bad = []
    for raw in raw_records:
        try:
            book = Book.model_validate(normalize(raw))
        except (ValueError, ValidationError) as e:  # ValidationError is a ValueError subclass; listed for clarity
            reason = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()) \
                if isinstance(e, ValidationError) else str(e)
            bad.append({"product_url": raw.get("product_url"), "reason": reason, "raw": raw})
            continue
        good.setdefault(book.product_url, book)
    return list(good.values()), bad


def write_json(path: Path, data) -> None:
    """Write to a temp file, then swap it in: a crash mid-write never leaves a half-written books.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def store(out_dir: Path, books: list[Book], errors: list[dict]) -> None:
    """books.json is rewritten from this run's records, never appended to, so a rerun can't duplicate anything."""
    write_json(out_dir / "books.json", [b.model_dump(mode="json") for b in books])
    write_json(out_dir / "errors.json", errors)
