# The polite scraper

FlyRank AI Internship · Backend AI Engineering · A9 (Week 5) · Python lane

## Target classification

| Question | Answer |
|---|---|
| **Which site?** | [Books to Scrape](https://books.toscrape.com/), part of [toscrape.com](https://toscrape.com/) |
| **Why may I automate it?** | It's a **sandbox**. Its own page says it is "a fictional bookstore that desperately wants to be scraped", "a safe place for beginners learning web scraping". The books, prices and stock are fictional, and no person's data is involved. |
| **robots.txt** | I requested `https://books.toscrape.com/robots.txt` once (25 Nov 2026): **HTTP 404, no robots file found.** A missing file isn't permission; the sandbox statement above is. |
| **How much?** | Only the **first 3 catalogue pages** and the **60 book pages** they link to: 63 pages, about 1 MB, out of 1,000 books / 50 catalogue pages. |
| **What data?** | Per book: title, URL, price, availability, star rating, description, plus where and when it was fetched. |
| **Why is that appropriate?** | It's a public practice site built for exactly this, the scope is small and fixed, every request is identified, slow and cached, and nothing personal or behind a login is collected. |

**I will not reuse this code on another site without checking its rules and terms first.**
