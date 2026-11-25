"""Central configuration for the polite scraper."""

from pathlib import Path

# Project layout: <root>/src/config.py -> <root>
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
OUTPUT_DIR = PROJECT_ROOT / "output"

BOOKS_FILE = OUTPUT_DIR / "books.json"
ERRORS_FILE = OUTPUT_DIR / "errors.json"
REPORT_FILE = OUTPUT_DIR / "run-report.json"

# Target site
ALLOWED_HOST = "books.toscrape.com"
START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3

# Politeness
CONTACT_URL = "https://github.com/azizulabedinazmi/FlyRank_A9-Scraper"
USER_AGENT = f"FlyRankInternship-A9/1.0 (+{CONTACT_URL})"
REQUEST_TIMEOUT = 10  # seconds (connect + read)
# 0.5 s is the hard floor required by the brief; 0.75 s is the target so that
# timer jitter can never push a gap below the floor.
MIN_DELAY_FLOOR = 0.5
REQUEST_DELAY = 0.75
# Extra back-off before the single retry (timeouts / 5xx only).
RETRY_WAIT = 1.5
MAX_RETRIES = 1
