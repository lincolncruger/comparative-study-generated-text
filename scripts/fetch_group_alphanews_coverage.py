#!/usr/bin/env python3
"""Fetch Alpha News Stream (alphanewsstream.com) articles for Data
Visualization 2's 30 GROUPS tickers, per-observation (not per-ticker --
a broad per-ticker date-range call only returns the most recent ~100
articles in the range, not ones spread across the whole window, so each
observation needs its own narrow-window request).

Archive coverage starts around January 2017 (confirmed empirically:
Dec 15 2016 returns zero articles, Jan 15 2017 doesn't) -- observations
before that are skipped entirely rather than written with an empty
sources list, matching how WSJ/DJNW/Massive-Benzinga already handle
gaps in this project.

Auth: X-Api-Key header (NOT a query param, NOT apiKey=). Response
articles only carry a short "summary" field, not a full body -- there is
no separate full-text endpoint in this API, unlike Benzinga.

Run:
    python3 scripts/fetch_group_alphanews_coverage.py
"""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import timedelta

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OBS_PATH = os.path.join(ROOT, "group_observations.csv")
OUT_PATH = os.path.join(ROOT, "wsj_extracted", "alphanews_consolidated.json")
API_URL = "https://api.alphanewsstream.com/v1/news"
ARCHIVE_START = pd.Timestamp("2017-01-01")


def load_api_key():
    value = os.environ.get("ALPHANEWS_STREAM_API_KEY")
    if value:
        return value.strip()
    env_path = os.path.join(ROOT, ".env")
    for line in open(env_path).read().splitlines():
        name, sep, val = line.partition("=")
        if sep and name.strip() == "ALPHANEWS_STREAM_API_KEY":
            return val.strip()
    raise RuntimeError("ALPHANEWS_STREAM_API_KEY is not configured")


def fetch(ticker, start_date, end_date, api_key):
    params = {
        "symbol": ticker,
        "start_date": start_date,
        "end_date": end_date,
        "count": 100,
        "summary": "yes",
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"X-Api-Key": api_key})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("status") != "Success":
        raise RuntimeError(f"Request failed for {ticker}: {payload}")
    return payload.get("articles") or []


def relevance(article, ticker):
    """Fewer co-tagged symbols = more dedicated coverage of this ticker,
    not a broad multi-company roundup mention."""
    symbols = article.get("tags", {}).get("symbols", [])
    mentions_ticker = any(s.endswith(f":{ticker}") for s in symbols)
    if not mentions_ticker:
        return -1
    return 100 - len(symbols)


def main():
    api_key = load_api_key()
    obs = pd.read_csv(OBS_PATH, parse_dates=["earnings_date"])
    qualifying = obs[obs["earnings_date"] >= ARCHIVE_START].sort_values(["ticker", "earnings_date"])
    print(f"{len(qualifying)} qualifying observations (>= {ARCHIVE_START.date()})", flush=True)

    result = json.load(open(OUT_PATH)) if os.path.exists(OUT_PATH) else {}

    for _, row in qualifying.iterrows():
        ticker = row["ticker"]
        note_key = f"{ticker}_{row['fiscal_yearquarter']}"
        if note_key in result:
            continue
        edate = pd.Timestamp(row["earnings_date"]).normalize()
        wstart = (edate - timedelta(days=1)).strftime("%Y-%m-%d")
        wend = (edate + timedelta(days=3)).strftime("%Y-%m-%d")
        try:
            articles = fetch(ticker, wstart, wend, api_key)
        except Exception as exc:
            print(f"{note_key}: FETCH ERROR {exc}", flush=True)
            time.sleep(3)
            continue

        deduped = []
        seen = set()
        for a in articles:
            # Dedup by id AND by (headline, date) -- the same wire story
            # is often syndicated to multiple feeds under this service
            # (e.g. "MarketWatch.com - Top Stories" vs "MarketWatch.com -
            # GOOG") with different ids but identical headline/date/body.
            key = a.get("id"), (a.get("headline"), a.get("date"))
            dedup_key = key[1]
            if dedup_key in seen:
                continue
            deduped.append(a)
            seen.add(dedup_key)

        scored = [(a, relevance(a, ticker)) for a in deduped]
        scored = [(a, s) for a, s in scored if s >= 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        selected = [a for a, _ in scored[:3]]

        result[note_key] = {
            "ticker": ticker,
            "company_name": row["company_name"],
            "fiscal_yearquarter": row["fiscal_yearquarter"],
            "earnings_date": row["earnings_date"].strftime("%Y-%m-%d"),
            "ret_1day_pct": row["ret_1day_pct"],
            "ret_2day_pct": row["ret_2day_pct"],
            "ret_3day_pct": row["ret_3day_pct"],
            "ret_5day_pct": row["ret_5day_pct"],
            "articles": [
                {
                    "headline": a.get("headline"),
                    "date": a.get("date"),
                    "source": a.get("source"),
                    "url": a.get("url"),
                    "id": a.get("id"),
                    # The API's own field is capitalized "Summary" -- not
                    # "summary" as the docs' example implied -- confirmed by
                    # inspecting a raw response directly; every article
                    # fetched before this fix had summary=None.
                    "summary": a.get("Summary"),
                    "n_tagged_symbols": len(a.get("tags", {}).get("symbols", [])),
                }
                for a in selected
            ],
        }
        print(f"{note_key}: {len(articles)} fetched, {len(selected)} selected", flush=True)
        with open(OUT_PATH, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        time.sleep(0.8)

    print(f"\nWrote {len(result)} observations to {OUT_PATH}")


if __name__ == "__main__":
    main()
