#!/usr/bin/env python3
"""Fetch current market cap for Data Visualization 5/6/7's ticker sets
(GROUP4_GROUPS/GROUP5_GROUPS/GROUP6_GROUPS in app.py -- named for when
they were built, before a later renumbering moved them from sections
4/5/6 to 5/6/7). These tickers were screened by market-cap band at
selection time but the actual number was never saved for display.

Sequential with a pause between requests -- an earlier aggressive
parallel pass triggered a full IP-level Yahoo Finance rate limit.

Run:
    python3 scripts/fetch_group456_market_caps.py
"""
import json
import time

import yfinance as yf

TICKERS = [
    # Data Viz 5 (group4)
    "MTW", "SFIX", "PCTY", "MGNI", "ASO", "NGL", "REZI", "CENTA", "BSM", "METC",
    "BA", "JNJ", "PH", "MRVL", "FTNT", "TMUS", "UBER", "VZ", "MO", "MCD",
    # Data Viz 6 (group5)
    "CYH", "MATW", "INDI", "GRC", "APPN", "AXTI", "RYTM", "ALGM", "WLK", "PCVX",
    "SYK", "MPC", "SPGI", "NEE", "MRK", "KO", "LRCX", "COST", "CSCO", "XOM",
    # Data Viz 7 (group6)
    "NABL", "DSGN", "PUBM", "ABEO", "LFST", "CRAI", "GOGO", "RCUS", "GDYN", "KURA",
    "DELL", "QCOM", "PSX", "SNOW", "APP", "ADI", "PFE", "PEP", "NET", "WDC",
    "IBM", "AMD", "DE", "CRWD",
]
# De-dupe while preserving order (none expected to repeat across groups, but safe)
TICKERS = list(dict.fromkeys(TICKERS))
OUT_PATH = "data/group456_market_caps.json"


def main():
    result = {}
    for t in TICKERS:
        try:
            mcap = yf.Ticker(t).fast_info.get("marketCap")
        except Exception as exc:
            print(f"{t}: FETCH ERROR {exc}")
            mcap = None
        result[t] = mcap
        print(f"{t}: {mcap}")
        with open(OUT_PATH, "w") as f:
            json.dump(result, f, indent=2)
        time.sleep(1.2)

    missing = [t for t, v in result.items() if v is None]
    print(f"\nWrote {OUT_PATH}: {len(result) - len(missing)}/{len(result)} succeeded")
    if missing:
        print("missing:", missing)


if __name__ == "__main__":
    main()
