#!/usr/bin/env python3
"""Retry the full-text fetch for every article in
wsj_extracted/stocknews_consolidated.json, using curl (HTTP/2, browser
headers, longer timeout) and a cleaner extractor that prefers the article
body container over every <p> on the page (Zacks pages otherwise come back
as mostly cookie banners and sidebar promos)."""
import json
import os
import subprocess

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "wsj_extracted", "stocknews_consolidated.json")
MAX_TEXT_CHARS = 8000
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
BODY_SELECTORS = [
    "#comtext", ".commentary_body", "article", ".main-body-container",
    ".bw-release-story", "#bw-release-story", ".article-body", ".article__body",
    "[itemprop=articleBody]", ".caas-body", "main",
]
JUNK = ("cookie", "Accept All", "Deny Optional", "Zacks Rank #1", "Strong Buy stocks", "ZacksTrade",
        "Privacy Policy", "Visit our website", "Hand-picked from", "Based on total page views",
        "Based on page view growth", "best ETFs", "top picks", "Zacks Investment Research |")
# Zacks (and some other templated sites) sometimes append unrelated
# "related content" / rank-list / notification-signup blocks straight
# after the real article body, with no HTML boundary distinguishing them --
# a per-paragraph JUNK filter alone can't tell "this whole paragraph is an
# ad" from "this paragraph mentions a stock ticker", so instead this marks
# where the boilerplate section STARTS and drops everything from there on,
# keeping only what came before it.
TRUNCATE_MARKERS = (
    "We'd like to show you notifications",
    "This includes personalizing content and advertising",
    "Zacks #1 Rank List",
    "We use cookies to understand how you use our site",
)


def curl(url):
    proc = subprocess.run(
        ["curl", "-s", "-L", "--compressed", "-m", "45", "-A", UA,
         "-H", "Accept: text/html,application/xhtml+xml",
         "-H", "Accept-Language: en-US,en;q=0.9",
         "-w", "\n__HTTP_STATUS__%{http_code}", url],
        capture_output=True, text=True, errors="replace",
    )
    body, _, status = proc.stdout.rpartition("\n__HTTP_STATUS__")
    return (status or "000"), body


def extract(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    candidates = [c for sel in BODY_SELECTORS for c in soup.select(sel)]
    container = max(candidates, key=lambda c: len(c.find_all("p")), default=None)
    if container is None or len(container.find_all("p")) < 3:
        container = soup
    paragraphs = container.find_all("p")
    lines = []
    for p in paragraphs:
        t = p.get_text(" ", strip=True)
        if any(marker in t for marker in TRUNCATE_MARKERS):
            break
        if len(t) > 40 and not any(j in t for j in JUNK) and t not in lines:
            lines.append(t)
    return "\n".join(lines)[:MAX_TEXT_CHARS] or None


BOT_PAGE = ("you were a bot", "Just a moment", "verify you are human", "Access Denied")


def urllib_get(url):
    import urllib.request
    try:
        request = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=30) as response:
            return str(response.status), response.read().decode("utf-8", errors="replace")
    except Exception:
        return "000", ""


def best_text(url):
    best = None
    for fetch in (urllib_get, curl):
        status, html = fetch(url)
        if not (status.startswith("2") and html):
            continue
        text = extract(html)
        if text and not any(b in text for b in BOT_PAGE) and len(text) > len(best or ""):
            best = text
    return best


def main():
    data = json.load(open(PATH))
    summary = {}
    for note_key, obs in data.items():
        for a in obs["articles"]:
            if a.get("type") != "Article":
                continue
            text = best_text(a["url"])
            existing = a.get("full_text")
            if existing and any(b in existing for b in BOT_PAGE):
                existing = None
            if not text or len(text) < len(existing or ""):
                text = existing
            status = "ok " if text else "---"
            a["full_text"] = text
            ok = bool(text)
            summary.setdefault(a["source"], [0, 0])[0 if ok else 1] += 1
            print(f"{note_key:13} {status} {len(text or ''):>5} chars | {a['source'][:22]:22} | {a['title'][:55]}", flush=True)
    with open(PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("\nper source [ok, failed]:")
    for src, (ok, bad) in sorted(summary.items()):
        print(f"  {src:28} {ok} ok, {bad} failed")


if __name__ == "__main__":
    main()
