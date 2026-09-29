#!/usr/bin/env python3
"""Fetch price history for Data Visualization 6's 24 tickers (see
GROUP6_GROUPS in app.py), same pattern as Data Viz 4/5: for each ticker, a
window from (min 2021-2023 earnings date - 3 months) to (max earnings date
+ 3 months), plus one shared S&P 500 series covering the full union of all
tickers' windows. Sequential with a pause between requests -- an earlier
aggressive parallel pass triggered a full IP-level Yahoo Finance rate
limit.
"""
import json
import time

import pandas as pd
import yfinance as yf

TICKERS = [
    "NABL", "DSGN", "PUBM", "ABEO", "LFST", "CRAI", "GOGO", "RCUS", "GDYN", "KURA",
    "DELL", "QCOM", "PSX", "SNOW", "APP", "ADI", "PFE", "PEP", "NET", "WDC",
    "IBM", "AMD", "DE", "CRWD",
]
OUT_PATH = "data/group6_price_history.json"
PAD = pd.DateOffset(months=3)


def series_from_history(hist):
    hist = hist.reset_index()
    date_col = "Date" if "Date" in hist.columns else "Datetime"
    return [
        {"date": pd.Timestamp(row[date_col]).strftime("%Y-%m-%d"), "close": float(row["Close"])}
        for _, row in hist.iterrows()
    ]


def main():
    df = pd.read_csv("Data - Returns/earnings_returns_clean.csv", parse_dates=["earningsdate"])
    sub = df[
        (df["ticker"].isin(TICKERS))
        & (df["earningsdate"] >= "2021-01-01")
        & (df["earningsdate"] <= "2023-12-31")
    ]

    tickers_out = {}
    overall_start = None
    overall_end = None

    for t in TICKERS:
        tsub = sub[sub["ticker"] == t]
        if tsub.empty:
            print(f"{t}: no observations, skipping")
            continue
        win_start = tsub["earningsdate"].min() - PAD
        win_end = tsub["earningsdate"].max() + PAD
        overall_start = win_start if overall_start is None else min(overall_start, win_start)
        overall_end = win_end if overall_end is None else max(overall_end, win_end)

        try:
            hist = yf.Ticker(t).history(start=win_start.strftime("%Y-%m-%d"), end=win_end.strftime("%Y-%m-%d"))
        except Exception as exc:
            print(f"{t}: FETCH ERROR {exc}")
            time.sleep(2)
            continue

        if hist.empty:
            print(f"{t}: EMPTY history")
            time.sleep(1.2)
            continue

        tickers_out[t] = {
            "window_start": win_start.strftime("%Y-%m-%d"),
            "window_end": win_end.strftime("%Y-%m-%d"),
            "series": series_from_history(hist),
        }
        print(f"{t}: {len(tickers_out[t]['series'])} bars, {win_start.date()} to {win_end.date()}")
        time.sleep(1.2)

    print(f"Fetching S&P 500 (^GSPC) for {overall_start.date()} to {overall_end.date()}")
    sp_hist = yf.Ticker("^GSPC").history(
        start=overall_start.strftime("%Y-%m-%d"), end=overall_end.strftime("%Y-%m-%d")
    )
    sp500_series = series_from_history(sp_hist)

    result = {"sp500": sp500_series, "tickers": tickers_out}
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {OUT_PATH}: {len(tickers_out)} tickers, {len(sp500_series)} S&P bars")


if __name__ == "__main__":
    main()
