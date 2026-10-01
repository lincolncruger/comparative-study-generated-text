#!/usr/bin/env python3
"""Fetch StockNews API articles for Data Visualization 1 observations dated
April 2019 onward, as input for the "Why Moved 2" prompt.

Per observation: one StockNews call for the window from the day before the
earnings date to three days after, articles sorted oldest first. The API
only returns a short text summary, so each article's page is also fetched
(no API cost) via refetch_stocknews_full_text's best_text(), which tries
both urllib and curl and truncates known boilerplate/related-content
blocks that some publishers (Zacks in particular) append after -- or
instead of -- the real article.

Run:
    python3 scripts/fetch_stocknews_coverage.py [n_observations | all]
Resumable: observations already in the output file are skipped, and
progress is saved after every observation.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import timedelta
from email.utils import parsedate_to_datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refetch_stocknews_full_text import best_text  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OBS_PATH = os.path.join(ROOT, "data", "earnings_241.json")
OUT_PATH = os.path.join(ROOT, "wsj_extracted", "stocknews_consolidated.json")
API_URL = "https://stocknewsapi.com/api/v1"
WINDOW_START = pd.Timestamp("2019-04-01")
SEED = 20261001
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def load_api_key():
    for line in open(os.path.join(ROOT, ".env")).read().splitlines():
        name, sep, val = line.partition("=")
        if sep and name.strip() == "STOCKNEWS_API_KEY":
            return val.strip()
    raise RuntimeError("STOCKNEWS_API_KEY is not configured")


def fetch_articles(ticker, start, end, api_key):
    params = {
        "tickers": ticker,
        "date": f"{start:%m%d%Y}-{end:%m%d%Y}",
        "items": 100,
        "page": 1,
        "token": api_key,
    }
    request = urllib.request.Request(API_URL + "?" + urllib.parse.urlencode(params), headers=UA)
    last_exc = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response).get("data") or []
        except Exception as exc:  # transient DNS/network hiccups -- retry rather than crash the batch
            last_exc = exc
            time.sleep(5 * (attempt + 1))
    raise last_exc


def main():
    api_key = load_api_key()
    df = pd.DataFrame(json.load(open(OBS_PATH)))
    df["earnings_date"] = pd.to_datetime(df["earnings_date"])
    eligible = df[df["earnings_date"] >= WINDOW_START].sort_values(["ticker", "earnings_date"])

    if len(sys.argv) > 1 and sys.argv[1] != "all":
        eligible = eligible.sample(n=int(sys.argv[1]), random_state=SEED).sort_values(["ticker", "earnings_date"])

    result = json.load(open(OUT_PATH)) if os.path.exists(OUT_PATH) else {}
    failed = []
    for _, row in eligible.iterrows():
        note_key = f"{row['ticker']}_{row['fiscal_yearquarter']}"
        if note_key in result:
            continue
        try:
            edate = row["earnings_date"].normalize()
            raw = fetch_articles(row["ticker"], edate - timedelta(days=1), edate + timedelta(days=3), api_key)
            raw.sort(key=lambda a: parsedate_to_datetime(a["date"]))

            articles = []
            for a in raw:
                articles.append({
                    "title": a.get("title"),
                    "published_date": parsedate_to_datetime(a["date"]).isoformat(),
                    "source": a.get("source_name"),
                    "type": a.get("type"),
                    "url": a.get("news_url"),
                    "tickers": a.get("tickers"),
                    "api_summary": a.get("text"),
                    "full_text": best_text(a["news_url"]) if a.get("type") == "Article" else None,
                })

            result[note_key] = {
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "fiscal_yearquarter": row["fiscal_yearquarter"],
                "earnings_date": edate.strftime("%Y-%m-%d"),
                "ret_2day_pct": round(row["ret_2day"] * 100, 2),
                "articles": articles,
            }
            with_text = sum(1 for a in articles if a["full_text"])
            print(f"{note_key}: {len(articles)} articles, {with_text} with full text", flush=True)
            with open(OUT_PATH, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            # A single observation's transient network failure (DNS blip,
            # timeout) shouldn't kill an hour-long batch -- log it and move
            # on; it's still missing from `result` so a resumed run retries it.
            failed.append(note_key)
            print(f"{note_key}: SKIPPED after error: {exc}", flush=True)
        time.sleep(0.3)

    print(f"Wrote {len(result)} observations to {OUT_PATH}")
    if failed:
        print(f"Failed (retry by rerunning, these are not in the output yet): {failed}")


if __name__ == "__main__":
    main()
