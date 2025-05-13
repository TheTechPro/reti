"""
Retigabine user-extraction
Thread:  https://www.tinnitustalk.com/threads/retigabine-trobalt-potiga-—-general-discussion.5074/
Python 3.8+  |  pip install requests beautifulsoup4
"""
import re, time, sys
from pathlib import Path
from collections import OrderedDict
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.tinnitustalk.com/threads/retigabine-trobalt-potiga-%E2%80%94-general-discussion.5074/"
HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; RetigabineScraper/1.0)"}

# ---------- helper: iterate over all thread pages ---------- #
def iter_pages():
    """Yield every page URL until XenForo's 404/‘Oops!’ page appears."""
    n = 1
    while True:
        url = BASE_URL if n == 1 else f"{BASE_URL}page-{n}"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200 or "Oops! We ran into some problems." in resp.text:
            break
        yield resp.text
        n += 1
        time.sleep(1)                       # be polite: 1 request / s

# ---------- detection patterns ---------- #
DRUG_NAMES   = r"(?:retigabine|trobalt|potiga|rtb)"
DOSAGE       = r"\b\d{1,4}\s?(?:mg|milligrams?)\b"
# ✅ positive: first-person + action verb + drug name (optionally dosage)
POS_CONTEXT  = re.compile(
    rf"\b(i'?m|i\s+am|i'?ve|i\s+have|i\s+will|i'?ll|i\s+started|i\s+just\s+started|i\s+recently\s+started|"
    rf"i\s+began|i\s+started\s+taking|i\s+tried|i\s+took|i\s+take|i\s+have\s+been\s+on)\s+"
    rf"(?:[^\n]{{0,60}}?)"                 # up to 60 chars lookahead (capture dosage somewhere nearby)
    rf"{DRUG_NAMES}"
    rf"(?:[^\n]{{0,60}}?)",               # and 60 chars after
    flags=re.I,
)
# ❌ negatives: “never tried”, “won’t take”, etc.
NEG_CONTEXT  = re.compile(
    rf"\b(i\s+have\s+not|i\s+haven't|i\s+never|i\s+won't|i\s+will\s+not|i\s+don't|i\s+do\s+not)\s+"
    rf"(?:[^\n]{{0,40}}?)"
    rf"{DRUG_NAMES}", 
    flags=re.I,
)

QUOTE_CSS = "blockquote"                 # XenForo quotes are wrapped in <blockquote>

def post_mentions_use(text: str) -> bool:
    """Return True if text is a positive mention AND not a negative one."""
    if NEG_CONTEXT.search(text):
        return False
    return bool(POS_CONTEXT.search(text) or                 # explicit ‘I took…’
                (re.search(DRUG_NAMES, text, re.I) and      # OR drug name + dosage in same post
                 re.search(DOSAGE, text, re.I)))

# ---------- main extraction ---------- #
def extract_users():
    users = OrderedDict()                # preserve discovery order
    for page_html in iter_pages():
        soup = BeautifulSoup(page_html, "html.parser")
        for article in soup.select("article"):
            # get raw post text w/o quoted passages
            for q in article.select(QUOTE_CSS):
                q.decompose()
            body = article.get_text(" ", strip=True)
            if not body:
                continue
            if post_mentions_use(body):
                username = article.get("data-author") or article.select_one(".message-name") or ""
                username = getattr(username, "text", username).strip()
                if username:
                    users[username] = None
    return list(users.keys())

if __name__ == "__main__":
    try:
        names = extract_users()
        if not names:
            sys.exit("No retigabine users detected – check your network or tweak patterns.")
        # save + print
        out = Path("retigabine_users.txt")
        out.write_text("\n".join(names), encoding="utf-8")
        print(f"\nFound {len(names)} unique users who appear to have **actually tried** retigabine:\n")
        print("\n".join(names))
        print(f"\nFull list written to: {out.absolute()}")
    except Exception as exc:
        sys.exit(f"Error: {exc}")