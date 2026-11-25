"""The polite scraper: Books to Scrape, first 3 catalogue pages, 60 books -> clean, validated JSON.

Stage 0 only classifies the target (see README). No request code yet.
"""

BASE_URL = "https://books.toscrape.com/"
MAX_CATALOGUE_PAGES = 3

if __name__ == "__main__":
    print(f"Target: {BASE_URL} (first {MAX_CATALOGUE_PAGES} catalogue pages). Classification: see README.")
