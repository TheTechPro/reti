# tinnitustalk_retigabine_scraper.py
# Builds a CSV with: username, tinnitus_cause, somatic, retigabine_suppression
# Works with Python 3.8+ and requires: cloudscraper, beautifulsoup4, pandas, tqdm

from __future__ import annotations

import argparse
import re
import time
from typing import List, Tuple, Dict, Optional
from urllib.parse import urljoin

import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup
from tqdm.auto import tqdm

BASE_THREAD = (
    "https://www.tinnitustalk.com/threads/retigabine-trobalt-potiga-%E2%80%94-general-discussion.5074/"
)
MAX_PAGE = 268  # last page on 2025-05-13

# ----- pattern definitions -------------------------------------------------
SUPPRESSION_POS = re.compile(
    r"\b(suppression|suppressed|reduced|reduction|quieter|quiet|lowered|improved|went\s+down|silenced|better)\b",
    re.I,
)
SUPPRESSION_NEG = re.compile(
    r"\b(no|not|didn['`]t|never|hardly|little|barely)\s+(any\s+)?(suppression|help|benefit|improve|effect)\b",
    re.I,
)

CAUSE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(noise|loud|concert|music|club|gunshot|explosion|fireworks|acoustic)"), "acoustic trauma"),
    (re.compile(r"\b(ototoxic|drug\s*induced|medication|antibiotic|aminoglycoside|cisplatin|chemotherapy)"), "ototoxicity"),
    (re.compile(r"\b(ear\s*infection|otitis|sinusitis|infection)"), "infection"),
    (re.compile(r"\b(stress|anxiety|depression|panic)"), "stress"),
    (re.compile(r"meniere"), "menieres"),
]
CAUSE_NEG = re.compile(r"\b(not|no|never)\s+(the\s+)?(cause|caused|from)\b", re.I)

SOMATIC_POS = re.compile(
    r"\b(move|moving|turn|turning|rotate|rotating|tilt|press|pressing|touch|clench|open|close)(ing|ed)?\s+(my\s+)?(jaw|neck|head).*?(change|modulate|alter|affect|influence)|somatic\s+tinnitus",
    re.I,
)
SOMATIC_NEG = re.compile(r"\b(not|no|never)\s+(somatic|change\s+when|modulat)", re.I)

RE_PROF_CAUSE = re.compile(r"Cause\s+of\s+Tinnitus", re.I)
RE_PROF_SOMATIC = re.compile(r"Somatic\s+Tinnitus", re.I)
# ---------------------------------------------------------------------------

def make_scraper() -> cloudscraper.CloudScraper:
    return cloudscraper.create_scraper(
        browser={"browser": "firefox", "platform": "android", "desktop": False}
    )

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape TinnitusTalk Retigabine thread")
    p.add_argument("csvfile", nargs="?", default="usernames.csv", help="CSV with usernames (default: usernames.csv)")
    p.add_argument("--out", default="tinnitustalk_retigabine_report.csv", help="Output CSV")
    p.add_argument("--delay", type=float, default=1.0, help="Delay between HTTP requests (seconds)")
    return p.parse_args()

def clean_username(name: str) -> str:
    return name.strip().lstrip("@")

def thread_pages() -> List[str]:
    return [BASE_THREAD] + [f"{BASE_THREAD}page-{p}" for p in range(2, MAX_PAGE + 1)]

def fetch_posts_by_user(username: str, scraper, delay: float) -> Tuple[List[str], Optional[str]]:
    posts: List[str] = []
    profile_url: Optional[str] = None
    uname_lc = username.lower()
    for page in thread_pages():
        r = scraper.get(page, timeout=30)
        if r.status_code != 200:
            time.sleep(delay)
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for art in soup.select("article"):
            a_tag = art.find("a", {"data-user-id": True})
            if not a_tag:
                continue
            if a_tag.text.strip().lower() != uname_lc:
                continue
            posts.append(str(art))
            if not profile_url:
                profile_url = urljoin(BASE_THREAD, a_tag["href"])
        time.sleep(delay / 4)
    return posts, profile_url

def detect_suppression(posts_html: List[str]) -> str:
    for html in posts_html:
        txt = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
        if "retigabine" not in txt and "trobalt" not in txt:
            continue
        if SUPPRESSION_NEG.search(txt):
            return "N"
        if SUPPRESSION_POS.search(txt):
            return "Y"
    return "N"

def infer_cause_and_somatic(posts_html: List[str]) -> Tuple[str, str]:
    text = " ".join(
        BeautifulSoup(h, "html.parser").get_text(" ", strip=True).lower() for h in posts_html
    )
    somatic = "unknown"
    if SOMATIC_NEG.search(text):
        somatic = "N"
    elif SOMATIC_POS.search(text):
        somatic = "Y"
    cause = "unknown"
    if not CAUSE_NEG.search(text):
        for pat, label in CAUSE_PATTERNS:
            if pat.search(text):
                cause = label
                break
    return cause, somatic

def scrape_profile(url: str, scraper, delay: float) -> Tuple[str, str]:
    cause = somatic = "unknown"
    r = scraper.get(url, timeout=30)
    if r.status_code != 200:
        time.sleep(delay)
        return cause, somatic
    soup = BeautifulSoup(r.text, "html.parser")
    for dt in soup.select(".pairsJustified dt"):
        label = dt.get_text(" ", strip=True)
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        val = dd.get_text(" ", strip=True)
        if RE_PROF_CAUSE.match(label):
            cause = val or "unknown"
        elif RE_PROF_SOMATIC.match(label):
            somatic = "Y" if val.lower().startswith("y") else "N"
    return cause, somatic

def main() -> None:
    ns = parse_args()
    usernames = [clean_username(u) for u in pd.read_csv(ns.csvfile, header=None)[0]]
    scraper = make_scraper()
    results: List[Dict[str, str]] = []
    for user in tqdm(usernames, desc="Processing users"):
        posts, profile_url = fetch_posts_by_user(user, scraper, ns.delay)
        suppression = detect_suppression(posts)
        cause, somatic = infer_cause_and_somatic(posts)
        if (cause == "unknown" or somatic == "unknown") and profile_url:
            cause_p, somatic_p = scrape_profile(profile_url, scraper, ns.delay)
            if cause == "unknown":
                cause = cause_p
            if somatic == "unknown":
                somatic = somatic_p
        results.append(
            {
                "username": user,
                "tinnitus_cause": cause,
                "somatic": somatic,
                "retigabine_suppression": suppression,
            }
        )
        time.sleep(ns.delay)
    pd.DataFrame(results).to_csv(ns.out, index=False)
    print("[done] Wrote", ns.out, "(n=", len(results), ")")

if __name__ == "__main__":
    main()