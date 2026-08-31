# fetch_group_price_history.py
# Same pattern as fetch_price_history.py, but for the "Data Visualization 2"
# market-cap-group tickers (Data - Returns/earnings_returns_clean.csv)
# instead of the original 241-observation dataset. One-time build script,
# writes data/group_price_history.json.

import json
import os

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
RETURNS_PATH = os.path.join(HERE, "Data - Returns", "earnings_returns_clean.csv")
OUT_PATH = os.path.join(HERE, "data", "group_price_history.json")

PAD = pd.DateOffset(months=3)

GROUP_TICKERS = {
    "Group 1": ["NVDA", "AAPL", "GOOGL", "MSFT", "AMZN", "AVGO", "FB", "TSLA", "LLY", "WMT"],
    "Group 2": ["CAT", "GE", "PG", "NFLX", "HD", "PANW", "PM", "TXN", "KLAC", "AMAT"],
    "Group 3": ["TJX", "NEM", "ISRG", "LMT", "SBUX", "CVS", "LOW", "ADBE", "MAR", "F"],
}
ALL_TICKERS = sorted({t for tickers in GROUP_TICKERS.values() for t in tickers})

# Yahoo Finance stopped serving any data at all under the old "FB" symbol
# after Facebook's 2022 rename to Meta -- confirmed empirically (yf.download
# ("FB", ...) returns an empty frame for every date range, including pre-
# rename ones that plainly have real trading history). "META" is the same
# underlying security and Yahoo keeps its full history there, including the
# pre-rename years, so FB's series is fetched under that symbol instead
# while still being stored under the "FB" key (GROUPS/GROUP_COMPANY_NAMES
# elsewhere in the app use "FB", not "META", to avoid double-counting the
# same company under two tickers).
DOWNLOAD_SYMBOL_OVERRIDES = {"FB": "META"}


def fetch_series(symbol, start, end):
    symbol = DOWNLOAD_SYMBOL_OVERRIDES.get(symbol, symbol)
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
    returns = pd.read_csv(RETURNS_PATH, parse_dates=["earningsdate"])
    returns = returns[returns["ticker"].isin(ALL_TICKERS)]
    spans = returns.groupby("ticker")["earningsdate"].agg(["min", "max"])

    overall_start = spans["min"].min() - PAD
    overall_end = spans["max"].max() + PAD

    print(f"Fetching S&P 500 (^GSPC): {overall_start.date()} -> {overall_end.date()}")
    sp500 = fetch_series("^GSPC", overall_start, overall_end)
    print(f"  {len(sp500)} rows")

    result = {"sp500": sp500, "tickers": {}}

    for ticker in ALL_TICKERS:
        if ticker not in spans.index:
            print(f"Skipping {ticker}: no rows in returns data")
            continue
        window_start = spans.loc[ticker, "min"] - PAD
        window_end = spans.loc[ticker, "max"] + PAD
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
