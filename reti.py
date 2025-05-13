#!/usr/bin/env python3
"""
Retigabine user-extraction (defensive v1.1)
Thread: https://www.tinnitustalk.com/threads/retigabine-trobalt-potiga-—-general-discussion.5074/

Dependencies:
    pip install cloudscraper beautifulsoup4 requests
"""

import re, sys, time
from collections import OrderedDict
from pathlib import Path

import cloudscraper
from bs4 import BeautifulSoup

# -------------------------------------------------------------------------
BASE_URL = (
    "https://www.tinnitustalk.com/threads/"
    "retigabine-trobalt-potiga-%E2%80%94-general-discussion.5074/"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

# -------------------------------------------------------------------------
def iter_pages():
    """Yield raw HTML for every page until XenForo stops returning posts."""
    scraper = cloudscraper.create_scraper()
    scraper.headers.update(HEADERS)

    page = 1
    while True:
        url = BASE_URL if page == 1 else f"{BASE_URL}page-{page}"
        resp = scraper.get(url, timeout=30)
        print(f"[fetch] {url} -> {resp.status_code}")

        if resp.status_code >= 400:
            print("[stop] HTTP error.")
            break
        if "<article" not in resp.text.lower():
            print("[stop] No <article> tags found.")
            break

        yield resp.text
        page += 1
        time.sleep(1)            # 1 req/s politeness

# -------------------------------------------------------------------------
DRUG_NAMES = r"(?:retigabine|trobalt|potiga|rtb)"
DOSAGE     = r"\b\d{1,4}\s?(?:mg|milligrams?)\b"

POS_RE = re.compile(
    rf"\b(i['’]?m|i\s+am|i['’]?ve|i\s+have|i\s+will|i['’]?ll|"
    rf"i\s+started|i\s+began|i\s+tried|i\s+took|i\s+take|i\s+have\s+been)\b"
    rf"(?:(?!\bnever\b|\bnot\b)[\s\S]{{0,120}}?)"   # up to 120 chars, skip negations
    rf"{DRUG_NAMES}",
    flags=re.I,
)
NEG_RE = re.compile(
    rf"\b(i\s+have\s+not|i\s+haven['’]?t|i\s+never|i\s+won['’]?t|"
    rf"i\s+will\s+not|i\s+don['’]?t|i\s+do\s+not)\b"
    rf"(?:[\s\S]{{0,60}}?)"
    rf"{DRUG_NAMES}",
    flags=re.I,
)

def mentions_use(text: str) -> bool:
    """True if the post shows the author actually used retigabine."""
    if NEG_RE.search(text):
        return False
    return bool(
        POS_RE.search(text) or
        (re.search(DRUG_NAMES, text, re.I) and re.search(DOSAGE, text, re.I))
    )

# -------------------------------------------------------------------------
def extract_users():
    """Return an ordered list of unique usernames who tried retigabine."""
    users = OrderedDict()
    for html in iter_pages():
        soup = BeautifulSoup(html, "html.parser")
        for art in soup.select("article"):
            # strip quoted text to avoid false positives
            for q in art.select("blockquote"):
                q.decompose()
            body = art.get_text(" ", strip=True)
            if not body or not mentions_use(body):
                continue

            # ---------- robust author extraction ---------- #
            name = None

            # 1) data-author attribute (fastest)
            if art.has_attr("data-author"):
                name = art["data-author"].strip()

            # 2) fallback CSS selectors (desktop & mobile skins)
            if not name:
                elem = art.select_one(
                    ".message-name, .username--link, .username, [itemprop='name']"
                )
                if elem:
                    name = elem.get_text(strip=True)

            # 3) skip if still unknown
            if not name:
                continue

            users[name] = None
    return list(users)

# -------------------------------------------------------------------------
if __name__ == "__main__":
    names = extract_users()
    if not names:
        sys.exit("\nNo users detected — check fetch log, cookies, or regex patterns.\n")

    out = Path("retigabine_users.txt")
    out.write_text("\n".join(names), encoding="utf-8")

    print(f"\nFound {len(names)} confirmed users:\n")
    print("\n".join(names))
    print(f"\nSaved list to: {out.resolve()}\n")
