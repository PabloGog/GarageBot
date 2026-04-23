#!/usr/bin/env python3
"""
Garage listing monitor for ss.lv and city24.lv
Sends Telegram notification when new garage listings appear.

Setup:
  pip install requests beautifulsoup4

Config:
  Set BOT_TOKEN and CHAT_ID below, then run:
  python garage_monitor.py

Cron (every 30 min):
  */30 * * * * /usr/bin/python3 /path/to/garage_monitor.py
"""

import os
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────

BOT_TOKEN = "8303942608:AAGhwyfjxYxHAjTzX32peN4M66YqsJjtV4U"   # from @BotFather
CHAT_ID   = "@AceKong"    # your Telegram user/chat ID

# File to store seen listing IDs between runs
STATE_FILE = os.path.join(os.path.dirname(__file__), "garage_seen.json")

# Search URLs — tweak filters as needed
SOURCES = [
    {
        "name": "ss.lv",
        "url": "https://www.ss.lv/lv/real-estate/premises/garages/riga/",

        "parser": "parse_ss",
    },
    {
        "name": "city24.lv",
        "url": "https://www.city24.lv/real-estate-search/garages-for-sale/riga/id=245396-city",
        "parser": "parse_city24",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── PARSERS ───────────────────────────────────────────────────────────────────

def parse_ss(html: str) -> list[dict]:
    """Parse ss.lv listing page."""
    soup = BeautifulSoup(html, "html.parser")
    listings = []

    for row in soup.select("tr[id^='tr_']"):
        link_tag = row.select_one("a.am")
        if not link_tag:
            continue
        href = link_tag.get("href", "")
        if not href.startswith("/"):
            continue
        url = "https://www.ss.lv" + href
        title = link_tag.get_text(strip=True)

        price_td = row.select_one("td.msga2-o.pp6")
        price = price_td.get_text(strip=True) if price_td else "—"

        listing_id = hashlib.md5(url.encode()).hexdigest()[:12]
        listings.append({
            "id": listing_id,
            "title": title,
            "price": price,
            "url": url,
            "source": "ss.lv",
        })

    return listings


def parse_city24(html: str) -> list[dict]:
    """Parse city24.lv listing page."""
    soup = BeautifulSoup(html, "html.parser")
    listings = []

    for card in soup.select("article.object-item, div.listing-item"):
        link_tag = card.select_one("a[href]")
        if not link_tag:
            continue
        href = link_tag.get("href", "")
        url = href if href.startswith("http") else "https://www.city24.lv" + href
        title_tag = card.select_one("h2, h3, .object-title")
        title = title_tag.get_text(strip=True) if title_tag else "Garāža"
        price_tag = card.select_one(".price, .object-price")
        price = price_tag.get_text(strip=True) if price_tag else "—"

        listing_id = hashlib.md5(url.encode()).hexdigest()[:12]
        listings.append({
            "id": listing_id,
            "title": title,
            "price": price,
            "url": url,
            "source": "city24.lv",
        })

    return listings


# ── STATE ─────────────────────────────────────────────────────────────────────

def load_seen() -> set:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)


# ── TELEGRAM ──────────────────────────────────────────────────────────────────

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Telegram error: {e}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def fetch(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"Fetch error {url}: {e}")
        return None


def main():
    seen = load_seen()
    new_listings = []

    parsers = {
        "parse_ss": parse_ss,
        "parse_city24": parse_city24,
    }

    for source in SOURCES:
        print(f"[{datetime.now():%H:%M:%S}] Checking {source['name']}...")
        html = fetch(source["url"])
        if not html:
            continue

        parser_fn = parsers[source["parser"]]
        listings = parser_fn(html)
        print(f"  Found {len(listings)} listings")

        for listing in listings:
            if listing["id"] not in seen:
                new_listings.append(listing)
                seen.add(listing["id"])

    if new_listings:
        print(f"  {len(new_listings)} NEW listings!")
        for l in new_listings:
            msg = (
                f"🏠 <b>Новый гараж — {l['source']}</b>\n"
                f"{l['title']}\n"
                f"💰 {l['price']}\n"
                f"📍 Рига, Курземе\n"
                f"🔗 <a href='{l['url']}'>{l['url']}</a>"
            )
            send_telegram(msg)
    else:
        print("  No new listings.")

    save_seen(seen)


if __name__ == "__main__":
    main()
