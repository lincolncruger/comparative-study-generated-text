#!/usr/bin/env python3
"""Fetch raw Massive/Benzinga evidence for the Data Viz 4/5 pilot.

The generated prose is intentionally kept out of this fetcher: ChatGPT reviews
the cached evidence using the handoff's ``llm_reasoning.py`` prompt rules, and
the dashboard reads the resulting ``viz45_chatgpt_coverage.json`` cache.
"""

import json
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_group_massive_benzinga_coverage import (  # noqa: E402
    COMPANY_TERMS,
    article_date,
    clean_text,
    fetch_ticker,
    load_api_key,
    relevance,
)

COMPANY_TERMS.update({
    "MTW": ("manitowoc",),
    "SFIX": ("stitch fix",),
    "PCTY": ("paylocity",),
    "CYH": ("community health systems",),
    "MATW": ("matthews international", "matthews intl"),
    "INDI": ("indie semiconductor",),
})


RETURNS_PATH = ROOT / "Data - Returns" / "earnings_returns_clean.csv"
OUTPUT_PATH = ROOT / "data" / "viz45_massive_benzinga_evidence.json"
WINDOW_START = pd.Timestamp("2021-01-01")
WINDOW_END = pd.Timestamp("2023-12-31")
SEED = 20260928

PILOT_TICKERS = {
    "Data Visualization 4": ["MTW", "SFIX", "PCTY"],
    "Data Visualization 5": ["CYH", "MATW", "INDI"],
}


def observations(frame, ticker):
    rows = frame[
        frame["ticker"].eq(ticker)
        & frame["earningsdate"].between(WINDOW_START, WINDOW_END)
    ].copy()
    if len(rows) > 10:
        rows = rows.sample(n=10, random_state=SEED)
    return rows.sort_values("earningsdate")


def main():
    api_key = load_api_key()
    frame = pd.read_csv(RETURNS_PATH, parse_dates=["earningsdate"])
    output = {}

    for section, tickers in PILOT_TICKERS.items():
        for ticker in tickers:
            rows = observations(frame, ticker)
            if rows.empty:
                print(f"{section} / {ticker}: no observations", flush=True)
                continue
            articles = fetch_ticker(
                ticker,
                rows["earningsdate"].min() - timedelta(days=2),
                rows["earningsdate"].max() + timedelta(days=4),
                api_key,
            )
            covered = 0
            for _, row in rows.iterrows():
                event_date = row["earningsdate"].normalize()
                window = [
                    article
                    for article in articles
                    if event_date - timedelta(days=1)
                    <= article_date(article)
                    <= event_date + timedelta(days=3)
                ]
                window.sort(
                    key=lambda article: (
                        relevance(article, ticker),
                        article.get("published", ""),
                    ),
                    reverse=True,
                )
                if not window:
                    continue

                key = f"{ticker}_{row['yq']}"
                output[key] = {
                    "section": section,
                    "ticker": ticker,
                    "company_name": row.get("company_name", ticker),
                    "fiscal_yearquarter": row["yq"],
                    "earnings_date": event_date.strftime("%Y-%m-%d"),
                    "ret_2day": float(row["ret_2day"]),
                    "articles": [
                        {
                            "title": clean_text(article.get("title")),
                            "published": article.get("published"),
                            "source": article.get("author") or "Benzinga",
                            "url": article.get("url"),
                            "teaser": clean_text(article.get("teaser")),
                            "body": clean_text(article.get("body")),
                        }
                        for article in window
                    ],
                }
                covered += 1
            print(
                f"{section} / {ticker}: {covered}/{len(rows)} observations, "
                f"{len(articles)} fetched articles",
                flush=True,
            )

    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(output)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
