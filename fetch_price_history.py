# fetch_price_history.py
# One-time build script (not shipped/run by the end user) that pulls daily
# closing prices for each of the 17 tickers plus the S&P 500, padded by one
# quarter (~3 months) before the earliest and after the latest earnings date
# in the dataset for that ticker, and bakes the result into a static JSON
# file the dashboard reads at runtime -- no live network access needed when
# someone else clones and runs the app.

import json
import os

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
EARNINGS_PATH = os.path.join(HERE, "data", "earnings_241.json")
OUT_PATH = os.path.join(HERE, "data", "price_history.json")

PAD_END = pd.DateOffset(months=3)
# Padding before the earliest quarter needs to be wide enough for a beta
# estimation window (~250 trading days, ending ~46 days before the event --
# see compute_abnormal_returns.py) even for that ticker's very first shown
# quarter, not just 3 months.
PAD_START = pd.DateOffset(months=13)


def fetch_series(symbol, start, end):
    df = yf.download(symbol, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)
    if df.empty:
        return []
    close = df["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    return [
        {"date": d.strftime("%Y-%m-%d"), "close": float(v)}
        for d, v in zip(close.index, close.values)
    ]


def main():
    earnings = pd.DataFrame(json.load(open(EARNINGS_PATH)))
    earnings["earnings_date"] = pd.to_datetime(earnings["earnings_date"])
    spans = earnings.groupby("ticker")["earnings_date"].agg(["min", "max"])

    overall_start = (spans["min"].min() - PAD_START)
    overall_end = (spans["max"].max() + PAD_END)

    print(f"Fetching S&P 500 (^GSPC): {overall_start.date()} -> {overall_end.date()}")
    sp500 = fetch_series("^GSPC", overall_start, overall_end)
    print(f"  {len(sp500)} rows")

    result = {"sp500": sp500, "tickers": {}}

    for ticker in spans.index:
        window_start = spans.loc[ticker, "min"] - PAD_START
        window_end = spans.loc[ticker, "max"] + PAD_END
        print(f"Fetching {ticker}: {window_start.date()} -> {window_end.date()}")
        series = fetch_series(ticker, window_start, window_end)
        print(f"  {len(series)} rows")
        result["tickers"][ticker] = {
            "window_start": window_start.strftime("%Y-%m-%d"),
            "window_end": window_end.strftime("%Y-%m-%d"),
            "series": series,
        }

    with open(OUT_PATH, "w") as f:
        json.dump(result, f)
    print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()
