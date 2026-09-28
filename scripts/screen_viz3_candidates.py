#!/usr/bin/env python3
"""Screen candidate tickers for Data Visualization 3's 3 market-cap bands,
pulling exclusively from our existing CUPIP earnings-returns dataset (no
external reference list) -- market cap itself isn't in that dataset, so
it's the one live lookup this needs.
"""
import json
import random
import sys
import time

import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

GROUPS_TICKERS = [
    "NVDA", "AAPL", "GOOGL", "MSFT", "AMZN", "AVGO", "FB", "TSLA", "LLY", "WMT",
    "CAT", "GE", "PG", "NFLX", "HD", "PANW", "PM", "TXN", "KLAC", "AMAT",
    "TJX", "NEM", "ISRG", "LMT", "SBUX", "CVS", "LOW", "ADBE", "MAR", "F",
]
DATAVIZ1_TICKERS = [
    "AAON", "ABM", "ABSI", "ACCO", "ACMR", "ACVA", "ADMA", "ADT", "AES", "AGCO",
    "AIR", "AKA", "AMC", "AMCX", "AMN", "ANIP", "POWW",
]
EXCLUDED = set(GROUPS_TICKERS) | set(DATAVIZ1_TICKERS)

BANDS = {
    "small_mid": (250e6, 10e9),
    "large": (100e9, 500e9),
    "mega": (500e9, float("inf")),
}
TARGET_MARGIN = 18


def get_mcap(ticker):
    try:
        mc = yf.Ticker(ticker).fast_info.get("marketCap")
        return ticker, mc
    except Exception:
        return ticker, None


def main():
    df = pd.read_csv("Data - Returns/earnings_returns_clean.csv", parse_dates=["earningsdate"])
    sub = df[(df["earningsdate"] >= "2021-01-01") & (df["earningsdate"] <= "2023-12-31")]
    counts = sub.groupby("ticker").size()
    eligible = sorted(set(counts[counts >= 10].index) - EXCLUDED)
    print(f"eligible candidates from our dataset: {len(eligible)}", flush=True)

    random.seed(20260928)
    shuffled = eligible[:]
    random.shuffle(shuffled)

    buckets = {k: [] for k in BANDS}
    checked = 0
    failed = 0

    def bucket_full():
        return all(len(v) >= TARGET_MARGIN for v in buckets.values())

    idx = 0
    with ThreadPoolExecutor(max_workers=20) as ex:
        while idx < len(shuffled) and not bucket_full():
            batch = shuffled[idx: idx + 40]
            idx += 40
            futures = [ex.submit(get_mcap, t) for t in batch]
            for fut in futures:
                try:
                    t, mcap = fut.result(timeout=20)
                except Exception:
                    continue
                checked += 1
                if mcap is None:
                    failed += 1
                    continue
                for band, (lo, hi) in BANDS.items():
                    if lo <= mcap < hi:
                        buckets[band].append((t, mcap))
            print(
                f"progress: checked={checked} failed={failed} "
                f"small_mid={len(buckets['small_mid'])} large={len(buckets['large'])} mega={len(buckets['mega'])}",
                flush=True,
            )

    print(f"FINAL checked: {checked} | failed: {failed}", flush=True)
    for band, items in buckets.items():
        print(band, len(items), flush=True)

    with open("/tmp/viz3_buckets.json", "w") as f:
        json.dump(buckets, f, indent=2)
    print("Wrote /tmp/viz3_buckets.json", flush=True)


if __name__ == "__main__":
    main()
