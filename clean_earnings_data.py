"""
Clean and reorganize the raw earnings-returns panels in Data/.

Raw inputs (untouched):
  - Data/earnings returns.csv        (gross returns, i.e. 1 + r; has a stray
                                       pivot table stuck in trailing columns)
  - Data/CUPIP_earnings returns.csv  (net returns, i.e. r)
  - Data/gvkey_cik_lookup.csv        (gvkey/CUSIP/ticker -> CIK lookup)

What this does, per returns file:
  1. Drops the leftover pivot-table columns from earnings returns.csv
     (columns past the real 12 data fields are a stray Year/Count/%% and
     Unique-Firms/Count summary table someone had pasted next to the data
     in the original spreadsheet).
  2. Parses `earningsdate` (Stata-style "05nov2014") into a real ISO date.
  3. Normalizes returns to net-return convention (r, not 1+r) so the two
     files are directly comparable. earnings returns.csv gets 1 subtracted
     from each ret_* column; a `return_convention` note records this.
  4. Drops exact duplicate rows, and duplicate (gvkey, earningsdate) pairs
     (keeping the first occurrence) since that pair should uniquely
     identify a company-quarter earnings event.
  5. Sorts alphabetically by ticker (case-insensitive), then by date within
     each ticker. Rows with a blank ticker sort to the end.
  6. Writes a cleaned CSV alongside the original, plus a short text report.

Run:
    python3 clean_earnings_data.py
"""
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent / "Data"

REPORT_LINES = []


def log(line=""):
    print(line)
    REPORT_LINES.append(line)


def parse_stata_date(series):
    return pd.to_datetime(series, format="%d%b%Y", errors="coerce")


def clean_plain(path_in: Path) -> pd.DataFrame:
    cols = ["gvkey", "CUSIP", "earningsdate", "year", "permno", "ticker",
            "ret_1day", "ret_1daypost", "ret_5day", "ret_3day", "ret_2day", "yq"]
    df = pd.read_csv(path_in, header=0, usecols=range(len(cols)), names=cols, skiprows=1)
    original_rows = len(df)

    # Only ret_1day/ret_1daypost are stored as gross returns (1+r) in this
    # file; ret_5day/ret_3day/ret_2day are already net returns, matching
    # CUPIP's convention directly (verified by joining the two files on
    # gvkey+earningsdate: ret_5day/3day/2day agree with CUPIP with NO
    # adjustment, while ret_1day/1daypost only agree after subtracting 1).
    gross_cols = ["ret_1day", "ret_1daypost"]
    df[gross_cols] = df[gross_cols] - 1.0

    df["earningsdate"] = parse_stata_date(df["earningsdate"])
    df = df.drop(columns=["year"])  # redundant with earningsdate/yq

    before = len(df)
    df = df.drop_duplicates()
    exact_dupes = before - len(df)

    before = len(df)
    df = df.drop_duplicates(subset=["gvkey", "earningsdate"], keep="first")
    key_dupes = before - len(df)

    missing_ticker = df["ticker"].isna().sum()

    df["ticker_sort"] = df["ticker"].str.upper()
    df = df.sort_values(["ticker_sort", "earningsdate"], na_position="last", kind="stable")
    df = df.drop(columns=["ticker_sort"])

    log(f"\n=== earnings returns.csv ===")
    log(f"  rows in / out          : {original_rows} -> {len(df)}")
    log(f"  exact duplicate rows dropped        : {exact_dupes}")
    log(f"  duplicate (gvkey, earningsdate) rows dropped (kept first): {key_dupes}")
    log(f"  rows with blank ticker (kept, sorted last) : {missing_ticker}")
    log(f"  ret_1day/ret_1daypost converted from gross (1+r) to net (r);")
    log(f"  ret_5day/ret_3day/ret_2day were already net, left as-is")

    return df


def clean_cupip(path_in: Path) -> pd.DataFrame:
    df = pd.read_csv(path_in)
    original_rows = len(df)
    df["earningsdate"] = parse_stata_date(df["earningsdate"])
    df["anndats"] = pd.to_datetime(df["anndats"], format="%d%b%Y", errors="coerce")

    before = len(df)
    df = df.drop_duplicates()
    exact_dupes = before - len(df)

    before = len(df)
    df = df.drop_duplicates(subset=["gvkey", "earningsdate"], keep="first")
    key_dupes = before - len(df)

    missing_ticker = df["ticker"].isna().sum()

    df["ticker_sort"] = df["ticker"].str.upper()
    df = df.sort_values(["ticker_sort", "earningsdate"], na_position="last", kind="stable")
    df = df.drop(columns=["ticker_sort"])

    log(f"\n=== CUPIP_earnings returns.csv ===")
    log(f"  rows in / out          : {original_rows} -> {len(df)}")
    log(f"  exact duplicate rows dropped        : {exact_dupes}")
    log(f"  duplicate (gvkey, earningsdate) rows dropped (kept first): {key_dupes}")
    log(f"  rows with blank ticker (kept, sorted last) : {missing_ticker}")
    log(f"  returns already net (r); left as-is")

    return df


def clean_lookup(path_in: Path) -> pd.DataFrame:
    df = pd.read_csv(path_in)
    before = len(df)
    df = df.drop_duplicates()
    dupes = before - len(df)
    df["ticker_sort"] = df["ticker"].str.upper()
    df = df.sort_values("ticker_sort", na_position="last", kind="stable")
    df = df.drop(columns=["ticker_sort"])

    log(f"\n=== gvkey_cik_lookup.csv ===")
    log(f"  rows in / out          : {before} -> {len(df)}")
    log(f"  exact duplicate rows dropped        : {dupes}")

    return df


def main():
    log("Cleaning report")
    log("===============")

    plain = clean_plain(DATA_DIR / "earnings returns.csv")
    plain.to_csv(DATA_DIR / "earnings_returns_clean.csv", index=False, date_format="%Y-%m-%d")

    cupip = clean_cupip(DATA_DIR / "CUPIP_earnings returns.csv")
    cupip.to_csv(DATA_DIR / "CUPIP_earnings_returns_clean.csv", index=False, date_format="%Y-%m-%d")

    lookup = clean_lookup(DATA_DIR / "gvkey_cik_lookup.csv")
    lookup.to_csv(DATA_DIR / "gvkey_cik_lookup_clean.csv", index=False)

    log("\nOutputs written to Data/:")
    log("  earnings_returns_clean.csv")
    log("  CUPIP_earnings_returns_clean.csv")
    log("  gvkey_cik_lookup_clean.csv")
    log("\nOriginal files left untouched.")

    (DATA_DIR / "cleaning_report.txt").write_text("\n".join(REPORT_LINES) + "\n")


if __name__ == "__main__":
    main()
