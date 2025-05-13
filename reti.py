"""
Retigabine user-extraction (defensive rewrite)
Thread: https://www.tinnitustalk.com/threads/retigabine-trobalt-potiga-—-general-discussion.5074/

pip install requests cloudscraper beautifulsoup4
# cloudscraper handles most Cloudflare "Just a moment" pages automatically
"""
import re, sys, time
from collections import OrderedDict
from pathlib import Path

import cloudscraper                # <- handles Cloudflare
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = (
    "https://www.tinnitustalk.com/threads/"
    "retigabine-trobalt-potiga-%E2%80%94-general-discussion.5074/"
)
HEADERS = {
    # mimic a modern desktop browser
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

# ---------- helper: iterate pages with Cloudflare bypass ---------- #
def iter_pages():
    scraper = cloudscraper.create_scraper(headers=HEADERS)
    page_num = 1
    while True:
        url = BASE_URL if page_num == 1 else f"{BASE_URL}page-{page_num}"
        r = scraper.get(url, timeout=30)
        print(f"[fetch] {url} -> {r.status_code}")
        if r.status_code >= 400:
            print("[stop] HTTP error.")
            break
        # XenForo sometimes embeds the "Oops!" phrase even on success
        # so only abort if *no* <article> tags are present.
        if "<article" not in r.text.lower():
            print("[stop] No <article> tags found.")
            break
        yield r.text
        page_num += 1
        time.sleep(1)                         # polite crawling

# ---------- detection regexes ---------- #
DRUG_NAMES = r"(?:retigabine|trobalt|potiga|rtb)"
DOSAGE     = r"\b\d{1,4}\s?(?:mg|milligrams?)\b"

POS_RE = re.compile(
    rf"\b(i['’]?m|i\s+am|i['’]?ve|i\s+have|i\s+will|i['’]?ll|"
    rf"i\s+started|i\s+began|i\s+tried|i\s+took|i\s+take|i\s+have\s+been)\b"
    rf"(?:(?!\bnever\b|\bnot\b)[\s\S]{{0,120}}?)"   # up to 120 chars, skip 'never/not'
    rf"{DRUG_NAMES}",
    flags=re.I,
)
NEG_RE = re.compile(
    rf"\b(i\s+have\s+not|i\s+haven['’]?t|i\s+never|i\s+won['’]?t|i\s+will\s+not|"
    rf"i\s+don['’]?t|i\s+do\s+not)\b"
    rf"(?:[\s\S]{{0,60}}?)"
    rf"{DRUG_NAMES}",
    flags=re.I,
)

def mentions_use(text: str) -> bool:
    if NEG_RE.search(text):
        return False
    return bool(POS_RE.search(text) or
                (re.search(DRUG_NAMES, text, re.I) and re.search(DOSAGE, text, re.I)))

# ---------- main ---------- #
def extract_users():
    users = OrderedDict()
    for html in iter_pages():
        soup = BeautifulSoup(html, "html.parser")
        for art in soup.select("article"):
            # strip quoted passages
            for q in art.select("blockquote"):
                q.decompose()
            body = art.get_text(" ", strip=True)
            if not body or not mentions_use(body):
                continue
            author = (
                art.get("data-author") or
                art.select_one(".message-name,.username")
            )
            name = getattr(author, "text", author).strip()
            if name:
                users[name] = None
    return list(users)

if __name__ == "__main__":
    names = extract_users()
    if not names:
        sys.exit("\nNo users detected. Run with --debug or see README for tips.\n")
    out = Path("retigabine_users.txt")
    out.write_text("\n".join(names), encoding="utf-8")
    print(f"\nFound {len(names)} confirmed users:\n")
    print("\n".join(names))
    print(f"\nSaved list to {out.absolute()}\n")
