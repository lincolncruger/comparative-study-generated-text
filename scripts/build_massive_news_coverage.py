#!/usr/bin/env python3
"""Fetch native Massive news and cache Data Visualization 1 coverage."""

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "earnings_241.json"
OUTPUT_PATH = ROOT / "data" / "massive_news_coverage.json"
API_URL = "https://api.massive.com/v2/reference/news"


def api_key():
    value = os.environ.get("MASSIVE_NEWS_API_KEY")
    if value:
        return value.strip()
    for line in (ROOT / ".env").read_text().splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "MASSIVE_NEWS_API_KEY":
            return value.strip().strip('"').strip("'")
    raise RuntimeError("MASSIVE_NEWS_API_KEY is not configured")


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def fetch(ticker, start, end, key):
    params = {
        "ticker": ticker,
        "published_utc.gte": start.strftime("%Y-%m-%d"),
        "published_utc.lte": end.strftime("%Y-%m-%d"),
        "limit": 1000,
        "sort": "published_utc",
        "order": "asc",
        "apiKey": key,
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    results = []
    while url:
        for attempt in range(8):
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    payload = json.load(response)
                break
            except urllib.error.HTTPError as exc:
                if exc.code != 429 or attempt == 7:
                    raise
                delay = int(exc.headers.get("Retry-After") or 13)
                print(f"{ticker}: rate limited; retrying in {delay}s", flush=True)
                time.sleep(delay)
        if payload.get("status") not in {"OK", "DELAYED"}:
            raise RuntimeError(f"Massive request failed for {ticker}: {payload}")
        results.extend(payload.get("results") or [])
        url = payload.get("next_url")
        if url and "apiKey=" not in url:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"apiKey": key})
    return results


def published(article):
    return pd.to_datetime(article.get("published_utc"), utc=True).tz_convert(None).normalize()


def source(article):
    publisher = article.get("publisher") or {}
    return {
        "title": clean(article.get("title")),
        "published_date": published(article).strftime("%Y-%m-%d"),
        "url": article.get("article_url"),
        "publisher": publisher.get("name"),
        "massive_id": article.get("id"),
    }


def build_entry(articles, event_date, observed_return):
    window = [a for a in articles if event_date - timedelta(days=1) <= published(a) <= event_date + timedelta(days=3)]
    if not window:
        return None
    window.sort(key=lambda a: a.get("published_utc", ""))
    descriptions = []
    for article in window:
        text = clean(article.get("description"))
        if text and text not in descriptions:
            descriptions.append(text)
    if descriptions:
        evidence = " ".join(descriptions)
        summary = evidence
        if len(evidence) > 2200:
            summary = evidence[:2200].rsplit(" ", 1)[0]
            summary += "."
    else:
        titles = [clean(a.get("title")) for a in window if clean(a.get("title"))]
        summary = "Massive indexed the following coverage around the earnings event: " + "; ".join(titles)

    combined = " ".join(clean(a.get("title")) + " " + clean(a.get("description")) for a in window)
    movement = "rose" if observed_return >= 0 else "fell"
    magnitude = abs(observed_return) * 100
    causal = re.search(r"(?:shares?|stock).{0,100}(?:after|following|because|as|on).{0,240}", combined, re.I)
    if causal:
        why = clean(causal.group(0))
        why = f"The stock {movement} {magnitude:.1f}% over the two-day earnings window. Native Massive coverage linked the reaction to this reported development: {why}."
    else:
        why = (
            f"The stock {movement} {magnitude:.1f}% over the two-day earnings window. "
            "The native Massive articles supplied the surrounding results and outlook context, but did not explicitly attribute the move to one confirmed first-order driver."
        )
    return {"summary_analysis": summary, "why_moved": why, "sources": [source(a) for a in window]}


def main():
    frame = pd.read_json(DATA_PATH)
    frame["earnings_date"] = pd.to_datetime(frame["earnings_date"])
    key = api_key()
    output = json.loads(OUTPUT_PATH.read_text()) if OUTPUT_PATH.exists() else {}
    for ticker in sorted(frame["ticker"].dropna().unique()):
        rows = frame[frame["ticker"].eq(ticker)].sort_values("earnings_date")
        ticker_keys = {f"{ticker}_{quarter}" for quarter in rows["fiscal_yearquarter"]}
        if ticker_keys and ticker_keys.issubset(output):
            print(f"{ticker}: already cached", flush=True)
            continue
        articles = fetch(ticker, rows["earnings_date"].min() - timedelta(days=2), rows["earnings_date"].max() + timedelta(days=3), key)
        covered = 0
        for _, row in rows.iterrows():
            entry = build_entry(articles, row["earnings_date"].normalize(), float(row.get("ret_2day", 0.0)))
            if entry:
                output[f"{ticker}_{row['fiscal_yearquarter']}"] = entry
                covered += 1
        OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
        print(f"{ticker}: {covered}/{len(rows)} observations, {len(articles)} native Massive articles", flush=True)
    print(f"Wrote {len(output)} observations to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
