#!/usr/bin/env python3
"""Re-fetch price history for Data Visualization 5/6/7's ticker sets
(GROUP4_GROUPS/GROUP5_GROUPS/GROUP6_GROUPS in app.py -- named for when they
were built, before a later renumbering moved them from sections 4/5/6 to
5/6/7), with a longer BACK-pad than the original fetch.

The original fetch_group{4,5,6}_price_history.py scripts only padded 3
months before each ticker's earliest 2021-2023 earnings date. That's not
enough: compute_abnormal_returns.py's estimation window needs daily data
from (earnings_date - 300 days) to (earnings_date - 46 days), so every
single ticker's FIRST quarter in the window was missing ~208-210 days of
required lookback and showed "n/a" for its abnormal return. This refetch
uses a 370-day back-pad (300 + 46 + ~24 days of slack for holidays/weekends
so the trading-day count comfortably clears the 60-observation minimum)
while keeping the original 3-month forward-pad for the chart's trailing
view after each ticker's last quarter.

Sequential with a pause between requests -- an earlier aggressive parallel
pass triggered a full IP-level Yahoo Finance rate limit.
"""
import json
import time

import pandas as pd
import yfinance as yf

GROUPS = {
    "group4": {
        "tickers": [
            "MTW", "SFIX", "PCTY", "MGNI", "ASO", "NGL", "REZI", "CENTA", "BSM", "METC",
            "BA", "JNJ", "PH", "MRVL", "FTNT", "TMUS", "UBER", "VZ", "MO", "MCD",
        ],
        "out_path": "data/group4_price_history.json",
    },
    "group5": {
        "tickers": [
            "CYH", "MATW", "INDI", "GRC", "APPN", "AXTI", "RYTM", "ALGM", "WLK", "PCVX",
            "SYK", "MPC", "SPGI", "NEE", "MRK", "KO", "LRCX", "COST", "CSCO", "XOM",
        ],
        "out_path": "data/group5_price_history.json",
    },
    "group6": {
        "tickers": [
            "NABL", "DSGN", "PUBM", "ABEO", "LFST", "CRAI", "GOGO", "RCUS", "GDYN", "KURA",
            "DELL", "QCOM", "PSX", "SNOW", "APP", "ADI", "PFE", "PEP", "NET", "WDC",
            "IBM", "AMD", "DE", "CRWD",
        ],
        "out_path": "data/group6_price_history.json",
    },
}

BACK_PAD = pd.Timedelta(days=370)
FORWARD_PAD = pd.DateOffset(months=3)


def series_from_history(hist):
    hist = hist.reset_index()
    date_col = "Date" if "Date" in hist.columns else "Datetime"
    return [
        {"date": pd.Timestamp(row[date_col]).strftime("%Y-%m-%d"), "close": float(row["Close"])}
        for _, row in hist.iterrows()
    ]


def fetch_group(name, tickers, out_path, returns_df):
    sub = returns_df[
        (returns_df["ticker"].isin(tickers))
        & (returns_df["earningsdate"] >= "2021-01-01")
        & (returns_df["earningsdate"] <= "2023-12-31")
    ]

    tickers_out = {}
    overall_start = None
    overall_end = None

    for t in tickers:
        tsub = sub[sub["ticker"] == t]
        if tsub.empty:
            print(f"{name} {t}: no observations, skipping")
            continue
        win_start = tsub["earningsdate"].min() - BACK_PAD
        win_end = tsub["earningsdate"].max() + FORWARD_PAD
        overall_start = win_start if overall_start is None else min(overall_start, win_start)
        overall_end = win_end if overall_end is None else max(overall_end, win_end)

        try:
            hist = yf.Ticker(t).history(start=win_start.strftime("%Y-%m-%d"), end=win_end.strftime("%Y-%m-%d"))
        except Exception as exc:
            print(f"{name} {t}: FETCH ERROR {exc}")
            time.sleep(2)
            continue

        if hist.empty:
            print(f"{name} {t}: EMPTY history")
            time.sleep(1.2)
            continue

        tickers_out[t] = {
            "window_start": win_start.strftime("%Y-%m-%d"),
            "window_end": win_end.strftime("%Y-%m-%d"),
            "series": series_from_history(hist),
        }
        print(f"{name} {t}: {len(tickers_out[t]['series'])} bars, {win_start.date()} to {win_end.date()}", flush=True)
        time.sleep(1.2)

    print(f"{name}: fetching S&P 500 (^GSPC) for {overall_start.date()} to {overall_end.date()}", flush=True)
    sp_hist = yf.Ticker("^GSPC").history(
        start=overall_start.strftime("%Y-%m-%d"), end=overall_end.strftime("%Y-%m-%d")
    )
    sp500_series = series_from_history(sp_hist)

    result = {"sp500": sp500_series, "tickers": tickers_out}
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {out_path}: {len(tickers_out)} tickers, {len(sp500_series)} S&P bars\n", flush=True)


def main():
    returns_df = pd.read_csv("Data - Returns/earnings_returns_clean.csv", parse_dates=["earningsdate"])
    for name, cfg in GROUPS.items():
        fetch_group(name, cfg["tickers"], cfg["out_path"], returns_df)


if __name__ == "__main__":
    main()
