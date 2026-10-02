"""
compute_group456_abnormal_returns.py
-------------------------------------
Same event-study methodology as ../compute_abnormal_returns.py (beta-adjusted
"market model" + "market-adjusted" z-scores, same 300-day estimation window
ending 46 days before earnings, same 60-observation minimum) -- just applied
to the three ticker sets introduced after that script was written: Data
Visualization 5/6/7's GROUP4_GROUPS/GROUP5_GROUPS/GROUP6_GROUPS (named for
when they were built, before a later renumbering shifted them from sections
4/5/6 to 5/6/7). These tickers were never run through the original script,
so their dashboard pages showed "n/a" for excess/abnormal return.

Writes:
    data/group4_abnormal_returns.json  -- Data Visualization 5's 20 tickers
    data/group5_abnormal_returns.json  -- Data Visualization 6's 20 tickers
    data/group6_abnormal_returns.json  -- Data Visualization 7's 24 tickers

Run (no arguments):
    python3 scripts/compute_group456_abnormal_returns.py
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from compute_abnormal_returns import process_dataset  # noqa: E402

GROUP4_GROUPS = {
    "Small & Mid Cap": ["MTW", "SFIX", "PCTY", "MGNI", "ASO", "NGL", "REZI", "CENTA", "BSM", "METC"],
    "Large Cap": ["BA", "JNJ", "PH", "MRVL", "FTNT", "TMUS", "UBER", "VZ", "MO", "MCD"],
}
GROUP5_GROUPS = {
    "Small & Mid Cap": ["CYH", "MATW", "INDI", "GRC", "APPN", "AXTI", "RYTM", "ALGM", "WLK", "PCVX"],
    "Large Cap": ["SYK", "MPC", "SPGI", "NEE", "MRK", "KO", "LRCX", "COST", "CSCO", "XOM"],
}
GROUP6_GROUPS = {
    "Small & Mid Cap": ["NABL", "DSGN", "PUBM", "ABEO", "LFST", "CRAI", "GOGO", "RCUS", "GDYN", "KURA"],
    "Large Cap": [
        "DELL", "QCOM", "PSX", "SNOW", "APP", "ADI", "PFE", "PEP", "NET", "WDC",
        "IBM", "AMD", "DE", "CRWD",
    ],
}

WINDOW_START = pd.Timestamp("2021-01-01")
WINDOW_END = pd.Timestamp("2023-12-31")
RETURNS_PATH = os.path.join(ROOT, "Data - Returns", "earnings_returns_clean.csv")


def rows_for(groups, out_name):
    all_tickers = [t for tickers in groups.values() for t in tickers]
    df = pd.read_csv(RETURNS_PATH, parse_dates=["earningsdate"])
    df = df[
        (df["ticker"].isin(all_tickers))
        & (df["earningsdate"] >= WINDOW_START)
        & (df["earningsdate"] <= WINDOW_END)
    ]
    df = df.rename(columns={"earningsdate": "earnings_date", "yq": "fiscal_yearquarter"})
    return df.to_dict("records")


def main():
    jobs = [
        ("Data Visualization 5 (group4)", GROUP4_GROUPS, "group4_price_history.json", "group4_abnormal_returns.json"),
        ("Data Visualization 6 (group5)", GROUP5_GROUPS, "group5_price_history.json", "group5_abnormal_returns.json"),
        ("Data Visualization 7 (group6)", GROUP6_GROUPS, "group6_price_history.json", "group6_abnormal_returns.json"),
    ]
    for label, groups, price_history_name, out_name in jobs:
        print(f"=== {label} ===")
        price_history_path = os.path.join(ROOT, "data", price_history_name)
        out_path = os.path.join(ROOT, "data", out_name)
        price_history = json.load(open(price_history_path)) if os.path.exists(price_history_path) else None
        rows = rows_for(groups, out_name)
        process_dataset(rows, "ticker", "fiscal_yearquarter", "earnings_date", "ret_2day", price_history, out_path)


if __name__ == "__main__":
    main()
