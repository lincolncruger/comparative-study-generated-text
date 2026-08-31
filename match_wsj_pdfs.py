"""
match_wsj_pdfs.py
------------------
Matches extracted WSJ PDFs (from extract_wsj_pdfs.py) to specific
ticker/quarter observations: a PDF matches an observation if its
published_date is the observation's earnings_date OR earnings_date + 1 day
(WSJ sometimes runs the earnings story the next morning), AND the ticker's
company name (or a known alt-name) appears in the PDF's title.

Run:
    python3 match_wsj_pdfs.py wsj_extracted/group1.json group1
"""
import json
import sys

import pandas as pd

ALT_NAMES = {
    "NVDA": ["nvidia"],
    "AAPL": ["apple"],
    "GOOGL": ["google", "alphabet"],
    "MSFT": ["microsoft"],
    "AMZN": ["amazon"],
    "AVGO": ["broadcom"],
    "FB": ["facebook"],
    "META": ["facebook", "meta"],
    "TSLA": ["tesla"],
    "LLY": ["eli lilly", "lilly"],
    "WMT": ["walmart", "wal-mart", "wal mart"],
    "CAT": ["caterpillar"],
    "GE": ["general electric"],
    "PG": ["procter & gamble", "procter and gamble", "p&g"],
    "NFLX": ["netflix"],
    "HD": ["home depot"],
    "PANW": ["palo alto networks"],
    "PM": ["philip morris"],
    "TXN": ["texas instruments"],
    "KLAC": ["kla"],
    "AMAT": ["applied materials"],
    "TJX": ["tjx", "t.j. maxx", "marshalls"],
    "NEM": ["newmont"],
    "ISRG": ["intuitive surgical"],
    "LMT": ["lockheed martin", "lockheed"],
    "SBUX": ["starbucks"],
    "CVS": ["cvs"],
    "LOW": ["lowe's", "lowes"],
    "ADBE": ["adobe"],
    "MAR": ["marriott"],
    "F": ["ford motor", "ford"],
}


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 match_wsj_pdfs.py <extracted.json> <group>")
        sys.exit(1)
    extracted_path = sys.argv[1]
    group = sys.argv[2]

    extracted = json.load(open(extracted_path))
    for r in extracted:
        r["title_lower"] = r.get("title", "").lower()

    returns = pd.read_csv("Data - Returns/earnings_returns_clean.csv", parse_dates=["earningsdate"])
    obs_path = "group_observations.csv"
    obs_df = pd.read_csv(obs_path)
    obs_df = obs_df[obs_df["group"] == group.replace("group", "Group ")]

    matches = {}
    unmatched_pdfs = set(r["filename"] for r in extracted)

    for _, row in obs_df.iterrows():
        ticker = row["ticker"]
        edate = pd.Timestamp(row["earnings_date"])
        note_key = f"{ticker}_{row['fiscal_yearquarter']}"
        alt_names = ALT_NAMES.get(ticker, [ticker.lower()])

        found = []
        for r in extracted:
            if r.get("published_date") is None:
                continue
            pdate = pd.Timestamp(r["published_date"])
            if pdate not in (edate, edate + pd.Timedelta(days=1)):
                continue
            if not any(name in r["title_lower"] for name in alt_names):
                continue
            found.append(r["filename"])
            unmatched_pdfs.discard(r["filename"])

        matches[note_key] = {
            "ticker": ticker,
            "fiscal_yearquarter": row["fiscal_yearquarter"],
            "earnings_date": row["earnings_date"],
            "pdfs": found,
        }

    n_zero = sum(1 for v in matches.values() if len(v["pdfs"]) == 0)
    n_one = sum(1 for v in matches.values() if len(v["pdfs"]) == 1)
    n_two_plus = sum(1 for v in matches.values() if len(v["pdfs"]) >= 2)
    print(f"{len(matches)} observations: {n_zero} with 0 PDFs, {n_one} with 1, {n_two_plus} with 2+")
    print(f"\nUnmatched PDFs ({len(unmatched_pdfs)}):")
    for fn in sorted(unmatched_pdfs):
        print(" ", fn)

    print("\nObservations with 0 matches:")
    for k, v in matches.items():
        if len(v["pdfs"]) == 0:
            print(" ", k, v["earnings_date"])

    print("\nObservations with 2+ matches:")
    for k, v in matches.items():
        if len(v["pdfs"]) >= 2:
            print(" ", k, v["pdfs"])

    out_path = f"wsj_extracted/{group}_matches.json"
    with open(out_path, "w") as f:
        json.dump(matches, f, indent=2, default=str)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
