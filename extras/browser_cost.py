"""Stretch: what does a real browser cost compared with a plain HTTP request?

Target: https://quotes.toscrape.com/js/ (the sandbox's JavaScript page: its quotes are built by a script, so they are
NOT in the HTML the server sends). One request each way, same user-agent.

Optional dependencies, not needed for the scraper:  pip install playwright psutil  (then: playwright install chromium,
or use an installed Edge/Chrome as below).

    python extras/browser_cost.py
"""
import gc
import json
import time

import psutil
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL = "https://quotes.toscrape.com/js/"
UA = "FlyRankInternship-A9/1.0 (+https://github.com/azizulabedinazmi/FlyRank_A9-Scraper)"
me = psutil.Process()


def tree_rss_mb() -> float:
    """Memory of this Python process plus every process it started (the browser and its helpers)."""
    procs = [me] + me.children(recursive=True)
    total = 0
    for p in procs:
        try:
            total += p.memory_info().rss
        except psutil.Error:
            pass
    return total / 2**20


gc.collect()
base = tree_rss_mb()

# 1. plain HTTP
t = time.perf_counter()
r = requests.get(URL, headers={"User-Agent": UA}, timeout=10)
plain_s = time.perf_counter() - t
plain_quotes = len(BeautifulSoup(r.text, "html.parser").select("div.quote"))
plain_mb = tree_rss_mb() - base

time.sleep(1)  # be polite between the two requests

# 2. a real browser
peak = base
t = time.perf_counter()
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge")  # uses the installed Edge; change to chrome or bundled chromium
    page = browser.new_page(user_agent=UA)
    page.goto(URL, wait_until="networkidle", timeout=20000)
    browser_quotes = page.locator("div.quote").count()
    peak = tree_rss_mb()
    browser.close()
browser_s = time.perf_counter() - t

result = {
    "url": URL,
    "plain_http": {"seconds": round(plain_s, 2), "extra_memory_mb": round(plain_mb, 1), "quotes_found": plain_quotes,
                   "status": r.status_code, "html_bytes": len(r.content)},
    "browser": {"seconds": round(browser_s, 2), "extra_memory_mb": round(peak - base, 1), "quotes_found": browser_quotes},
}
print(json.dumps(result, indent=2))
