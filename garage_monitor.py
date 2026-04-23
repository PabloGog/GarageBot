#!/usr/bin/env python3
"""
Garage listing monitor — ss.lv only
Sends Telegram notification when new listings appear.

Setup:
  pip install requests beautifulsoup4

Env vars required:
  BOT_TOKEN — from @BotFather
  CHAT_ID   — your Telegram user ID (from @userinfobot)
"""

import os
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────

BOT_TOKEN  = os.environ.get("BOT_TOKEN", "")
CHAT_ID    = os.environ.get("CHAT_ID", "")
STATE_FILE = os.path.join(os.path.dirname(__file__), "garage_seen.json")

SOURCE_URL = "https://www.ss.lv/lv/real-estate/premises/garages/riga/ilguciems/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── PARSER ────────────────────────────────────────────────────────────────────

def parse_ss(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []

    for row in soup.select("tr[id^='tr_']"):
        link_tag = row.select_one("a.am")
        if not link_tag:
            continue
        href = link_tag.get("href", "")
        if not href.startswith("/"):
            continue
        url   = "https://www.ss.lv" + href
        title = link_tag.get_text(strip=True)

        price_td = row.select_one("td.msga2-o.pp6")
        price    = price_td.get_text(strip=True) if price_td else "—"

        listing_id = hashlib.md5(url.encode()).hexdigest()[:12]
        listings.append({"id": listing_id, "title": title, "price": price, "url": url})

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
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Telegram error: {e}")

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: BOT_TOKEN and CHAT_ID must be set as environment variables.")
        exit(1)

    print(f"[{datetime.now():%H:%M:%S}] Checking ss.lv...")

    try:
        r = requests.get(SOURCE_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"Fetch error: {e}")
        exit(0)

    listings = parse_ss(html)
    print(f"  Found {len(listings)} listings total")

    seen     = load_seen()
    is_first = len(seen) == 0
    new_ones = [l for l in listings if l["id"] not in seen]

    for l in listings:
        seen.add(l["id"])
    save_seen(seen)

    if is_first:
        print(f"  First run — saved {len(listings)} listings, no notifications sent.")
        return

    if new_ones:
        print(f"  {len(new_ones)} NEW listing(s)!")
        for l in new_ones:
            msg = (
                f"🏠 <b>Новый гараж на ss.lv</b>\n"
                f"{l['title']}\n"
                f"💰 {l['price']}\n"
                f"📍 Рига, Курземе\n"
                f"🔗 <a href='{l['url']}'>{l['url']}</a>"
            )
            send_telegram(msg)
    else:
        print("  No new listings.")

if __name__ == "__main__":
    main()
