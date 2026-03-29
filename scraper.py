"""
scraper.py — Fetches all configured sources, deduplicates against SQLite,
returns only genuinely new items since last run.
"""

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import feedparser
import httpx
import requests
import yaml
from bs4 import BeautifulSoup
from loguru import logger

# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RawItem:
    source_id: str
    source_name: str
    title: str
    url: str
    content: str          # raw text (truncated to 4000 chars)
    published: str        # ISO datetime string
    priority: str         # critical / high / medium
    tags: list[str]
    content_hash: str     # SHA-256 of title+content — used for dedup


# ─────────────────────────────────────────────────────────────────────────────
# Database (SQLite — simple, no deps, perfect for this scale)
# ─────────────────────────────────────────────────────────────────────────────

class ItemStore:
    def __init__(self, db_path: str = "./data/rcmaas.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_items (
                content_hash TEXT PRIMARY KEY,
                source_id    TEXT,
                title        TEXT,
                url          TEXT,
                first_seen   TEXT
            )
        """)
        self.conn.commit()

    def is_new(self, content_hash: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM seen_items WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return row is None

    def mark_seen(self, item: RawItem):
        self.conn.execute(
            "INSERT OR IGNORE INTO seen_items VALUES (?, ?, ?, ?, ?)",
            (item.content_hash, item.source_id, item.title, item.url,
             datetime.now(timezone.utc).isoformat())
        )
        self.conn.commit()

    def close(self):
        self.conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Fetchers
# ─────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; RCMaaS-Bot/1.0; "
        "+https://your-domain.com/bot-info)"
    )
}


def _hash(title: str, content: str) -> str:
    raw = f"{title}||{content[:500]}"
    return hashlib.sha256(raw.encode()).hexdigest()


def fetch_rss(source: dict) -> list[RawItem]:
    """Parse an RSS/Atom feed."""
    items = []
    try:
        feed = feedparser.parse(source["feed_url"])
        for entry in feed.entries[:15]:  # cap at 15 most recent
            title   = entry.get("title", "")
            url     = entry.get("link", "")
            summary = entry.get("summary", entry.get("description", ""))
            # Strip HTML from summary
            soup    = BeautifulSoup(summary, "lxml")
            content = soup.get_text(separator=" ", strip=True)[:4000]
            pub     = entry.get("published", entry.get("updated",
                        datetime.now(timezone.utc).isoformat()))

            items.append(RawItem(
                source_id   = source["id"],
                source_name = source["name"],
                title       = title,
                url         = url,
                content     = content,
                published   = str(pub),
                priority    = source.get("priority", "medium"),
                tags        = source.get("tags", []),
                content_hash = _hash(title, content),
            ))
    except Exception as e:
        logger.error(f"RSS fetch failed for {source['id']}: {e}")
    return items


def fetch_scrape(source: dict) -> list[RawItem]:
    """Scrape a web page and extract items by CSS selector."""
    items = []
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        blocks = soup.select(source.get("scrape_selector", "article"))[:10]

        for block in blocks:
            title_el = block.find(["h2", "h3", "h4", "a"])
            title    = title_el.get_text(strip=True) if title_el else "Update"
            link_el  = block.find("a", href=True)
            url      = link_el["href"] if link_el else source["url"]
            if url.startswith("/"):
                from urllib.parse import urlparse
                base = urlparse(source["url"])
                url  = f"{base.scheme}://{base.netloc}{url}"
            content  = block.get_text(separator=" ", strip=True)[:4000]

            items.append(RawItem(
                source_id    = source["id"],
                source_name  = source["name"],
                title        = title,
                url          = url,
                content      = content,
                published    = datetime.now(timezone.utc).isoformat(),
                priority     = source.get("priority", "medium"),
                tags         = source.get("tags", []),
                content_hash = _hash(title, content),
            ))
        time.sleep(1)  # polite crawl delay
    except Exception as e:
        logger.error(f"Scrape failed for {source['id']}: {e}")
    return items


def fetch_federal_register_api(source: dict) -> list[RawItem]:
    """Call the Federal Register JSON API."""
    items = []
    try:
        resp = httpx.get(
            source["api_url"],
            params=source["api_params"],
            timeout=30,
            headers=HEADERS
        )
        resp.raise_for_status()
        data = resp.json()
        for doc in data.get("results", [])[:15]:
            title   = doc.get("title", "")
            url     = doc.get("html_url", "")
            content = doc.get("abstract", doc.get("excerpts", ""))[:4000]
            pub     = doc.get("publication_date",
                               datetime.now(timezone.utc).isoformat())
            items.append(RawItem(
                source_id    = source["id"],
                source_name  = source["name"],
                title        = title,
                url          = url,
                content      = content,
                published    = pub,
                priority     = source.get("priority", "medium"),
                tags         = source.get("tags", []),
                content_hash = _hash(title, content),
            ))
    except Exception as e:
        logger.error(f"Federal Register API failed: {e}")
    return items


# ─────────────────────────────────────────────────────────────────────────────
# Main scraper
# ─────────────────────────────────────────────────────────────────────────────

def run_scraper(
    sources_path: str = "./sources.yaml",
    db_path: str = "./data/rcmaas.db"
) -> list[RawItem]:
    """
    Fetch all sources, return only items that are NEW since last run.
    Marks returned items as seen in the DB.
    """
    with open(sources_path) as f:
        config = yaml.safe_load(f)

    store = ItemStore(db_path)
    all_new: list[RawItem] = []

    for source in config["sources"]:
        logger.info(f"Fetching: {source['name']} [{source['type']}]")

        if source["type"] == "rss":
            fetched = fetch_rss(source)
        elif source["type"] == "scrape":
            fetched = fetch_scrape(source)
        elif source["type"] == "api":
            fetched = fetch_federal_register_api(source)
        else:
            logger.warning(f"Unknown type: {source['type']} for {source['id']}")
            continue

        for item in fetched:
            if store.is_new(item.content_hash):
                store.mark_seen(item)
                all_new.append(item)
                logger.success(f"  NEW: {item.title[:80]}")
            else:
                logger.debug(f"  skip (seen): {item.title[:60]}")

    store.close()

    # Sort: critical first, then high, then medium
    priority_order = {"critical": 0, "high": 1, "medium": 2}
    all_new.sort(key=lambda x: priority_order.get(x.priority, 3))

    logger.info(f"Scraper done. {len(all_new)} new items found.")
    return all_new


if __name__ == "__main__":
    from loguru import logger
    logger.add("./logs/scraper.log", rotation="7 days")
    items = run_scraper()
    for i in items:
        print(f"[{i.priority.upper()}] {i.source_name}: {i.title}")
