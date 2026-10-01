#!/usr/bin/env python3
"""Cache Massive/Benzinga evidence for Data Viz 2's ChatGPT pilot."""

import json
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_group_massive_benzinga_coverage import (  # noqa: E402
    article_date,
    clean_text,
    fetch_ticker,
    load_api_key,
    relevance,
)


INPUT_PATH = ROOT / "group_observations.csv"
OUTPUT_PATH = ROOT / "data" / "viz2_chatgpt_evidence.json"
PILOT_TICKERS = ("AAPL", "MSFT", "AMZN")


def main():
    api_key = load_api_key()
    frame = pd.read_csv(INPUT_PATH, parse_dates=["earnings_date"])
    output = {}

    for ticker in PILOT_TICKERS:
        observations = frame[frame["ticker"].eq(ticker)].sort_values("earnings_date")
        articles = fetch_ticker(
            ticker,
            observations["earnings_date"].min() - timedelta(days=2),
            observations["earnings_date"].max() + timedelta(days=4),
            api_key,
        )
        covered = 0
        for _, row in observations.iterrows():
            event_date = row["earnings_date"].normalize()
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
            key = f"{ticker}_{row['fiscal_yearquarter']}"
            output[key] = {
                "ticker": ticker,
                "company_name": row["company_name"],
                "fiscal_yearquarter": row["fiscal_yearquarter"],
                "earnings_date": event_date.strftime("%Y-%m-%d"),
                "ret_2day": float(row["ret_2day_pct"]) / 100.0,
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
        print(f"{ticker}: {covered}/{len(observations)} observations from {len(articles)} articles", flush=True)

    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(output)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
