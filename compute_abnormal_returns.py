"""
compute_abnormal_returns.py
----------------------------
Precomputes, per earnings observation, TWO standard event-study ways of
turning "stock return minus market return" into a z-score that's
comparable across tickers of very different normal volatility -- see the
conversation this came out of for the reasoning. Writes two static JSON
files the dashboard just reads (same "precompute once, dashboard reads a
static file" pattern as fetch_price_history.py / build_group_context.py,
rather than running this live on every Streamlit rerun):

    data/abnormal_returns.json        -- keyed "TICKER_fiscalyearquarter",
                                          for the original 241-observation
                                          dataset (earnings_241.json).
    data/group_abnormal_returns.json  -- same shape, for the Data
                                          Visualization 2 group tickers
                                          (Data - Returns/earnings_returns_clean.csv).

Each entry: {"market_model": {...} | null, "market_adjusted": {...} | null}.
Both use the same trailing estimation window -- (earnings_date - 300 days)
to (earnings_date - 46 days), ending well before the event so neither
estimate is contaminated by pre-earnings drift or the reaction itself --
and the same 60-observation minimum, so they're directly comparable to
each other, not just internally consistent.

  "market_model" (beta-adjusted center): estimate beta/alpha via OLS of the
    stock's daily returns on the S&P's over the estimation window; expected
    2-day return = 2*alpha + beta * (S&P's actual 2-day return around the
    event); abnormal_return = actual - expected; standardize by the std
    dev of overlapping 2-day OLS-residual sums from the same window. Beta
    correction happens in the numerator (the center).

  "market_adjusted" (beta=1, correction via scale instead): historical
    excess return = stock's 2-day return minus the S&P's 2-day return, for
    every overlapping 2-day window in the estimation period; standardize
    the event's own (stock - S&P) 2-day excess return by the std dev of
    that historical excess-return series. No beta estimation at all -- a
    high-beta stock's larger normal swings show up as a wider historical
    excess-return distribution instead of being subtracted out up front.
    This is the simpler, more standard of the two (Brown & Warner's
    "market-adjusted return" method vs. their "market model" method).

Run (no arguments -- processes both datasets in one pass):
    python3 compute_abnormal_returns.py
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

ESTIMATION_WINDOW_DAYS = 300
ESTIMATION_WINDOW_END_BUFFER_DAYS = 46
MIN_ESTIMATION_OBS = 60


def sp_actual_2day_return(sp_close_sorted, earnings_date):
    """S&P % change from the first trading day on/after earnings_date to
    two trading days later -- same definition as app.py's sp_return_2day."""
    on_or_after = sp_close_sorted[sp_close_sorted["date"] >= earnings_date]
    if on_or_after.empty:
        return None
    start_pos = on_or_after.index[0]
    end_pos = start_pos + 2
    if end_pos >= len(sp_close_sorted):
        return None
    start_price = sp_close_sorted.iloc[start_pos]["close"]
    end_price = sp_close_sorted.iloc[end_pos]["close"]
    return (end_price / start_price - 1) * 100


def build_close_series(series_rows):
    df = pd.DataFrame(series_rows)
    if df.empty:
        return df.assign(date=[])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def build_daily_returns(close_df):
    df = close_df.copy()
    df["ret"] = df["close"].pct_change() if not df.empty else []
    return df


def rolling_2day_returns(close_df):
    """One row per (date, ret2) where ret2 is the % return from that
    trading day's close to the close two trading days later -- same
    start/end convention as sp_actual_2day_return, just computed for every
    position instead of one event date. Keyed by the END date so it can be
    matched between stock and S&P series on trading days they share."""
    if len(close_df) < 3:
        return pd.DataFrame({"date": [], "ret2": []})
    close = close_df["close"].to_numpy()
    dates = close_df["date"].to_numpy()
    ret2 = close[2:] / close[:-2] - 1
    return pd.DataFrame({"date": dates[2:], "ret2": ret2})


def estimation_window(earnings_date):
    window_end = earnings_date - pd.Timedelta(days=ESTIMATION_WINDOW_END_BUFFER_DAYS)
    window_start = earnings_date - pd.Timedelta(days=ESTIMATION_WINDOW_DAYS)
    return window_start, window_end


def compute_market_model(stock_daily, sp_daily, earnings_date, actual_2day_pct, sp_2day_actual):
    if sp_2day_actual is None:
        return None
    window_start, window_end = estimation_window(earnings_date)

    s = stock_daily[(stock_daily["date"] >= window_start) & (stock_daily["date"] <= window_end)]
    m = sp_daily[(sp_daily["date"] >= window_start) & (sp_daily["date"] <= window_end)]
    merged = s.merge(m, on="date", suffixes=("_stock", "_sp")).dropna()
    if len(merged) < MIN_ESTIMATION_OBS:
        return None

    x = merged["ret_sp"].to_numpy()
    y = merged["ret_stock"].to_numpy()
    beta, alpha = np.polyfit(x, y, 1)

    resid = y - (alpha + beta * x)
    resid_2day = resid[:-1] + resid[1:]  # overlapping consecutive-day pairs
    if len(resid_2day) < 2:
        return None
    sigma_2day_pct = float(np.std(resid_2day, ddof=1)) * 100
    if sigma_2day_pct == 0:
        return None

    expected_2day_pct = 2 * alpha * 100 + beta * sp_2day_actual
    abnormal_pct = actual_2day_pct - expected_2day_pct
    z_score = abnormal_pct / sigma_2day_pct

    return {
        "beta": round(float(beta), 3),
        "abnormal_return_pct": round(abnormal_pct, 3),
        "sigma_pct": round(sigma_2day_pct, 3),
        "z_score": round(z_score, 3),
        "n_obs": int(len(merged)),
    }


def compute_market_adjusted(stock_r2, sp_r2, earnings_date, actual_2day_pct, sp_2day_actual):
    if sp_2day_actual is None:
        return None
    window_start, window_end = estimation_window(earnings_date)

    s = stock_r2[(stock_r2["date"] >= window_start) & (stock_r2["date"] <= window_end)]
    m = sp_r2[(sp_r2["date"] >= window_start) & (sp_r2["date"] <= window_end)]
    merged = s.merge(m, on="date", suffixes=("_stock", "_sp")).dropna()
    if len(merged) < MIN_ESTIMATION_OBS:
        return None

    excess_hist_pct = (merged["ret2_stock"] - merged["ret2_sp"]).to_numpy() * 100
    sigma_pct = float(np.std(excess_hist_pct, ddof=1))
    if sigma_pct == 0:
        return None

    excess_pct = actual_2day_pct - sp_2day_actual
    z_score = excess_pct / sigma_pct

    return {
        "excess_return_pct": round(excess_pct, 3),
        "sigma_pct": round(sigma_pct, 3),
        "z_score": round(z_score, 3),
        "n_obs": int(len(merged)),
    }


def process_dataset(rows, ticker_col, quarter_col, date_col, ret2day_col, price_history, out_path):
    if price_history is None:
        print(f"  no price history available -- skipping {out_path}")
        return

    sp_close = build_close_series(price_history["sp500"])
    sp_daily = build_daily_returns(sp_close)
    sp_r2 = rolling_2day_returns(sp_close)

    result = {}
    both_skipped = 0
    daily_cache = {}
    r2_cache = {}

    for row in rows:
        ticker = row[ticker_col]
        if ticker not in price_history["tickers"]:
            both_skipped += 1
            continue
        if ticker not in daily_cache:
            stock_close = build_close_series(price_history["tickers"][ticker]["series"])
            daily_cache[ticker] = build_daily_returns(stock_close)
            r2_cache[ticker] = rolling_2day_returns(stock_close)
        stock_daily = daily_cache[ticker]
        stock_r2 = r2_cache[ticker]
        if stock_daily.empty:
            both_skipped += 1
            continue

        earnings_date = pd.to_datetime(row[date_col])
        # Both source datasets store ret_2day as a fraction (e.g. 0.0432 for
        # +4.32%), confirmed against how app.py already displays it
        # elsewhere (row["ret_2day"] * 100) -- no unit-guessing here.
        actual_2day_pct = float(row[ret2day_col]) * 100
        note_key = f"{ticker}_{row[quarter_col]}"
        sp_2day_actual = sp_actual_2day_return(sp_close, earnings_date)

        market_model = compute_market_model(stock_daily, sp_daily, earnings_date, actual_2day_pct, sp_2day_actual)
        market_adjusted = compute_market_adjusted(stock_r2, sp_r2, earnings_date, actual_2day_pct, sp_2day_actual)
        if market_model is None and market_adjusted is None:
            both_skipped += 1
            continue
        result[note_key] = {"market_model": market_model, "market_adjusted": market_adjusted}

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  {len(result)} computed, {both_skipped} skipped (insufficient data for both) -> {out_path}")


def main():
    print("=== Original 241-observation dataset ===")
    earnings_path = os.path.join(HERE, "data", "earnings_241.json")
    price_history_path = os.path.join(HERE, "data", "price_history.json")
    out_path = os.path.join(HERE, "data", "abnormal_returns.json")

    earnings_rows = json.load(open(earnings_path))
    price_history = json.load(open(price_history_path)) if os.path.exists(price_history_path) else None
    process_dataset(earnings_rows, "ticker", "fiscal_yearquarter", "earnings_date", "ret_2day",
                     price_history, out_path)

    print("\n=== Data Visualization 2 group dataset ===")
    returns_path = os.path.join(HERE, "Data - Returns", "earnings_returns_clean.csv")
    group_price_history_path = os.path.join(HERE, "data", "group_price_history.json")
    group_out_path = os.path.join(HERE, "data", "group_abnormal_returns.json")

    GROUPS_TICKERS = [
        "NVDA", "AAPL", "GOOGL", "MSFT", "AMZN", "AVGO", "FB", "TSLA", "LLY", "WMT",
        "CAT", "GE", "PG", "NFLX", "HD", "PANW", "PM", "TXN", "KLAC", "AMAT",
        "TJX", "NEM", "ISRG", "LMT", "SBUX", "CVS", "LOW", "ADBE", "MAR", "F",
    ]
    df = pd.read_csv(returns_path, parse_dates=["earningsdate"])
    df = df[df["ticker"].isin(GROUPS_TICKERS)]
    df = df.rename(columns={"earningsdate": "earnings_date", "yq": "fiscal_yearquarter"})
    group_rows = df.to_dict("records")
    group_price_history = json.load(open(group_price_history_path)) if os.path.exists(group_price_history_path) else None
    process_dataset(group_rows, "ticker", "fiscal_yearquarter", "earnings_date", "ret_2day",
                     group_price_history, group_out_path)


if __name__ == "__main__":
    main()
