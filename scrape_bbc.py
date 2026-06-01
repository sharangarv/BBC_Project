"""
scrape_bbc.py
─────────────
Scrapes BBC News using public RSS feeds + article page fetching.
Saves results to raw_articles.json

Install:
    pip install requests beautifulsoup4 lxml

Run:
    python scrape_bbc.py                        # all sections, 100 articles
    python scrape_bbc.py --max 50               # limit to 50
    python scrape_bbc.py --sections world,tech  # specific sections only
    python scrape_bbc.py --delay 2              # slower, more polite
"""

import requests
import json
import time
import random
import re
import argparse
from bs4 import BeautifulSoup
from datetime import datetime
from html import unescape
from pathlib import Path


# ── BBC Public RSS Feeds ─────────────────────────────────────────────────────
RSS_FEEDS = {
    "top":         "https://feeds.bbci.co.uk/news/rss.xml",
    "world":       "https://feeds.bbci.co.uk/news/world/rss.xml",
    "uk":          "https://feeds.bbci.co.uk/news/uk/rss.xml",
    "technology":  "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "science":     "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "business":    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "health":      "https://feeds.bbci.co.uk/news/health/rss.xml",
    "sport":       "https://feeds.bbci.co.uk/sport/rss.xml",
    "india":       "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml",
    "entertainment": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
}

# ── Junk text patterns ───────────────────────────────────────────────────────
JUNK_PATTERNS = [
    r"Getty Images",
    r"Image source,.*",
    r"Image caption,.*",
    r"This video can not be played.*",
    r"To play this video.*",
    r"BBC [A-Z][a-z]+\s*\n",
    r"Share this article.*",
    r"Read more:.*",
    r"\bAdvertisement\b",
    r"Follow BBC.*on.*",
    r"You may also like.*",
    r"\[.*?\]",
]
JUNK_RE = re.compile("|".join(JUNK_PATTERNS), re.IGNORECASE)


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT":             "1",
        "Connection":      "keep-alive",
    })
    return session


def fetch_rss(session: requests.Session, section: str, feed_url: str) -> list:
    """Pull article stubs from a BBC RSS feed."""
    try:
        r = session.get(feed_url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"  [WARN] RSS failed for '{section}': {e}")
        return []

    soup = BeautifulSoup(r.content, "xml")
    items = soup.find_all("item")
    results = []

    for item in items:
        # BBC RSS: <link> tag content sits as a NavigableString sibling
        link_tag = item.find("link")
        url = ""
        if link_tag:
            # Try .get_text() first, then next_sibling
            url = link_tag.get_text(strip=True)
            if not url and link_tag.next_sibling:
                url = str(link_tag.next_sibling).strip()

        title   = item.find("title").get_text(strip=True)   if item.find("title")       else ""
        desc    = item.find("description").get_text(strip=True) if item.find("description") else ""
        pubdate = item.find("pubDate").get_text(strip=True)  if item.find("pubDate")     else ""

        if url and "bbc.co.uk" in url or url and "bbc.com" in url:
            results.append({
                "url":            url,
                "headline":       unescape(title),
                "description":    unescape(desc),
                "published_date": pubdate,
                "section":        section,
            })

    print(f"  [RSS] {section:15s} → {len(results)} articles")
    return results


def scrape_article(session: requests.Session, url: str) -> dict:
    """Fetch a BBC article page and extract body, author, tags, images."""
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        return {"error": str(e)}

    soup = BeautifulSoup(r.content, "lxml")

    # ── Body text ─────────────────────────────────────────────────────────────
    body_text = ""

    # BBC article body selectors (multiple layouts exist)
    selectors = [
        "article[data-component='text-block']",
        "div[data-component='text-block']",
        "div.ssrcss-11r1m41-RichTextComponentWrapper",  # newer BBC layout
        "div[class*='RichTextContainer']",
        "div[class*='article__body']",
        "div.story-body__inner",                         # older BBC layout
        "div#story-body",
        "article",
    ]
    for sel in selectors:
        blocks = soup.select(sel)
        if blocks:
            paras = []
            for block in blocks:
                paras += [p.get_text(" ", strip=True) for p in block.find_all("p")]
            text = " ".join(p for p in paras if len(p.split()) > 5)
            if len(text.split()) > 30:
                body_text = text
                break

    # Fallback: all <p> with enough words
    if not body_text:
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True).split()) > 8]
        body_text = " ".join(paras)

    # ── Author ────────────────────────────────────────────────────────────────
    author = ""
    for sel in [
        "span[class*='byline']",
        "p[class*='byline']",
        "div[class*='contributor']",
        "span[class*='author']",
        "strong[class*='author']",
    ]:
        tag = soup.select_one(sel)
        if tag:
            author = tag.get_text(strip=True).replace("By ", "").strip()
            break
    if not author:
        meta = soup.find("meta", {"name": "author"}) or soup.find("meta", {"property": "article:author"})
        if meta:
            author = meta.get("content", "")

    # ── Tags ──────────────────────────────────────────────────────────────────
    tags = []
    for sel in ["li[class*='tags'] a", "a[class*='tag']", "ul[class*='tags'] a"]:
        found = [t.get_text(strip=True) for t in soup.select(sel)]
        if found:
            tags = found
            break

    # ── Images ────────────────────────────────────────────────────────────────
    images = list({
        img.get("src") or img.get("data-src", "")
        for img in soup.select("article img, div[class*='image'] img")
        if (img.get("src") or img.get("data-src", "")).startswith("http")
    })

    # ── Clean body ────────────────────────────────────────────────────────────
    body_text = unescape(body_text)
    body_text = JUNK_RE.sub("", body_text)
    body_text = re.sub(r"\s{2,}", " ", body_text).strip()

    return {
        "body_text": body_text,
        "author":    author,
        "tags":      tags,
        "images":    images,
    }


def run(max_articles: int, output_path: str, delay: float, sections_filter: list):
    session  = make_session()
    seen_urls = set()
    all_stubs = []

    # ── Step 1: Collect stubs from RSS ───────────────────────────────────────
    print("\n📡 Step 1: Fetching BBC RSS feeds...\n")
    feeds_to_fetch = {
        k: v for k, v in RSS_FEEDS.items()
        if not sections_filter or k in sections_filter
    }
    for section, url in feeds_to_fetch.items():
        stubs = fetch_rss(session, section, url)
        for s in stubs:
            if s["url"] not in seen_urls:
                seen_urls.add(s["url"])
                all_stubs.append(s)
        time.sleep(random.uniform(0.3, 0.8))

    total = min(len(all_stubs), max_articles)
    print(f"\n🔍 Step 2: Scraping {total} article pages...\n")

    articles = []
    for i, stub in enumerate(all_stubs[:max_articles], 1):
        print(f"  [{i:>3}/{total}] {stub['headline'][:65]}...")
        details = scrape_article(session, stub["url"])

        if "error" in details:
            print(f"          ⚠ Skipped ({details['error']})")
            continue

        wc = len(details["body_text"].split())
        if wc < 50:
            print(f"          ⚠ Skipped (only {wc} words)")
            continue

        articles.append({
            "url":            stub["url"],
            "headline":       stub["headline"],
            "description":    stub["description"],
            "author":         details["author"],
            "published_date": stub["published_date"],
            "section":        stub["section"],
            "tags":           details["tags"],
            "body_text":      details["body_text"],
            "word_count":     wc,
            "images":         details["images"],
            "scraped_at":     datetime.utcnow().isoformat() + "Z",
        })
        print(f"          ✓ {wc} words | {stub['section']} | {details['author'] or 'author unknown'}")

        time.sleep(random.uniform(delay, delay + 1.0))

    # ── Save ─────────────────────────────────────────────────────────────────
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*55}")
    print(f"  ✅  {len(articles)} articles saved → {Path(output_path).resolve()}")
    print(f"{'='*55}\n")
    print("Next step:  python filter_articles.py\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Scrape BBC News via RSS + article pages.")
    p.add_argument("--max",      type=int,   default=100,               help="Max articles (default 100)")
    p.add_argument("--output",   type=str,   default="raw_articles.json", help="Output file")
    p.add_argument("--delay",    type=float, default=1.5,               help="Seconds between requests (default 1.5)")
    p.add_argument("--sections", type=str,   default="",                help="Comma-separated: top,world,uk,technology,science,business,health,sport,india,entertainment")
    args = p.parse_args()

    sections = [s.strip() for s in args.sections.split(",") if s.strip()] or None
    run(args.max, args.output, args.delay, sections)