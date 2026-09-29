#!/usr/bin/env python3
"""Screen candidate tickers for Data Visualization 6's market-cap bands,
pulling exclusively from our existing CUPIP earnings-returns dataset (no
external reference list) -- market cap itself isn't in that dataset, so
it's the one live lookup this needs. Excludes every ticker already used
in Data Viz 1 through 5.

Deliberately gentle (sequential, with a pause between requests, resumable
via incremental saves) -- an earlier aggressive parallel pass (20
workers, no delay) triggered a full IP-level Yahoo Finance rate limit
that blocked even single unbatched requests for a while.
"""
import json
import os
import random
import time

import pandas as pd
import yfinance as yf

GROUPS_TICKERS = [
    "NVDA", "AAPL", "GOOGL", "MSFT", "AMZN", "AVGO", "FB", "TSLA", "LLY", "WMT",
    "CAT", "GE", "PG", "NFLX", "HD", "PANW", "PM", "TXN", "KLAC", "AMAT",
    "TJX", "NEM", "ISRG", "LMT", "SBUX", "CVS", "LOW", "ADBE", "MAR", "F",
]
DATAVIZ1_TICKERS = [
    "AAON", "ABM", "ABSI", "ACCO", "ACMR", "ACVA", "ADMA", "ADT", "AES", "AGCO",
    "AIR", "AKA", "AMC", "AMCX", "AMN", "ANIP", "POWW",
]
DATAVIZ4_TICKERS = [
    "MTW", "SFIX", "PCTY", "MGNI", "ASO", "NGL", "REZI", "CENTA", "BSM", "METC",
    "BA", "JNJ", "PH", "MRVL", "FTNT", "TMUS", "UBER", "VZ", "MO", "MCD",
]
DATAVIZ5_TICKERS = [
    "CYH", "MATW", "INDI", "GRC", "APPN", "AXTI", "RYTM", "ALGM", "WLK", "PCVX",
    "SYK", "MPC", "SPGI", "NEE", "MRK", "KO", "LRCX", "COST", "CSCO", "XOM",
]
EXCLUDED = set(GROUPS_TICKERS) | set(DATAVIZ1_TICKERS) | set(DATAVIZ4_TICKERS) | set(DATAVIZ5_TICKERS)

BANDS = {
    "small_mid": (250e6, 10e9),
    "large": (100e9, 1e12),
}
TARGET_MARGIN = 18

BUCKETS_PATH = "/tmp/viz6_buckets.json"
CHECKED_PATH = "/tmp/viz6_checked.json"


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

    random.seed(20260931)
    shuffled = eligible[:]
    random.shuffle(shuffled)

    buckets = json.load(open(BUCKETS_PATH)) if os.path.exists(BUCKETS_PATH) else {k: [] for k in BANDS}
    already_checked = set(json.load(open(CHECKED_PATH))) if os.path.exists(CHECKED_PATH) else set()
    checked = len(already_checked)
    failed = 0

    def bucket_full():
        return all(len(v) >= TARGET_MARGIN for v in buckets.values())

    def save():
        with open(BUCKETS_PATH, "w") as f:
            json.dump(buckets, f, indent=2)
        with open(CHECKED_PATH, "w") as f:
            json.dump(sorted(already_checked), f)

    for t in shuffled:
        if bucket_full():
            break
        if t in already_checked:
            continue
        ticker, mcap = get_mcap(t)
        already_checked.add(t)
        checked += 1
        if mcap is None:
            failed += 1
        else:
            for band, (lo, hi) in BANDS.items():
                if lo <= mcap < hi:
                    buckets[band].append((ticker, mcap))
        if checked % 10 == 0:
            save()
            print(
                f"progress: checked={checked} failed={failed} "
                f"small_mid={len(buckets['small_mid'])} large={len(buckets['large'])}",
                flush=True,
            )
        time.sleep(1.2)

    save()
    print(f"FINAL checked: {checked} | failed: {failed}", flush=True)
    for band, items in buckets.items():
        print(band, len(items), flush=True)
    print(f"Wrote {BUCKETS_PATH}", flush=True)


if __name__ == "__main__":
    main()
