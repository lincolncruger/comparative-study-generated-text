"""
McGill Dashboard -- Earnings Reaction Review
=============================================

For each of 17 tickers, this dashboard shows -- per earnings-report quarter --
two things side by side:

  LEFT  ("Contextualized interpretation"): what was already known/priced-in
        before the report, and the report's own news, built from real
        web-search research with clickable sources ("Verify" buttons).
  RIGHT ("Generated text"): the AI-generated paragraph explaining the stock's
        2-day post-earnings move, from the original research pipeline.

The point of the comparison is to see whether grounding an explanation in
what was genuinely NEW information (vs. already-known/priced-in) changes the
narrative -- the qualitative analogue of how a bank's probability of default
should only move on new information, not on restating old news.

This file is a single Streamlit script, structured top to bottom as:
  1. Imports & file paths
  2. Page theme (CSS)
  3. Data loaders (one JSON file per data layer -- see comments there)
  4. Left-column context-text rendering (two systems: current + legacy)
  5. Charts (full ticker history + per-quarter zoomed "Visualize" chart)
  6. Main page layout -- the part that actually runs top-to-bottom on every
     Streamlit rerun: header, ticker nav, per-quarter loop.

It's meant to be built once and handed off, not repeatedly modified -- see
the section comments below for the reasoning behind non-obvious choices.
"""

import base64
import json
import os
import re
import textwrap
from urllib.parse import quote as url_quote

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

# =============================================================================
# 1. IMPORTS & FILE PATHS
# =============================================================================

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data", "earnings_241.json")
NOTES_PATH = os.path.join(HERE, "data", "my_notes.json")
LOGO_PATH = os.path.join(HERE, "assets", "mcgill_logo.png")
PRICE_HISTORY_PATH = os.path.join(HERE, "data", "price_history.json")
ABNORMAL_RETURNS_PATH = os.path.join(HERE, "data", "abnormal_returns.json")
BULLETS_PATH = os.path.join(HERE, "data", "bullets_241.json")
SOURCES_PATH = os.path.join(HERE, "data", "sources_241.json")
CONTEXT_SUMMARIES_PATH = os.path.join(HERE, "data", "context_summaries_241.json")
WEBSEARCH_LONG_PATH = os.path.join(HERE, "data", "websearch_long_241.json")
COMPANY_INFO_PATH = os.path.join(HERE, "data", "company_info_241.json")
COMPARATIVE_ANSWERS_PATH = os.path.join(HERE, "data", "comparative_answers_241.json")
GROUP_COVERAGE_ACCURACY_PATH = os.path.join(HERE, "data", "group_coverage_accuracy_answers.json")

# "Data Visualization 2" -- three market-cap-banded groups of large/mega-cap
# tickers pulled from the full 5,503-company returns panel (see
# clean_earnings_data.py), NOT part of the original 241-observation pipeline.
# These have real returns + fetched price history (group_price_history.json,
# built by fetch_group_price_history.py). Contextual interpretation text
# exists per-group as it's produced (group_context.json, built by
# build_group_context.py from a "Context Data Visualization 2/Group_N_*.xlsx"
# workbook) -- coverage is partial group-by-group, and there is still no
# AI-generated "final_paragraph" text for these companies (that pipeline only
# ever ran on the 17 tickers above), so this section shows the contextual
# interpretation alone, full-width, rather than the original's left/right
# interpretation-vs-generated-text comparison.
GROUP_RETURNS_PATH = os.path.join(HERE, "Data - Returns", "earnings_returns_clean.csv")
GROUP_PRICE_HISTORY_PATH = os.path.join(HERE, "data", "group_price_history.json")
GROUP_ABNORMAL_RETURNS_PATH = os.path.join(HERE, "data", "group_abnormal_returns.json")
GROUP4_ABNORMAL_RETURNS_PATH = os.path.join(HERE, "data", "group4_abnormal_returns.json")
GROUP5_ABNORMAL_RETURNS_PATH = os.path.join(HERE, "data", "group5_abnormal_returns.json")
GROUP6_ABNORMAL_RETURNS_PATH = os.path.join(HERE, "data", "group6_abnormal_returns.json")
GROUP_CONTEXT_PATH = os.path.join(HERE, "data", "group_context.json")
GROUP_WSJ_COVERAGE_PATH = os.path.join(HERE, "data", "group_wsj_coverage.json")
GROUP_DJNW_COVERAGE_PATH = os.path.join(HERE, "data", "group_djnw_coverage.json")
GROUP_MASSIVE_BENZINGA_COVERAGE_PATH = os.path.join(HERE, "data", "group_massive_benzinga_coverage.json")
GROUP_ALPHANEWS_COVERAGE_PATH = os.path.join(HERE, "data", "group_alphanews_coverage.json")
MASSIVE_BENZINGA_COVERAGE_PATH = os.path.join(HERE, "data", "massive_benzinga_coverage.json")
MASSIVE_NEWS_COVERAGE_PATH = os.path.join(HERE, "data", "massive_news_coverage.json")
STOCKNEWS_COVERAGE_PATH = os.path.join(HERE, "data", "stocknews_coverage.json")
GROUP4_STOCKNEWS_V2_CLAUDE_PATH = os.path.join(HERE, "wsj_extracted", "stocknews_v2_claude.json")
GROUP4_STOCKNEWS_V2_REBUILD_PATH = os.path.join(HERE, "wsj_extracted", "stocknews_v2_rebuild.json")
# Codex's half of the same Data Viz 5 StockNews batch -- written as 3
# separate shard files (24 keys each, covering all 72 of Codex's assigned
# note keys with no overlap between shards or with Claude's 62) rather
# than into the single stocknews_v2_rebuild.json path the handoff
# originally named -- that file is stale leftover from before the
# Claude/Codex key split was finalized (its 19 keys don't match either
# side's current assignment), so it's read too but contributes nothing
# that collides with real coverage.
GROUP4_STOCKNEWS_V2_CODEX_SHARD_PATHS = [
    os.path.join(HERE, "wsj_extracted", f"stocknews_v2_codex_shard_{i}.json") for i in range(3)
]
VIZ45_CHATGPT_COVERAGE_PATH = os.path.join(HERE, "data", "viz45_chatgpt_coverage.json")
VIZ2_CHATGPT_COVERAGE_PATH = os.path.join(HERE, "data", "viz2_chatgpt_coverage.json")
GROUP_PD_CATEGORIES_PATH = os.path.join(HERE, "data", "group_pd_categories.json")
GROUP_FIRST_ORDER_CATEGORIES_PATH = os.path.join(HERE, "data", "group_first_order_categories.json")
# The 11 fixed categories each of the 3 coverage sources (Contextualized
# interpretation / WSJ / DJNW) is independently rated against, per
# observation -- lets a viewer see whether all 3 sources actually surface
# the same relevant topics, or whether one is silently missing something
# the others caught. A category is "positive"/"negative" only when that
# source's own text (plus, for context/WSJ/DJNW respectively, the linked
# SEC filing / PDF / article) actually addresses it; otherwise it's left
# blank -- these are exact key strings used in group_pd_categories.json.
PD_CATEGORIES = [
    "Guidance",
    "Order book / order backlog",
    "Revenue",
    "Product / Users",
    "Profits and profitability",
    "Costs",
    "Debt, leverage and capital raise",
    "Capex",
    "Management",
    "Litigation",
    "Others: eg. Covid, or macro events",
]
# Streamlit's static-file server (enabled via .streamlit/config.toml's
# [server] enableStaticServing = true) only serves files placed under a
# static/ folder next to this script, at the URL path /app/static/<path>.
# A PDF opened via a data: URI in a new tab is silently blocked by Chrome
# (a security restriction on data: URL navigation from link clicks, since
# Chrome 65) -- confirmed empirically, no error, no tab, nothing happens --
# so the PDFs are copied into static/ once (see the shell copy that
# populated this) and linked to as real URLs instead, which have no such
# restriction.
GROUP_WSJ_STATIC_SLUGS = {
    "Group 1": "wsj-group-1",
    "Group 2": "wsj-group-2",
    "Group 3": "wsj-group-3",
}

GROUPS = {
    # GOOG and META intentionally excluded -- GOOGL and FB already cover
    # Alphabet and Meta (both are the same company under a ticker-symbol
    # split; see GROUP_COMPANY_NAMES below), so including both symbols per
    # company would double-count them.
    "Group 1": ["NVDA", "AAPL", "GOOGL", "MSFT", "AMZN", "AVGO", "FB", "TSLA", "LLY", "WMT"],
    "Group 2": ["CAT", "GE", "PG", "NFLX", "HD", "PANW", "PM", "TXN", "KLAC", "AMAT"],
    "Group 3": ["TJX", "NEM", "ISRG", "LMT", "SBUX", "CVS", "LOW", "ADBE", "MAR", "F"],
}
GROUP_MARKET_CAP_LABELS = {
    # Escaped $ -- st.button()'s label is rendered through the same
    # markdown/LaTeX pass as st.markdown, where a pair of unescaped $ signs
    # gets interpreted as inline math (mangling to e.g. "50𝐵–150B" instead
    # of showing literally). See the same issue/fix for $ in body text below.
    "Group 1": ">\\$1T",
    # Upper bound is the highest current market cap in the group (AMAT,
    # ~$383B as of the last check), rounded up to a clean $400B.
    "Group 2": "\\$250B to \\$400B",
    "Group 3": "\\$50B\u2013\\$150B",
}
GROUP_COMPANY_NAMES = {
    "NVDA": "NVIDIA", "AAPL": "Apple", "GOOGL": "Alphabet",
    "MSFT": "Microsoft", "AMZN": "Amazon", "AVGO": "Broadcom", "FB": "Meta Platforms",
    "TSLA": "Tesla", "LLY": "Eli Lilly", "WMT": "Walmart",
    "CAT": "Caterpillar", "GE": "General Electric", "PG": "Procter & Gamble", "NFLX": "Netflix",
    "HD": "Home Depot", "PANW": "Palo Alto Networks", "PM": "Philip Morris International",
    "TXN": "Texas Instruments", "KLAC": "KLA Corporation", "AMAT": "Applied Materials",
    "TJX": "TJX Companies", "NEM": "Newmont", "ISRG": "Intuitive Surgical", "LMT": "Lockheed Martin",
    "SBUX": "Starbucks", "CVS": "CVS Health", "LOW": "Lowe's", "ADBE": "Adobe",
    "MAR": "Marriott International", "F": "Ford Motor Company",
}

# Human-entered ratings comparing the AI-generated text against the grounded
# context, collected in the "Comparative Study" section and displayed
# read-only in "Data Visualization". "Not yet rated" is always index 0 so an
# unanswered question defaults there without needing a special case.
Q1_QUESTION = "Is the generated text true?"
Q1_OPTIONS = ["Not yet rated", "True", "Partially true", "False"]
Q2_QUESTION = "Is the generated text accurate in explaining the stock movement post earnings?"
Q2_OPTIONS = ["Not yet rated", "Accurate", "Partially accurate", "Inaccurate"]

st.set_page_config(page_title="Earnings Reaction Review", layout="wide")

# =============================================================================
# 2. PAGE THEME (CSS)
# =============================================================================
# Same navy/gold palette as the Six Paths Macro Dashboard. Injected once,
# up front, via st.html rather than st.markdown(unsafe_allow_html=True) --
# a blank line inside a <style> block passed through st.markdown gets
# treated as the end of the raw-HTML block by the markdown parser, and
# everything after it gets dumped onto the page as literal text instead of
# being parsed as CSS.
#
# Several class names below aren't just styling -- they're small "widgets"
# built from a checkbox/radio + label pair, styled so the label reads as a
# clickable button and the checked/unchecked state shows or hides a sibling
# element via CSS alone (no JavaScript, no server round-trip):
#   .verify-toggle-wrap / .verify-para-wrap  -- "Verify" source-link buttons
#   div[class*="st-key-viz_"] + .visualize-*  -- the "Visualize" chart toggle
#     (this one targets a real Streamlit element by its container `key`,
#     since the toggle and the Plotly chart it reveals are two separate
#     Streamlit-rendered elements, not raw HTML in the same string -- see
#     the "Visualize" toggle in the main loop below for how it's wired up)
st.html(
    """
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500&display=swap" rel="stylesheet">
    <style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(to top, #050D1F 0%, #0E2040 22%, #1A3A5C 46%, #3A6FA8 64%, #DCE8F5 85%, #F8FAFD 100%) !important;
    }
    [data-testid="stHeader"] {
        background: transparent !important;
    }
    hr.gold-divider {
        border: none;
        border-top: 2px solid #4A90D9;
        margin: 0.3rem 0 1.2rem 0;
    }
    /* Streamlit's st.dialog() title -- uses whichever heading level the
       installed version renders it with, so all 3 are targeted here
       rather than guessing one. */
    [data-testid="stDialog"] h1,
    [data-testid="stDialog"] h2,
    [data-testid="stDialog"] h3 {
        text-align: center;
        width: 100%;
    }
    hr.quarter-divider {
        border: none;
        border-top: 1px solid #4A90D9;
        opacity: 0.35;
        margin: 0.4rem 0 1.1rem 0;
    }
    .right-panel {
        padding-left: 0.5rem;
    }
    .context-heading {
        color: #D8B978;
        font-weight: bold;
        margin-top: 0.9rem;
        margin-bottom: 0.3rem;
    }
    .context-driver-heading {
        color: #D8B978;
        font-weight: bold;
        font-size: 0.92rem;
        padding-left: 1.5rem;
        margin-top: 0.9rem;
        margin-bottom: 0.2rem;
    }
    .context-driver-body {
        padding-left: 1.5rem;
        font-size: 0.88rem;
    }
    .verify-toggle-wrap {
        text-align: center;
        margin: 0.8rem 0;
    }
    .verify-toggle-wrap input[type="checkbox"] {
        display: none;
    }
    .verify-toggle-wrap label {
        cursor: pointer;
        color: #4A90D9;
        border: 1px solid rgba(74,144,217,0.4);
        padding: 3px 14px;
        border-radius: 2px;
        font-size: 0.82rem;
        display: inline-block;
        font-family: 'Cormorant Garamond', serif;
        transition: all 0.2s ease;
    }
    .verify-toggle-wrap label:hover {
        color: #FFD700;
        border-color: #FFD700;
    }
    .verify-content {
        display: none;
        margin-top: 0.6rem;
        text-align: left;
    }
    .verify-toggle-wrap input[type="checkbox"]:checked ~ .verify-content {
        display: block;
    }
    .verify-toggle-wrap input[type="checkbox"]:checked ~ label {
        color: #FFD700;
        border-color: #FFD700;
    }
    .format-body p, .right-panel p, .context-driver-body {
        text-align: justify;
    }
    .format-body {
        text-align: left;
        margin-top: 0.8rem;
    }
    .verify-para-wrap {
        text-align: left;
        margin: 0 0 0.9rem 0;
    }
    .verify-para-wrap input[type="checkbox"] {
        display: none;
    }
    .verify-para-wrap label {
        cursor: pointer;
        color: #4A90D9;
        border: 1px solid rgba(74,144,217,0.4);
        padding: 2px 10px;
        border-radius: 2px;
        font-size: 0.72rem;
        display: inline-block;
        font-family: 'Cormorant Garamond', serif;
        transition: all 0.2s ease;
    }
    .verify-para-wrap label:hover {
        color: #FFD700;
        border-color: #FFD700;
    }
    .verify-para-content {
        display: none;
        margin-top: 0.3rem;
        text-align: left;
    }
    .verify-para-wrap input[type="checkbox"]:checked ~ .verify-para-content {
        display: block;
    }
    .verify-para-wrap input[type="checkbox"]:checked ~ label {
        color: #FFD700;
        border-color: #FFD700;
    }
    .quarter-header {
        font-family: 'Cormorant Garamond', serif;
        font-size: 1.5rem;
        letter-spacing: 0.5px;
        color: #FFD700;
        margin-bottom: 0.3rem;
    }
    div[class*="st-key-viz_"] {
        text-align: center;
        margin-bottom: 0.6rem;
    }
    .visualize-checkbox {
        display: none;
    }
    .visualize-label {
        cursor: pointer;
        color: #4A90D9;
        border: 1px solid rgba(74,144,217,0.4);
        padding: 3px 14px;
        border-radius: 2px;
        font-size: 0.82rem;
        display: inline-block;
        font-family: 'Cormorant Garamond', serif;
        transition: all 0.2s ease;
    }
    .visualize-label:hover {
        color: #FFD700;
        border-color: #FFD700;
    }
    div[class*="st-key-viz_"]:has(.visualize-checkbox:checked) .visualize-label {
        color: #FFD700;
        border-color: #FFD700;
    }
    div[class*="st-key-viz_"] div[data-testid="stPlotlyChart"] {
        display: none;
        margin-top: 0.8rem;
        text-align: left;
    }
    div[class*="st-key-viz_"]:has(.visualize-checkbox:checked) div[data-testid="stPlotlyChart"] {
        display: block;
    }
    div[data-testid="stHorizontalBlock"] button {
        height: 42px !important;
        font-size: 0.7rem !important;
        font-weight: 400 !important;
        letter-spacing: 0.3px !important;
        padding: 0 0.3rem !important;
        background-color: #162B4D !important;
        color: #D6E4F0 !important;
        border: 1px solid #1E3A5F !important;
        border-radius: 0px !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stHorizontalBlock"] button:hover {
        background-color: #1E3A5F !important;
        color: #FFD700 !important;
        border-color: #FFD700 !important;
    }
    div[data-testid="stHorizontalBlock"] button[kind="primary"] {
        background-color: #1A3A5C !important;
        color: #FFD700 !important;
        border: 1px solid #FFD700 !important;
        border-bottom: 3px solid #FFD700 !important;
    }
    </style>
    """
)


# =============================================================================
# 3. DATA LOADERS
# =============================================================================
# Everything the dashboard shows is read from small JSON files in data/,
# each holding one layer of the picture, keyed by "{ticker}_{fiscal_yearquarter}"
# (e.g. "AAON_2017q3") unless noted otherwise:
#
#   earnings_241.json          the 241-row core dataset: one row per
#                               ticker-quarter, with the AI-generated
#                               "final_paragraph" (right column) and its
#                               2-day return. The one thing everything else
#                               is keyed against.
#   price_history.json         daily close prices per ticker + S&P 500,
#                               padded ~3 months either side of each
#                               ticker's first/last quarter, for the charts.
#   bullets_241.json           neutral, fact-only bullet points stripped of
#                               narrative/sentiment, summarizing each row's
#                               final_paragraph (shown under "Generated text").
#
#   -- left column ("Contextualized interpretation") --
#   websearch_long_241.json    CURRENT / PRIMARY source: real web-search
#                               research, long format -- Prior Context /
#                               Current Earnings Release / Possible Drivers,
#                               broken into individual paragraphs, each with
#                               its own cited sources (or none, if that
#                               paragraph is inference rather than sourced
#                               fact). Covers all 241 rows.
#
# (data/websearch_summary_241.json also exists on disk -- a short-form
# summary version of the same research, with a Long format/Summary toggle
# in an earlier version of this dashboard -- but nothing currently loads
# it; the dashboard shows the long format only.)
#   my_notes.json               LEGACY fallback: an earlier, less-grounded
#   sources_241.json            (ChatGPT-drafted) context text + sources.
#                               Only used for a row if it has no
#                               websearch_long_241.json entry -- in
#                               practice that's no rows any more, since
#                               web-search research now covers all 241, but
#                               the fallback is left in for robustness.
#   context_summaries_241.json  short, number-free qualitative summaries
#                               (e.g. "AAON underperformed the market
#                               heading in, as...") used only inside the
#                               per-quarter "Visualize" chart popup, not the
#                               main left column.
#
# (data/key_dates_241.json also exists on disk -- an earlier iteration of
# the Visualize chart plotted its entries as extra vertical lines -- but
# nothing currently loads it; kept in case that's revisited.)
def _mtime(path):
    """File's last-modified time, used as a cache-busting argument below --
    passing this into a @st.cache_data function makes Streamlit's cache key
    include it, so editing the JSON file on disk (without editing any code)
    is enough to invalidate the cache on the next rerun. Without this, the
    cache would keep serving the old file contents for the life of the
    process, and only a full restart would pick up the change -- which was
    the actual reason a restart was needed after every data edit."""
    return os.path.getmtime(path) if os.path.exists(path) else None


@st.cache_data
def load_data(mtime_marker):
    with open(DATA_PATH) as f:
        rows = json.load(f)
    df = pd.DataFrame(rows)
    df["earnings_date"] = pd.to_datetime(df["earnings_date"])
    return df.sort_values(["ticker", "earnings_date"])


@st.cache_data
def load_notes(mtime_marker):
    if os.path.exists(NOTES_PATH):
        with open(NOTES_PATH) as f:
            return json.load(f)
    return {}


@st.cache_data
def logo_data_uri(mtime_marker):
    if not os.path.exists(LOGO_PATH):
        return None
    with open(LOGO_PATH, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


@st.cache_data
def load_price_history(mtime_marker):
    if not os.path.exists(PRICE_HISTORY_PATH):
        return None
    with open(PRICE_HISTORY_PATH) as f:
        return json.load(f)


@st.cache_data
def load_abnormal_returns(mtime_marker):
    if not os.path.exists(ABNORMAL_RETURNS_PATH):
        return {}
    with open(ABNORMAL_RETURNS_PATH) as f:
        return json.load(f)


@st.cache_data
def load_bullets(mtime_marker):
    if not os.path.exists(BULLETS_PATH):
        return {}
    with open(BULLETS_PATH) as f:
        rows = json.load(f)
    return {(r["ticker"], r["fiscal_yearquarter"]): r["bullets"] for r in rows}


@st.cache_data
def load_sources(mtime_marker):
    if not os.path.exists(SOURCES_PATH):
        return {}
    with open(SOURCES_PATH) as f:
        return json.load(f)


@st.cache_data
def load_context_summaries(mtime_marker):
    if not os.path.exists(CONTEXT_SUMMARIES_PATH):
        return {}
    with open(CONTEXT_SUMMARIES_PATH) as f:
        return json.load(f)


@st.cache_data
def load_websearch_long(mtime_marker):
    if not os.path.exists(WEBSEARCH_LONG_PATH):
        return {}
    with open(WEBSEARCH_LONG_PATH) as f:
        return json.load(f)


@st.cache_data
def load_company_info(mtime_marker):
    if not os.path.exists(COMPANY_INFO_PATH):
        return {}
    with open(COMPANY_INFO_PATH) as f:
        return json.load(f)


@st.cache_data
def load_comparative_answers(mtime_marker):
    if not os.path.exists(COMPARATIVE_ANSWERS_PATH):
        return {}
    with open(COMPARATIVE_ANSWERS_PATH) as f:
        return json.load(f)


def save_comparative_answers(answers):
    """Not cached, not mtime-gated -- this is the one place in the dashboard
    that writes data back to disk. The write updates the file's mtime, so
    the next script rerun's load_comparative_answers() call (same
    cache-busting pattern as every other loader) picks up the change."""
    with open(COMPARATIVE_ANSWERS_PATH, "w") as f:
        json.dump(answers, f, indent=2)


@st.cache_data
def load_group_coverage_accuracy(mtime_marker):
    if not os.path.exists(GROUP_COVERAGE_ACCURACY_PATH):
        return {}
    with open(GROUP_COVERAGE_ACCURACY_PATH) as f:
        return json.load(f)


def save_group_coverage_accuracy(answers):
    with open(GROUP_COVERAGE_ACCURACY_PATH, "w") as f:
        json.dump(answers, f, indent=2)


def anchor_id(ticker, fiscal_yearquarter):
    return f"q_{ticker}_{fiscal_yearquarter}"


@st.cache_data
def load_group_returns(mtime_marker):
    """Data Visualization 2's underlying data: the cleaned full returns panel,
    filtered to the group tickers and renamed to match the column names
    render_price_chart()/build_quarter_visualize_fig() already expect
    (earnings_date, fiscal_yearquarter), so those two chart functions can be
    reused as-is for this section too."""
    if not os.path.exists(GROUP_RETURNS_PATH):
        return pd.DataFrame()
    all_group_tickers = [t for tickers in GROUPS.values() for t in tickers]
    df = pd.read_csv(GROUP_RETURNS_PATH, parse_dates=["earningsdate"])
    df = df[df["ticker"].isin(all_group_tickers)].copy()
    df = df.rename(columns={"earningsdate": "earnings_date", "yq": "fiscal_yearquarter"})
    return df.sort_values(["ticker", "earnings_date"]).reset_index(drop=True)


DATAVIZ3_WINDOW_START = pd.Timestamp("2021-01-01")
DATAVIZ3_WINDOW_END = pd.Timestamp("2023-12-31")
DATAVIZ3_SEED = 20260928


@st.cache_data
def load_group3_band_observations(mtime_marker):
    """Data Visualization 3's Group 1/2/3 subgroups: the SAME 30 tickers as
    Data Visualization 2 (same market-cap bands, same GROUP_MARKET_CAP_
    LABELS), but a different, non-overlapping observation window --
    2021-2023 instead of the panel-midpoint-centered quarters Data
    Visualization 2 shows -- so nothing here duplicates an observation
    already displayed there. Up to 10 quarters per ticker, randomly
    sampled (fixed seed) when more than 10 fall in the window.

    FB is a special case: Yahoo delisted the "FB" ticker entirely after
    Facebook's 2022 rename (see the price-history fix elsewhere in this
    file), and the returns dataset itself splits the same company's
    2021-2023 history across two ticker symbols -- "FB" through
    2022q2, "META" from 2022q3 on. Both halves are pulled and relabeled
    "FB" here so this ticker's 10 observations span the full window
    continuously, matching how GROUPS/GROUP_COMPANY_NAMES elsewhere in
    this file already treat FB as the single canonical symbol for this
    company (avoiding double-counting it under two tickers)."""
    if not os.path.exists(GROUP_RETURNS_PATH):
        return pd.DataFrame()
    all_group_tickers = [t for tickers in GROUPS.values() for t in tickers]
    raw = pd.read_csv(GROUP_RETURNS_PATH, parse_dates=["earningsdate"])
    raw = raw.rename(columns={"earningsdate": "earnings_date", "yq": "fiscal_yearquarter"})
    window = raw[(raw["earnings_date"] >= DATAVIZ3_WINDOW_START) & (raw["earnings_date"] <= DATAVIZ3_WINDOW_END)]

    fb_rows = window[window["ticker"].isin(["FB", "META"])].copy()
    fb_rows["ticker"] = "FB"
    other_rows = window[window["ticker"].isin(all_group_tickers) & (window["ticker"] != "FB")]
    combined = pd.concat([other_rows, fb_rows], ignore_index=True)

    sampled = (
        combined.groupby("ticker", group_keys=False)
        .apply(lambda g: g.sample(n=min(10, len(g)), random_state=DATAVIZ3_SEED))
    )
    return sampled.sort_values(["ticker", "earnings_date"]).reset_index(drop=True)


# Data Visualization 5: 2 new market-cap bands (Small & Mid Cap and a
# merged Large Cap band covering $100B-$1T -- the original 3-band split
# had a separate Mega Cap $500B+ tier, but true mega-caps are scarce once
# Data Viz 1/2/3's tickers are excluded, so Large and Mega were merged
# into one band per the user's direction), with their own randomly-
# selected tickers -- pulled only from our own CUPIP earnings-returns
# dataset, excluding every ticker already used in Data Viz 1/2/3 -- and
# 10 quarters per ticker in the same 2021-2023 window as Data Viz 3.
# Market cap itself isn't in our dataset, so screening these tickers
# needed one-off live yfinance lookups (scripts/screen_viz4_candidates.py,
# run slowly/sequentially after an earlier aggressive attempt triggered a
# temporary IP-level Yahoo rate limit); the result is fixed data from here
# on, no live lookups happen at app runtime.
GROUP4_GROUPS = {
    "Small & Mid Cap": ["MTW", "SFIX", "PCTY", "MGNI", "ASO", "NGL", "REZI", "CENTA", "BSM", "METC"],
    "Large Cap": ["BA", "JNJ", "PH", "MRVL", "FTNT", "TMUS", "UBER", "VZ", "MO", "MCD"],
}
GROUP4_BAND_LABELS = {
    "Small & Mid Cap": "\\$250M\u2013\\$10B, 2021-2023",
    "Large Cap": "\\$100B\u2013\\$1T, 2021-2023",
}
GROUP4_COMPANY_NAMES = {
    "MTW": "Manitowoc", "SFIX": "Stitch Fix", "PCTY": "Paylocity", "MGNI": "Magnite",
    "ASO": "Academy Sports & Outdoors", "NGL": "NGL Energy Partners", "REZI": "Resideo Technologies",
    "CENTA": "Central Garden & Pet", "BSM": "Black Stone Minerals", "METC": "Ramaco Resources",
    "BA": "Boeing", "JNJ": "Johnson & Johnson", "PH": "Parker-Hannifin", "MRVL": "Marvell Technology",
    "FTNT": "Fortinet", "TMUS": "T-Mobile US", "UBER": "Uber Technologies", "VZ": "Verizon Communications",
    "MO": "Altria Group", "MCD": "McDonald's",
}
GROUP4_PRICE_HISTORY_PATH = os.path.join(HERE, "data", "group4_price_history.json")


@st.cache_data
def load_group4_price_history(mtime_marker):
    if not os.path.exists(GROUP4_PRICE_HISTORY_PATH):
        return None
    with open(GROUP4_PRICE_HISTORY_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group4_band_observations(mtime_marker):
    """Same pattern as load_group3_band_observations(), for GROUP4_GROUPS'
    tickers -- up to 10 quarters per ticker in 2021-2023, randomly sampled
    (fixed seed) when more than 10 fall in the window. No FB-style ticker-
    rename special case needed here."""
    if not os.path.exists(GROUP_RETURNS_PATH):
        return pd.DataFrame()
    group4_tickers = [t for tickers in GROUP4_GROUPS.values() for t in tickers]
    raw = pd.read_csv(GROUP_RETURNS_PATH, parse_dates=["earningsdate"])
    raw = raw.rename(columns={"earningsdate": "earnings_date", "yq": "fiscal_yearquarter"})
    window = raw[
        (raw["earnings_date"] >= DATAVIZ3_WINDOW_START)
        & (raw["earnings_date"] <= DATAVIZ3_WINDOW_END)
        & (raw["ticker"].isin(group4_tickers))
    ]
    sampled = (
        window.groupby("ticker", group_keys=False)
        .apply(lambda g: g.sample(n=min(10, len(g)), random_state=DATAVIZ3_SEED))
    )
    return sampled.sort_values(["ticker", "earnings_date"]).reset_index(drop=True)


# Data Visualization 6: same pattern as Data Visualization 5 -- 20 more
# newly-selected tickers (screened via live yfinance market-cap lookups
# against our own CUPIP dataset, excluding every ticker already used in
# Data Viz 1/2/3/4; scripts/screen_viz5_candidates.py), same 2 bands, same
# 2021-2023 window. The Large Cap band's candidate pool came out to
# exactly 10 after screening, so all 10 are used rather than a random
# subset of a larger pool -- still a randomly-discovered set (from
# shuffling the full eligible candidate list first), just with no surplus
# left to additionally sample from.
GROUP5_GROUPS = {
    "Small & Mid Cap": ["CYH", "MATW", "INDI", "GRC", "APPN", "AXTI", "RYTM", "ALGM", "WLK", "PCVX"],
    "Large Cap": ["SYK", "MPC", "SPGI", "NEE", "MRK", "KO", "LRCX", "COST", "CSCO", "XOM"],
}
GROUP5_BAND_LABELS = {
    "Small & Mid Cap": "\\$250M\u2013\\$10B, 2021-2023",
    "Large Cap": "\\$100B\u2013\\$1T, 2021-2023",
}
GROUP5_COMPANY_NAMES = {
    "CYH": "Community Health Systems", "MATW": "Matthews International", "INDI": "indie Semiconductor",
    "GRC": "Gorman-Rupp", "APPN": "Appian", "AXTI": "AXT Inc.", "RYTM": "Rhythm Pharmaceuticals",
    "ALGM": "Allegro MicroSystems", "WLK": "Westlake", "PCVX": "Vaxcyte",
    "SYK": "Stryker", "MPC": "Marathon Petroleum", "SPGI": "S&P Global", "NEE": "NextEra Energy",
    "MRK": "Merck & Co.", "KO": "Coca-Cola", "LRCX": "Lam Research", "COST": "Costco Wholesale",
    "CSCO": "Cisco Systems", "XOM": "Exxon Mobil",
}
GROUP5_PRICE_HISTORY_PATH = os.path.join(HERE, "data", "group5_price_history.json")


@st.cache_data
def load_group5_price_history(mtime_marker):
    if not os.path.exists(GROUP5_PRICE_HISTORY_PATH):
        return None
    with open(GROUP5_PRICE_HISTORY_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group5_band_observations(mtime_marker):
    """Same pattern as load_group4_band_observations(), for GROUP5_GROUPS'
    tickers."""
    if not os.path.exists(GROUP_RETURNS_PATH):
        return pd.DataFrame()
    group5_tickers = [t for tickers in GROUP5_GROUPS.values() for t in tickers]
    raw = pd.read_csv(GROUP_RETURNS_PATH, parse_dates=["earningsdate"])
    raw = raw.rename(columns={"earningsdate": "earnings_date", "yq": "fiscal_yearquarter"})
    window = raw[
        (raw["earnings_date"] >= DATAVIZ3_WINDOW_START)
        & (raw["earnings_date"] <= DATAVIZ3_WINDOW_END)
        & (raw["ticker"].isin(group5_tickers))
    ]
    sampled = (
        window.groupby("ticker", group_keys=False)
        .apply(lambda g: g.sample(n=min(10, len(g)), random_state=DATAVIZ3_SEED))
    )
    return sampled.sort_values(["ticker", "earnings_date"]).reset_index(drop=True)


# Data Visualization 7: same pattern as Data Visualization 5/6 -- 24 more
# newly-selected tickers (screened via live yfinance market-cap lookups
# against our own CUPIP dataset, excluding every ticker already used in
# Data Viz 1/2/3/4/5; scripts/screen_viz6_candidates.py), same 2021-2023
# window. Large Cap ($100B-$1T) candidates were scarce after excluding
# everything already used elsewhere -- the screen found only 14 before
# stopping (vs. the usual 18-candidate margin), so all 14 are used rather
# than trimming to 10 to match the other groups.
GROUP6_GROUPS = {
    "Small & Mid Cap": ["NABL", "DSGN", "PUBM", "ABEO", "LFST", "CRAI", "GOGO", "RCUS", "GDYN", "KURA"],
    "Large Cap": [
        "DELL", "QCOM", "PSX", "SNOW", "APP", "ADI", "PFE", "PEP", "NET", "WDC",
        "IBM", "AMD", "DE", "CRWD",
    ],
}
GROUP6_BAND_LABELS = {
    "Small & Mid Cap": "\\$250M\u2013\\$10B, 2021-2023",
    "Large Cap": "\\$100B\u2013\\$1T, 2021-2023",
}
GROUP6_COMPANY_NAMES = {
    "NABL": "N-able", "DSGN": "Design Therapeutics", "PUBM": "PubMatic", "ABEO": "Abeona Therapeutics",
    "LFST": "LifeStance Health Group", "CRAI": "CRA International", "GOGO": "Gogo",
    "RCUS": "Arcus Biosciences", "GDYN": "Grid Dynamics Holdings", "KURA": "Kura Oncology",
    "DELL": "Dell Technologies", "QCOM": "Qualcomm", "PSX": "Phillips 66", "SNOW": "Snowflake",
    "APP": "AppLovin", "ADI": "Analog Devices", "PFE": "Pfizer", "PEP": "PepsiCo",
    "NET": "Cloudflare", "WDC": "Western Digital", "IBM": "International Business Machines",
    "AMD": "Advanced Micro Devices", "DE": "Deere & Company", "CRWD": "CrowdStrike Holdings",
}
GROUP6_PRICE_HISTORY_PATH = os.path.join(HERE, "data", "group6_price_history.json")


@st.cache_data
def load_group6_price_history(mtime_marker):
    if not os.path.exists(GROUP6_PRICE_HISTORY_PATH):
        return None
    with open(GROUP6_PRICE_HISTORY_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group6_band_observations(mtime_marker):
    """Same pattern as load_group5_band_observations(), for GROUP6_GROUPS'
    tickers."""
    if not os.path.exists(GROUP_RETURNS_PATH):
        return pd.DataFrame()
    group6_tickers = [t for tickers in GROUP6_GROUPS.values() for t in tickers]
    raw = pd.read_csv(GROUP_RETURNS_PATH, parse_dates=["earningsdate"])
    raw = raw.rename(columns={"earningsdate": "earnings_date", "yq": "fiscal_yearquarter"})
    window = raw[
        (raw["earnings_date"] >= DATAVIZ3_WINDOW_START)
        & (raw["earnings_date"] <= DATAVIZ3_WINDOW_END)
        & (raw["ticker"].isin(group6_tickers))
    ]
    sampled = (
        window.groupby("ticker", group_keys=False)
        .apply(lambda g: g.sample(n=min(10, len(g)), random_state=DATAVIZ3_SEED))
    )
    return sampled.sort_values(["ticker", "earnings_date"]).reset_index(drop=True)


@st.cache_data
def load_group_price_history(mtime_marker):
    if not os.path.exists(GROUP_PRICE_HISTORY_PATH):
        return None
    with open(GROUP_PRICE_HISTORY_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group_abnormal_returns(mtime_marker):
    if not os.path.exists(GROUP_ABNORMAL_RETURNS_PATH):
        return {}
    with open(GROUP_ABNORMAL_RETURNS_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group4_abnormal_returns(mtime_marker):
    if not os.path.exists(GROUP4_ABNORMAL_RETURNS_PATH):
        return {}
    with open(GROUP4_ABNORMAL_RETURNS_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group5_abnormal_returns(mtime_marker):
    if not os.path.exists(GROUP5_ABNORMAL_RETURNS_PATH):
        return {}
    with open(GROUP5_ABNORMAL_RETURNS_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group6_abnormal_returns(mtime_marker):
    if not os.path.exists(GROUP6_ABNORMAL_RETURNS_PATH):
        return {}
    with open(GROUP6_ABNORMAL_RETURNS_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group_context(mtime_marker):
    if not os.path.exists(GROUP_CONTEXT_PATH):
        return {}
    with open(GROUP_CONTEXT_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group_wsj_coverage(mtime_marker):
    if not os.path.exists(GROUP_WSJ_COVERAGE_PATH):
        return {}
    with open(GROUP_WSJ_COVERAGE_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group_djnw_coverage(mtime_marker):
    if not os.path.exists(GROUP_DJNW_COVERAGE_PATH):
        return {}
    with open(GROUP_DJNW_COVERAGE_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group_massive_benzinga_coverage(mtime_marker):
    if not os.path.exists(GROUP_MASSIVE_BENZINGA_COVERAGE_PATH):
        return {}
    with open(GROUP_MASSIVE_BENZINGA_COVERAGE_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group_alphanews_coverage(mtime_marker):
    if not os.path.exists(GROUP_ALPHANEWS_COVERAGE_PATH):
        return {}
    with open(GROUP_ALPHANEWS_COVERAGE_PATH) as f:
        return json.load(f)


@st.cache_data
def load_massive_benzinga_coverage(mtime_marker):
    if not os.path.exists(MASSIVE_BENZINGA_COVERAGE_PATH):
        return {}
    with open(MASSIVE_BENZINGA_COVERAGE_PATH) as f:
        return json.load(f)


@st.cache_data
def load_massive_news_coverage(mtime_marker):
    if not os.path.exists(MASSIVE_NEWS_COVERAGE_PATH):
        return {}
    with open(MASSIVE_NEWS_COVERAGE_PATH) as f:
        return json.load(f)


@st.cache_data
def load_stocknews_coverage(mtime_marker):
    if not os.path.exists(STOCKNEWS_COVERAGE_PATH):
        return {}
    with open(STOCKNEWS_COVERAGE_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group4_stocknews_v2(mtime_marker):
    """Data Visualization 5's "Why Moved 2" (v2, 11-category) StockNews
    coverage -- a deterministic, non-overlapping split between two writers
    (Claude processed stocknews_v2_claude.json's note keys, Codex/OpenAI
    processed the 3 stocknews_v2_codex_shard_*.json files', 24 keys each),
    so a plain dict union is safe: confirmed no key collisions across any
    of these files. stocknews_v2_rebuild.json is read too for
    forward-compatibility but is currently stale (see path comment above)."""
    result = {}
    paths = (
        [GROUP4_STOCKNEWS_V2_REBUILD_PATH]
        + GROUP4_STOCKNEWS_V2_CODEX_SHARD_PATHS
        + [GROUP4_STOCKNEWS_V2_CLAUDE_PATH]
    )
    for path in paths:
        if os.path.exists(path):
            with open(path) as f:
                result.update(json.load(f))
    return result


@st.cache_data
def load_viz45_chatgpt_coverage(mtime_marker):
    if not os.path.exists(VIZ45_CHATGPT_COVERAGE_PATH):
        return {}
    with open(VIZ45_CHATGPT_COVERAGE_PATH) as f:
        return json.load(f)


@st.cache_data
def load_viz2_chatgpt_coverage(mtime_marker):
    if not os.path.exists(VIZ2_CHATGPT_COVERAGE_PATH):
        return {}
    with open(VIZ2_CHATGPT_COVERAGE_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group_pd_categories(mtime_marker):
    if not os.path.exists(GROUP_PD_CATEGORIES_PATH):
        return {}
    with open(GROUP_PD_CATEGORIES_PATH) as f:
        return json.load(f)


@st.cache_data
def load_group_first_order_categories(mtime_marker):
    if not os.path.exists(GROUP_FIRST_ORDER_CATEGORIES_PATH):
        return {}
    with open(GROUP_FIRST_ORDER_CATEGORIES_PATH) as f:
        return json.load(f)


def render_wsj_pdf_link_html(source, static_slug):
    """Returns HTML for a plain link that opens the source PDF in a new
    browser tab, served from Streamlit's static/ folder (see
    GROUP_WSJ_STATIC_SLUGS above for why this isn't a data: URI), plus a
    second "Download PDF" fallback link with the `download` attribute --
    in case the viewer's browser or settings don't open the PDF inline
    (e.g. a PDF viewer extension disabled, or a browser configured to
    always download PDFs instead of displaying them), this forces a
    plain file save instead of doing nothing. Returns a string (rather
    than calling st.markdown directly) so the caller can fold it into a
    larger combined HTML block -- see format_websearch_context_split()'s
    docstring for why that matters here."""
    filename = source.get("filename")
    if not filename or static_slug is None:
        return ""
    url = f"/app/static/{static_slug}/{url_quote(filename)}"
    label = source.get("title") or filename
    published = source.get("published_date", "")
    label_text = f"{label} ({published})" if published else label
    link_style = (
        "display:block; color:#4A90D9; font-size:0.85rem; "
        "margin-bottom:0.3rem; text-decoration:none;"
    )
    return (
        f"<a href='{url}' target='_blank' rel='noopener noreferrer' style='{link_style}'>"
        f"&#128196; Open PDF: {label_text}</a>"
        f"<a href='{url}' download='{filename}' style='{link_style} font-size:0.78rem; opacity:0.8;'>"
        f"&#11015; Download PDF</a>"
    )


def coverage_accuracy_html(note_key, source_key):
    """Read-only accuracy rating shown beneath Data Visualization 2 coverage."""
    value = (group_coverage_accuracy_lookup.get(note_key) or {}).get(source_key, "Not yet rated")
    colors = {
        "Accurate": ("#2ecc71", "Accurate"),
        "Not accurate": ("#e74c3c", "Not accurate"),
        "Not yet rated": ("rgba(214,228,240,0.55)", "Not yet rated"),
    }
    color, label = colors.get(value, colors["Not yet rated"])
    return (
        "<div style='margin-top:0.8rem; padding-top:0.55rem; border-top:1px solid rgba(255,255,255,0.12); "
        "font-size:0.86rem; font-weight:600;'>Coverage accuracy: "
        f"<span style='color:{color};'>{label}</span></div>"
    )


def render_djnw_source_link_html(source):
    """Returns HTML for a button-styled link to the original Dow Jones
    Newswires source page. Unlike the WSJ PDFs, these are already public
    URLs (mirrored on foxbusiness.com/advfn.com/finanznachrichten.de),
    so it just opens directly -- no local static-file copy needed."""
    url = source.get("url")
    if not url:
        return ""
    label = source.get("title") or "View source"
    button_style = (
        "display:inline-block; margin-top:0.3rem; margin-bottom:0.3rem; "
        "padding:0.4rem 0.9rem; border-radius:6px; background:#2E5E8C; "
        "color:#F0F4F8; font-size:0.85rem; text-decoration:none; font-weight:600;"
    )
    return f"<a href='{url}' target='_blank' rel='noopener noreferrer' style='{button_style}'>&#128279; View Source: {label}</a>"


PD_CATEGORY_SOURCES = [
    ("contextual_analysis", "Contextualized interpretation"),
    ("wsj", "WSJ Coverage"),
    ("djnw", "Dow Jones Newswires Coverage"),
]


@st.dialog(" ", width="large")
def _show_pd_categories_dialog(note_key):
    # Streamlit renders the @st.dialog() title itself, left-aligned, with
    # no built-in way to center it -- a CSS rule targeting its container
    # didn't take effect (its exact DOM structure isn't a stable target
    # across Streamlit versions), so the decorator gets a blank title
    # instead and this renders the real, centered one as ordinary content.
    st.markdown("<h2 style='text-align:center;'>PD Data Categories</h2>", unsafe_allow_html=True)
    entry = group_pd_categories_lookup.get(note_key)
    if not entry:
        st.info(
            "No PD Data Categories analysis available yet for this observation. "
            "The analysis is available for the complete 300-observation dashboard dataset."
        )
        return

    # Built as one combined HTML grid (not per-column st.markdown/st.caption
    # calls) for two reasons: (1) a shared grid with each category pinned to
    # its own explicit row is what makes "Guidance" / "Revenue" / etc. line
    # up laterally across all 3 columns regardless of how long any one
    # source's one-liner reason is -- same technique as the "Possible
    # Drivers" alignment elsewhere in this file. (2) plain st.markdown/
    # st.caption run text through Streamlit's markdown parser, which
    # renders anything between two "$" as LaTeX math -- every reason here
    # has two dollar amounts (e.g. "$500 million ... $3.5 billion"), which
    # was silently mangling them into squished italic math. render_inline_
    # markdown() escapes "$" before this ever reaches the parser.
    header_row = []
    for src_key, src_label in PD_CATEGORY_SOURCES:
        header_row.append(
            f"<div style='text-align:center; font-weight:bold; font-size:1.15rem;'>{src_label}</div>"
        )
    grid_parts = [
        f"<div style='grid-column:{i+1}; grid-row:1;'>{h}</div>" for i, h in enumerate(header_row)
    ]

    for row_i, category in enumerate(PD_CATEGORIES, start=2):
        for col_i, (src_key, src_label) in enumerate(PD_CATEGORY_SOURCES, start=1):
            src_data = entry.get(src_key)
            if src_data is None:
                if row_i == 2:
                    grid_parts.append(
                        f"<div style='grid-column:{col_i}; grid-row:2;'>"
                        f"<p style='font-size:0.95rem; font-style:italic; opacity:0.75;'>"
                        f"No coverage from this source for this observation.</p></div>"
                    )
                continue
            cell = src_data.get(category) or {}
            rating = cell.get("rating")
            reason = cell.get("reason")
            if rating == "positive":
                badge = "<span style='color:#5FBF6E;'>&#9679; Positive</span>"
            elif rating == "negative":
                badge = "<span style='color:#E06C6C;'>&#9679; Negative</span>"
            elif rating == "neutral":
                badge = "<span style='color:#B8C4D6;'>&#9679; Neutral</span>"
            else:
                badge = "<span style='opacity:0.5;'>&mdash;</span>"
            cell_html = (
                f"<div style='margin-bottom:0.6rem;'>"
                f"<div style='font-size:1rem; font-weight:600;'>{category} {badge}</div>"
            )
            if reason:
                cell_html += (
                    f"<div style='font-size:0.9rem; opacity:0.85; line-height:1.3;'>"
                    f"{render_inline_markdown(reason)}</div>"
                )
            cell_html += "</div>"
            grid_parts.append(f"<div style='grid-column:{col_i}; grid-row:{row_i};'>{cell_html}</div>")

    st.markdown(
        "<div style='display:grid; grid-template-columns: 1fr 1fr 1fr; "
        "column-gap:1.5rem; align-items:start;'>" + "".join(grid_parts) + "</div>",
        unsafe_allow_html=True,
    )


# Exact key strings of the "categories" table written by the Why Moved 2
# prompt (see "Why Moved 2.md") -- a different, 11-category set from
# PD_CATEGORIES above.
WHY_MOVED_2_CATEGORIES = [
    "Guidance",
    "Order book / backlog",
    "Revenue",
    "New Product Release / Users",
    "Profits, costs and margin",
    "Debt, leverage and capital raise",
    "Capex",
    "Management",
    "Litigation",
    "Macro and micro development",
    "Immediate reaction divergence",
]


@st.dialog(" ", width="large")
def _show_why_moved_2_categories_dialog(entry, source_label):
    st.markdown(f"<h2 style='text-align:center;'>{source_label} Categories</h2>", unsafe_allow_html=True)
    categories = entry.get("categories") or {}
    header_style = "font-weight:bold; font-size:1.05rem; padding-bottom:0.4rem; border-bottom:1px solid rgba(74,144,217,0.4);"
    rows = [
        f"<div style='{header_style}'>Category</div>"
        f"<div style='{header_style}'>Direction</div>"
        f"<div style='{header_style}'>Attribution</div>"
        f"<div style='{header_style}'>What happened vs. expected</div>"
    ]
    for category in WHY_MOVED_2_CATEGORIES:
        cell = categories.get(category)
        if not cell:
            rows.append(
                f"<div style='opacity:0.5;'>{category}</div>"
                "<div style='opacity:0.5;'>&mdash;</div>"
                "<div style='opacity:0.5;'>&mdash;</div>"
                "<div style='opacity:0.5; font-style:italic;'>Not tied to the stock's move</div>"
            )
            continue
        if cell.get("direction") == "positive":
            badge = "<span style='color:#5FBF6E;'>&#9679; Positive</span>"
        else:
            badge = "<span style='color:#E06C6C;'>&#9679; Negative</span>"
        attribution = (cell.get("attribution") or "").capitalize()
        rows.append(
            f"<div style='font-weight:600;'>{category}</div>"
            f"<div>{badge}</div>"
            f"<div>{attribution}</div>"
            f"<div style='font-size:0.92rem; line-height:1.35;'>{render_inline_markdown(cell.get('text') or '')}</div>"
        )
    st.markdown(
        "<div style='display:grid; grid-template-columns: 1.3fr 0.8fr 0.8fr 3fr; "
        "column-gap:1.2rem; row-gap:0.7rem; align-items:start;'>" + "".join(rows) + "</div>",
        unsafe_allow_html=True,
    )


@st.dialog(" ", width="large")
def _show_first_order_categories_dialog(note_key):
    st.markdown("<h2 style='text-align:center;'>First Order Categories</h2>", unsafe_allow_html=True)
    abnormal = group_abnormal_returns_lookup.get(note_key, {})
    market_adjusted = abnormal.get("market_adjusted") or {}
    market_model = abnormal.get("market_model") or {}
    excess = market_adjusted.get("excess_return_pct")
    excess_z = market_adjusted.get("z_score")
    abnormal_return = market_model.get("abnormal_return_pct")
    abnormal_z = market_model.get("z_score")

    def metric(value, z_score):
        if value is None or z_score is None:
            return "n/a"
        return f"{value:+.2f}% ({z_score:+.2f}σ)"

    st.markdown(
        "<div style='text-align:center; font-size:1rem; margin-bottom:1.2rem; opacity:0.9;'>"
        f"Market-adjusted excess return: <b>{metric(excess, excess_z)}</b>"
        " &nbsp;|&nbsp; "
        f"Beta-adjusted abnormal return: <b>{metric(abnormal_return, abnormal_z)}</b>"
        "</div>",
        unsafe_allow_html=True,
    )

    entry = group_first_order_categories_lookup.get(note_key)
    if not entry:
        st.info("No First Order Categories analysis is available for this observation.")
        return

    grid_parts = []
    for col_i, (source_key, source_label) in enumerate(PD_CATEGORY_SOURCES, start=1):
        grid_parts.append(
            f"<div style='grid-column:{col_i}; grid-row:1; text-align:center; "
            f"font-weight:bold; font-size:1.15rem;'>{source_label}</div>"
        )
        categories = entry.get(source_key)
        if not categories:
            grid_parts.append(
                f"<div style='grid-column:{col_i}; grid-row:2;'>"
                "<p style='font-size:0.95rem; font-style:italic; opacity:0.75;'>"
                "No first-order category implied by this coverage.</p></div>"
            )
            continue
        cells = []
        for item in categories[:2]:
            rating = item.get("rating")
            badge = (
                "<span style='color:#5FBF6E;'>&#9679; Positive</span>"
                if rating == "positive"
                else "<span style='color:#E06C6C;'>&#9679; Negative</span>"
            )
            cells.append(
                "<div style='margin-bottom:1rem;'>"
                f"<div style='font-size:1rem; font-weight:600;'>{item['category']} {badge}</div>"
                f"<div style='font-size:0.9rem; opacity:0.85; line-height:1.3;'>"
                f"{render_inline_markdown(item.get('reason', ''))}</div></div>"
            )
        grid_parts.append(
            f"<div style='grid-column:{col_i}; grid-row:2;'>{''.join(cells)}</div>"
        )

    st.markdown(
        "<div style='display:grid; grid-template-columns:1fr 1fr 1fr; "
        "column-gap:1.5rem; align-items:start;'>" + "".join(grid_parts) + "</div>",
        unsafe_allow_html=True,
    )


GROUP_PERIOD_MIDPOINT = pd.Timestamp("2017-07-01")  # midpoint of the 2010-2024 panel coverage


def middle_n_quarters(ticker_df, n=10, anchor=GROUP_PERIOD_MIDPOINT):
    """Take the n observations closest to the middle of the overall
    2010-2024 panel period (not the middle of this particular ticker's own
    row count) -- these tickers have 40-60 quarters each (vs. ~14 for the
    curated 241-observation set), too many to show at once. Anchoring on the
    fixed calendar midpoint, rather than each ticker's own coverage span,
    keeps every ticker's 10 shown quarters comparable across tickers even
    though a few (PANW, FB) don't cover the full period."""
    n_rows = len(ticker_df)
    if n_rows <= n:
        return ticker_df
    closest = ticker_df.iloc[(ticker_df["earnings_date"] - anchor).abs().argsort()[:n]]
    return closest.sort_values("earnings_date")


# =============================================================================
# 4. LEFT-COLUMN CONTEXT-TEXT RENDERING
# =============================================================================
# Two independent rendering paths feed the left ("Contextualized
# interpretation") column, matching the two data sources described above:
#
#   format_context_text()      renders the LEGACY my_notes.json text --
#                               plain "Prior Context / Earnings Summary /
#                               Possible Drivers" paragraphs, one shared
#                               Verify button per quarter (via sources_241.json).
#
#   format_websearch_context() renders the CURRENT websearch_*.json data --
#                               same three-section shape, but each
#                               paragraph carries its own sources (or none),
#                               so Verify buttons are per-paragraph, and
#                               there's an optional Long-format/Summary tab
#                               toggle. This is what every row actually
#                               shows now; format_context_text only fires as
#                               a fallback (see the main loop below).
#
# Both share render_inline_markdown() for turning the light markdown inside
# the text (**bold** driver labels, *italic* titles, literal $ signs) into
# safe HTML -- needed because everything here is rendered via st.html(),
# which does NOT run a markdown parser (unlike st.markdown), so nothing
# gets automatic bold/italic handling for free.

_CONTEXT_SECTION_HEADINGS = {"Prior Context", "Earnings Summary", "Possible Drivers of the Stock Move"}
_CONTEXT_DRIVER_RE = re.compile(r"^((?:First|Second|Third)-order driver — [^\n]+)\n(.*)$", re.DOTALL)
_CONTEXT_HIDDEN_PARAGRAPHS = {
    "These are ranked candidate drivers rather than confirmed causes of the stock reaction."
}


def format_context_text(text):
    """Render the ChatGPT-generated context text as HTML, coloring its
    'Prior Context' / 'Earnings Summary' / 'Possible Drivers...' section
    headings and 'First/Second/Third-order driver' sub-headings gold, so
    they read as structure rather than running into the body text."""
    parts = []
    for para in text.strip().split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para in _CONTEXT_HIDDEN_PARAGRAPHS:
            continue
        if para in _CONTEXT_SECTION_HEADINGS:
            parts.append(f"<div class='context-heading'>{para}</div>")
            continue
        m = _CONTEXT_DRIVER_RE.match(para)
        if m:
            heading, body = m.group(1), m.group(2)
            body = body.replace("$", "&#36;")
            parts.append(
                f"<div class='context-driver-heading'>{heading}</div>"
                f"<div class='context-driver-body'>{body}</div>"
            )
            continue
        para = para.replace("$", "&#36;")
        parts.append(f"<p style='margin-bottom:0.6rem; text-align:justify;'>{para}</p>")
    return "".join(parts)


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


def render_inline_markdown(text):
    """Escape $ (see format_context_text), turn **bold** spans -- used for
    driver lead-ins like '**First-order driver -- ...**' -- into gold text,
    and *italic* spans -- used for show/publication titles like
    '*The Walking Dead*' -- into actual italics."""
    text = text.replace("$", "&#36;")
    text = _BOLD_RE.sub(r"<strong style='color:#D8B978;'>\1</strong>", text)
    return _ITALIC_RE.sub(r"<em>\1</em>", text)


def _render_context_section_html(section, note_key, si):
    """Render one section (heading + paragraphs, each with its own Verify
    button when that paragraph cites sources) as an HTML string. `si` is
    the section's absolute index in the *original* full sections list --
    callers that split the list (see format_websearch_context_split)
    must pass the original index, not a position within their slice, so
    verify-checkbox ids stay unique and stable."""
    parts = [f"<div class='context-heading'>{section['heading']}</div>"]
    # Every paragraph in "Possible Drivers" is a First/Second/Third-order
    # driver item -- indent them slightly so they read as sub-items under
    # the section heading rather than flush-left like the other sections.
    indent_style = "padding-left:1.2rem; font-size:0.88rem;" if section["heading"] == "Possible Drivers" else ""
    for pi, para in enumerate(section["paragraphs"]):
        parts.append(f"<p style='margin-bottom:0.3rem; {indent_style}'>{render_inline_markdown(para['text'])}</p>")
        if para["sources"]:
            links_html = "".join(
                f"<a href='{s['url']}' target='_blank' rel='noopener noreferrer' "
                f"style='display:block; color:#4A90D9; font-size:0.78rem; "
                f"margin-bottom:0.3rem; text-decoration:none;'>{s['label']}</a>"
                for s in para["sources"]
            )
            verify_id = f"verify_{note_key}_{si}_{pi}"
            parts.append(
                f"<div class='verify-para-wrap' style='{indent_style}'>"
                f"<input type='checkbox' id='{verify_id}'>"
                f"<label for='{verify_id}'>Verify</label>"
                f"<div class='verify-para-content'>{links_html}</div>"
                f"</div>"
            )
    return "".join(parts)


def format_websearch_context(sections, note_key):
    """Render the web-search-sourced context as HTML: each section (Prior
    Context / Current Earnings Release / Possible Drivers) as individual
    paragraphs, each with its own Verify button when that specific
    paragraph cites sources (paragraphs with no citation get none)."""
    long_html = "".join(_render_context_section_html(s, note_key, si) for si, s in enumerate(sections))
    return f"<div class='format-body'>{long_html}</div>"


def format_websearch_context_split(sections, note_key):
    """Same rendering as format_websearch_context(), split into (pre,
    post) HTML strings -- each still wrapped in its own 'format-body'
    div -- at the "Possible Drivers" heading: pre is everything before
    it, post is "Possible Drivers" onward. Used in Data Visualization 2
    to align "Possible Drivers" with the WSJ/DJNW columns' "Why The
    Stock Moved" heading via a shared CSS grid row, since those columns
    are otherwise independent-height Streamlit containers with no way to
    match a heading's vertical position to content of unpredictable
    length in a neighboring column. Every entry in group_context.json
    has a "Possible Drivers" section (verified across all 300 of them),
    so this doesn't need a no-such-heading fallback."""
    split_idx = next((i for i, s in enumerate(sections) if s["heading"] == "Possible Drivers"), len(sections))
    pre = "".join(_render_context_section_html(s, note_key, si) for si, s in enumerate(sections[:split_idx]))
    post = "".join(
        _render_context_section_html(s, note_key, split_idx + si)
        for si, s in enumerate(sections[split_idx:])
    )
    return f"<div class='format-body'>{pre}</div>", f"<div class='format-body'>{post}</div>"


# =============================================================================
# 5. CHARTS
# =============================================================================
# Two different Plotly charts, both indexed to 100 at the start of their
# window so the stock and S&P are comparable on one axis regardless of the
# stock's actual price level:
#
#   render_price_chart()         one per ticker, at the top of the page --
#                                 the full history across every quarter
#                                 covered, with a faint dotted line + hover
#                                 tooltip at each earnings date, and an
#                                 invisible click-to-jump overlay (built
#                                 separately below the chart, since Plotly
#                                 hover text isn't clickable).
#
#   build_quarter_visualize_fig()  one per quarter, only rendered when its
#                                 "Visualize" toggle is opened -- a zoomed
#                                 ~2-quarter window centered on that
#                                 specific earnings date, with a circle
#                                 marker + label on the report day and a
#                                 boxed text summary of what was already
#                                 known coming in.
#
# sp_return_2day() is a small shared helper both charts use to compute the
# S&P's own 2-day move around a given earnings date, the same way the
# dataset's own ret_2day is computed for the stock.
def sp_return_2day(sp_df_sorted, earnings_date):
    """S&P 500 % change from the first trading day on/after earnings_date to
    two trading days later -- the S&P's counterpart to the stock's own
    ret_2day, computed from the same daily-close series used for the chart."""
    on_or_after = sp_df_sorted[sp_df_sorted["date"] >= earnings_date]
    if on_or_after.empty:
        return None
    start_pos = on_or_after.index[0]
    end_pos = start_pos + 2
    if end_pos >= len(sp_df_sorted):
        return None
    start_price = sp_df_sorted.iloc[start_pos]["close"]
    end_price = sp_df_sorted.iloc[end_pos]["close"]
    return (end_price / start_price - 1) * 100


def excess_return_str(stock_ret_pct, sp_ret_pct):
    """Stock's 2-day return in excess of the S&P's own 2-day return over the
    same window -- how far the stock outperformed (positive) or
    underperformed (negative) the market, isolating the stock-specific move
    from whatever the broader market did on the same days."""
    if sp_ret_pct is None:
        return "n/a"
    return f"{stock_ret_pct - sp_ret_pct:+.2f}%"


def abnormal_return_str(market_model_info):
    """Formats the "market_model" half of one entry from
    abnormal_returns.json / group_abnormal_returns.json (computed by
    compute_abnormal_returns.py -- beta-adjusted 2-day abnormal return,
    standardized into a z-score by that stock's own historical volatility,
    so it's comparable across tickers of very different normal
    volatility). Returns "n/a" when there wasn't enough price history to
    estimate it (e.g. a stock's first couple of quarters after IPO)."""
    if not market_model_info:
        return "n/a"
    return f"{market_model_info['abnormal_return_pct']:+.2f}% ({market_model_info['z_score']:+.2f}σ)"


def market_adjusted_z_suffix(market_adjusted_info):
    """Formats the "market_adjusted" half of one entry (the simpler
    Brown-and-Warner-style method: raw stock-minus-S&P excess return,
    standardized by that stock's own historical excess-return volatility
    instead of a beta regression) as a short " (+N.NNσ)" suffix to
    append after an already-displayed raw excess-return % -- its
    excess_return_pct is the same number as that display, just recomputed
    independently as a consistency check. Empty string if unavailable."""
    if not market_adjusted_info:
        return ""
    return f" ({market_adjusted_info['z_score']:+.2f}σ)"


def render_price_chart(ticker, price_history, quarters_df):
    if price_history is None or ticker not in price_history.get("tickers", {}):
        st.info("No price history available for this ticker.")
        return

    entry = price_history["tickers"][ticker]
    stock_df = pd.DataFrame(entry["series"])
    sp_df = pd.DataFrame(price_history["sp500"])
    if stock_df.empty or sp_df.empty:
        st.info("No price history available for this ticker.")
        return

    stock_df["date"] = pd.to_datetime(stock_df["date"])
    sp_df["date"] = pd.to_datetime(sp_df["date"])

    window_start = pd.to_datetime(entry["window_start"])
    window_end = pd.to_datetime(entry["window_end"])
    sp_df = sp_df[(sp_df["date"] >= window_start) & (sp_df["date"] <= window_end)].reset_index(drop=True)

    # Index both series to 100 at the start of the padded window so they're
    # comparable on one axis regardless of the stock's actual price level.
    stock_indexed = stock_df["close"] / stock_df["close"].iloc[0] * 100
    sp_indexed = sp_df["close"] / sp_df["close"].iloc[0] * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=stock_df["date"], y=stock_indexed,
        name=ticker, line=dict(color="#FFD700", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=sp_df["date"], y=sp_indexed,
        name="S&P 500", line=dict(color="#4A90D9", width=2),
    ))

    # ── Faint dotted vertical line at each earnings date, with the date and
    # quarter shown in a gold tooltip on hover. (A chart line's own pixel
    # opacity can't be changed purely by hovering in Plotly -- the tooltip is
    # the "made more visible" signal here.) ──
    y_all = pd.concat([stock_indexed, sp_indexed])
    y_min, y_max = y_all.min(), y_all.max()
    y_pad = (y_max - y_min) * 0.08
    for _, qrow in quarters_df.iterrows():
        edt = qrow["earnings_date"]
        if edt < window_start or edt > window_end:
            continue
        sp_ret = sp_return_2day(sp_df, edt)
        sp_ret_str = f"{sp_ret:+.2f}%" if sp_ret is not None else "n/a"
        label = (
            f"{qrow['fiscal_yearquarter'].upper()} — {edt.strftime('%Y-%m-%d')}<br>"
            f"2-day % change<br>"
            f"{ticker}: {qrow['ret_2day'] * 100:+.2f}%  |  S&P: {sp_ret_str}"
        )
        fig.add_trace(go.Scatter(
            x=[edt, edt], y=[y_min - y_pad, y_max + y_pad],
            mode="lines",
            line=dict(color="rgba(255,215,0,0.35)", width=1, dash="dot"),
            hoverinfo="text",
            hovertext=label,
            showlegend=False,
        ))

    CHART_HEIGHT = 600
    fig.update_layout(
        height=CHART_HEIGHT,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#D6E4F0", family="Cormorant Garamond, serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(gridcolor="rgba(74,144,217,0.15)"),
        yaxis=dict(gridcolor="rgba(74,144,217,0.15)", title="Indexed to 100 at window start"),
        hoverlabel=dict(bgcolor="#1A3A5C", bordercolor="#FFD700", font=dict(color="#FFD700", size=13)),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Invisible hover zones positioned over the chart, one per earnings
    # date, at the same fractional x-position as its dotted line. Each is
    # transparent until hovered, at which point a real clickable date label
    # (a genuine <a href="#anchor">, not a JS scroll trick) fades in. Pulled
    # up over the chart just rendered above via a negative top margin.
    # Horizontal position is approximate -- it assumes fixed left/right chart
    # margins for the y-axis label, which can be a little off; each zone is
    # made generously wide (36px) specifically to absorb that imprecision. ──
    window_span_days = (window_end - window_start).days or 1
    LEFT_MARGIN_PX = 55
    RIGHT_MARGIN_PX = 15

    zones_html = ""
    for _, qrow in quarters_df.iterrows():
        edt = qrow["earnings_date"]
        if edt < window_start or edt > window_end:
            continue
        frac = (edt - window_start).days / window_span_days
        sp_ret = sp_return_2day(sp_df, edt)
        sp_ret_str = f"{sp_ret:+.2f}%" if sp_ret is not None else "n/a"
        label = (
            f"{qrow['fiscal_yearquarter'].upper()} · {edt.strftime('%Y-%m-%d')}<br>"
            f"2-day % change<br>"
            f"{ticker}: {qrow['ret_2day'] * 100:+.2f}%  |  S&P: {sp_ret_str}"
        )
        href = f"#{anchor_id(ticker, qrow['fiscal_yearquarter'])}"
        zones_html += (
            f"<div class='hoverzone' style='left: calc({LEFT_MARGIN_PX}px + "
            f"(100% - {LEFT_MARGIN_PX + RIGHT_MARGIN_PX}px) * {frac:.5f});'>"
            f"<a href='{href}' class='hoverzone-label'>{label}</a>"
            f"<div class='hoverzone-hint'>Click to jump to this quarter</div>"
            f"</div>"
        )

    st.html(
        f"""
        <style>
        .hoverzone-container {{
            position: relative;
            height: {CHART_HEIGHT - 40}px;
            margin-top: -{CHART_HEIGHT - 20}px;
            margin-bottom: 20px;
            pointer-events: none;
        }}
        .hoverzone {{
            position: absolute;
            top: 0; bottom: 0;
            width: 36px;
            margin-left: -18px;
            pointer-events: auto;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
        }}
        .hoverzone-label {{
            opacity: 0;
            transition: opacity 0.15s ease;
            color: #FFD700;
            background: #1A3A5C;
            border: 1px solid #FFD700;
            font-size: 0.7rem;
            line-height: 1.5;
            text-align: center;
            padding: 4px 8px;
            border-radius: 2px;
            text-decoration: none;
            margin-top: 6px;
            white-space: nowrap;
            font-family: 'Cormorant Garamond', serif;
        }}
        .hoverzone-hint {{
            opacity: 0;
            transition: opacity 0.15s ease;
            color: #A9C3DE;
            font-style: italic;
            font-size: 0.65rem;
            margin-top: 4px;
            white-space: nowrap;
            font-family: 'Cormorant Garamond', serif;
        }}
        .hoverzone:hover .hoverzone-label {{ opacity: 1; }}
        .hoverzone:hover .hoverzone-hint {{ opacity: 1; }}
        </style>
        <div class='hoverzone-container'>{zones_html}</div>
        """
    )


def build_quarter_visualize_fig(ticker, price_history, quarters_df, row_idx, context_summary_text=None):
    """Zoomed stock-vs-S&P chart for a single quarter: a fixed ~2-quarter
    window (roughly 3 months either side of the earnings date), clipped to
    the available padded price series, with the target quarter's earnings
    date marked by a faint dotted line and a circle marker on the price line
    itself. Uses a fixed calendar window rather than the previous/next
    dataset row's earnings date because this dataset's rows are not
    consecutive real quarters -- adjacent rows can be a year or more apart."""
    if price_history is None or ticker not in price_history.get("tickers", {}):
        return None

    entry = price_history["tickers"][ticker]
    stock_df = pd.DataFrame(entry["series"])
    sp_df = pd.DataFrame(price_history["sp500"])
    if stock_df.empty or sp_df.empty:
        return None

    stock_df["date"] = pd.to_datetime(stock_df["date"])
    sp_df["date"] = pd.to_datetime(sp_df["date"])

    window_start_full = pd.to_datetime(entry["window_start"])
    window_end_full = pd.to_datetime(entry["window_end"])

    target_row = quarters_df.iloc[row_idx]
    target_date = target_row["earnings_date"]
    start_date = max(target_date - pd.DateOffset(months=3), window_start_full)
    end_date = min(target_date + pd.DateOffset(months=3), window_end_full)

    stock_win = stock_df[(stock_df["date"] >= start_date) & (stock_df["date"] <= end_date)].reset_index(drop=True)
    sp_win = sp_df[(sp_df["date"] >= start_date) & (sp_df["date"] <= end_date)].reset_index(drop=True)
    if stock_win.empty or sp_win.empty:
        return None

    stock_indexed = stock_win["close"] / stock_win["close"].iloc[0] * 100
    sp_indexed = sp_win["close"] / sp_win["close"].iloc[0] * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=stock_win["date"], y=stock_indexed,
        name=ticker, line=dict(color="#FFD700", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=sp_win["date"], y=sp_indexed,
        name="S&P 500", line=dict(color="#4A90D9", width=2),
    ))

    y_all = pd.concat([stock_indexed, sp_indexed])
    y_min, y_max = y_all.min(), y_all.max()
    y_pad = (y_max - y_min) * 0.08 if y_max > y_min else 1

    sp_ret = sp_return_2day(sp_win, target_date)
    sp_ret_str = f"{sp_ret:+.2f}%" if sp_ret is not None else "n/a"
    label = (
        f"{target_row['fiscal_yearquarter'].upper()} — {target_date.strftime('%Y-%m-%d')}<br>"
        f"2-day % change<br>"
        f"{ticker}: {target_row['ret_2day'] * 100:+.2f}%  |  S&P: {sp_ret_str}"
    )
    fig.add_trace(go.Scatter(
        x=[target_date, target_date], y=[y_min - y_pad, y_max + y_pad],
        mode="lines",
        line=dict(color="rgba(255,215,0,0.35)", width=1, dash="dot"),
        hoverinfo="text",
        hovertext=label,
        showlegend=False,
    ))

    # ── Circle marker directly on the stock price line at the earnings date,
    # with a text label above it, so the report day reads as an event on the
    # price line itself rather than only a vertical line. ──
    on_or_after = stock_win[stock_win["date"] >= target_date]
    if not on_or_after.empty:
        marker_pos = on_or_after.index[0]
        marker_x = stock_win.loc[marker_pos, "date"]
        marker_y = stock_indexed.loc[marker_pos]
        fig.add_trace(go.Scatter(
            x=[marker_x], y=[marker_y],
            mode="markers",
            marker=dict(size=14, color="#FFD700", line=dict(color="#0E2040", width=2)),
            hoverinfo="text",
            hovertext=label,
            showlegend=False,
        ))
        fig.add_annotation(
            x=marker_x, y=marker_y,
            text="Earnings report",
            showarrow=True, arrowhead=0, arrowcolor="#FFD700", ax=0, ay=-32,
            font=dict(color="#FFD700", size=11, family="Cormorant Garamond, serif"),
            bgcolor="rgba(14,32,64,0.9)", bordercolor="#FFD700", borderwidth=1, borderpad=4,
        )

    # ── Compact context-summary box, placed in whichever top/bottom-left
    # corner is empty of price line at the start of the window (checked
    # against where the series opens relative to the y-range's midpoint) so
    # it doesn't sit on top of the lines. ──
    if context_summary_text:
        opening_val = stock_indexed.iloc[0]
        y_mid = (y_min + y_max) / 2
        box_top = opening_val < y_mid
        # Plotly's annotation `width` is meant to auto-wrap text, but is
        # unreliable on long unbroken strings -- it was clipping to a single
        # line instead of reflowing. Breaking the text into lines ourselves
        # guarantees wrapping regardless of Plotly's own wrap behavior.
        wrapped_text = "<br>".join(textwrap.wrap(context_summary_text, width=58))
        fig.add_annotation(
            xref="paper", yref="paper",
            x=0.01, y=0.98 if box_top else 0.02,
            xanchor="left", yanchor="top" if box_top else "bottom",
            text=wrapped_text,
            showarrow=False,
            align="left",
            bgcolor="rgba(14,32,64,0.92)",
            bordercolor="#FFD700", borderwidth=1, borderpad=8,
            font=dict(color="#D6E4F0", size=13, family="Cormorant Garamond, serif"),
        )

    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#D6E4F0", family="Cormorant Garamond, serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(gridcolor="rgba(74,144,217,0.15)"),
        yaxis=dict(gridcolor="rgba(74,144,217,0.15)", title="Indexed to 100 at window start"),
        hoverlabel=dict(bgcolor="#1A3A5C", bordercolor="#FFD700", font=dict(color="#FFD700", size=13)),
    )
    return fig


# =============================================================================
# 6. MAIN PAGE LAYOUT
# =============================================================================
# Everything below this point is the actual Streamlit script body: it runs
# top to bottom on every rerun (every button click, every checkbox toggle
# handled purely by CSS doesn't trigger this -- but selecting a different
# ticker in the nav bar does). Roughly, in order:
#   - load all the data (cached, so this is cheap after the first run)
#   - header (logo or placeholder title)
#   - ticker nav bar (17 buttons, one row, click to switch selected_ticker)
#   - the selected ticker's full-history chart
#   - a loop over that ticker's quarters, each rendering:
#       "Visualize" chart toggle, then left/right columns
#       (Contextualized interpretation | Generated text)

df = load_data(_mtime(DATA_PATH))
price_history = load_price_history(_mtime(PRICE_HISTORY_PATH))
abnormal_returns_lookup = load_abnormal_returns(_mtime(ABNORMAL_RETURNS_PATH))
bullets_lookup = load_bullets(_mtime(BULLETS_PATH))
sources_lookup = load_sources(_mtime(SOURCES_PATH))
context_summaries_lookup = load_context_summaries(_mtime(CONTEXT_SUMMARIES_PATH))
websearch_long_lookup = load_websearch_long(_mtime(WEBSEARCH_LONG_PATH))
company_info_lookup = load_company_info(_mtime(COMPANY_INFO_PATH))
comparative_answers_lookup = load_comparative_answers(_mtime(COMPARATIVE_ANSWERS_PATH))
group_coverage_accuracy_lookup = load_group_coverage_accuracy(_mtime(GROUP_COVERAGE_ACCURACY_PATH))
notes_lookup = load_notes(_mtime(NOTES_PATH))
group_df = load_group_returns(_mtime(GROUP_RETURNS_PATH))
group3_band_observations = load_group3_band_observations(_mtime(GROUP_RETURNS_PATH))
group4_band_observations = load_group4_band_observations(_mtime(GROUP_RETURNS_PATH))
group4_price_history = load_group4_price_history(_mtime(GROUP4_PRICE_HISTORY_PATH))
group5_band_observations = load_group5_band_observations(_mtime(GROUP_RETURNS_PATH))
group5_price_history = load_group5_price_history(_mtime(GROUP5_PRICE_HISTORY_PATH))
group6_band_observations = load_group6_band_observations(_mtime(GROUP_RETURNS_PATH))
group6_price_history = load_group6_price_history(_mtime(GROUP6_PRICE_HISTORY_PATH))
group_price_history = load_group_price_history(_mtime(GROUP_PRICE_HISTORY_PATH))
group_context_lookup = load_group_context(_mtime(GROUP_CONTEXT_PATH))
group_abnormal_returns_lookup = load_group_abnormal_returns(_mtime(GROUP_ABNORMAL_RETURNS_PATH))
group4_abnormal_returns_lookup = load_group4_abnormal_returns(_mtime(GROUP4_ABNORMAL_RETURNS_PATH))
group5_abnormal_returns_lookup = load_group5_abnormal_returns(_mtime(GROUP5_ABNORMAL_RETURNS_PATH))
group6_abnormal_returns_lookup = load_group6_abnormal_returns(_mtime(GROUP6_ABNORMAL_RETURNS_PATH))
group_wsj_coverage_lookup = load_group_wsj_coverage(_mtime(GROUP_WSJ_COVERAGE_PATH))
group_djnw_coverage_lookup = load_group_djnw_coverage(_mtime(GROUP_DJNW_COVERAGE_PATH))
group_massive_benzinga_coverage_lookup = load_group_massive_benzinga_coverage(
    _mtime(GROUP_MASSIVE_BENZINGA_COVERAGE_PATH)
)
group_alphanews_coverage_lookup = load_group_alphanews_coverage(_mtime(GROUP_ALPHANEWS_COVERAGE_PATH))
massive_benzinga_coverage_lookup = load_massive_benzinga_coverage(
    _mtime(MASSIVE_BENZINGA_COVERAGE_PATH)
)
massive_news_coverage_lookup = load_massive_news_coverage(_mtime(MASSIVE_NEWS_COVERAGE_PATH))
stocknews_coverage_lookup = load_stocknews_coverage(_mtime(STOCKNEWS_COVERAGE_PATH))
group4_stocknews_v2_lookup = load_group4_stocknews_v2(
    (
        _mtime(GROUP4_STOCKNEWS_V2_CLAUDE_PATH),
        _mtime(GROUP4_STOCKNEWS_V2_REBUILD_PATH),
        tuple(_mtime(p) for p in GROUP4_STOCKNEWS_V2_CODEX_SHARD_PATHS),
    )
)
viz45_chatgpt_coverage_lookup = load_viz45_chatgpt_coverage(
    _mtime(VIZ45_CHATGPT_COVERAGE_PATH)
)
viz2_chatgpt_coverage_lookup = load_viz2_chatgpt_coverage(
    _mtime(VIZ2_CHATGPT_COVERAGE_PATH)
)
# The ChatGPT pilot was generated from the cached Massive/Benzinga articles
# using the prior RA's LLM-reasoning instructions.  Overlay only its three
# selected large-cap tickers; every other Data Viz 2 observation keeps the
# existing deterministic Massive/Benzinga coverage.
group_massive_benzinga_display_lookup = {
    **group_massive_benzinga_coverage_lookup,
    **viz2_chatgpt_coverage_lookup,
}
group_pd_categories_lookup = load_group_pd_categories(_mtime(GROUP_PD_CATEGORIES_PATH))
group_first_order_categories_lookup = load_group_first_order_categories(
    _mtime(GROUP_FIRST_ORDER_CATEGORIES_PATH)
)

tickers = sorted(df["ticker"].unique())
ticker_labels = {
    t: f"{t} — {df.loc[df['ticker'] == t, 'company_name'].iloc[0]}"
    for t in tickers
}

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = tickers[0]

# ── Header: McGill logo if provided, otherwise a styled text title ──
logo_uri = logo_data_uri(_mtime(LOGO_PATH))
if logo_uri:
    st.html(
        f"<div style='display:flex; align-items:center; justify-content:center; "
        f"height:260px; padding:0;'><img src='{logo_uri}' style='height:220px; "
        f"image-rendering:-webkit-optimize-contrast;' /></div>"
    )
else:
    st.markdown(
        "<div style='font-family:Cormorant Garamond, serif; font-weight:500; "
        "font-size:2.6rem; letter-spacing:1px; color:#D6E4F0; text-align:center; "
        "margin-top:1rem;'>McGill University</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Drop your McGill logo PNG at assets/mcgill_logo.png to replace this placeholder title.",
    )

st.markdown("<hr class='gold-divider'/>", unsafe_allow_html=True)

# ── Top-level section selector: everything below (the 17-ticker dashboard)
# lives inside "Data Visualization"; "Comparative Study" is a placeholder
# for now. Uses st.stop() rather than wrapping the rest of the script in an
# indented if-block, since the ticker dashboard below is a large, already
# working block of code that doesn't need to be touched to gate it. ──
if "selected_section" not in st.session_state:
    st.session_state.selected_section = "Data Visualization"

sections = [
    "Data Visualization", "Data Visualization 2", "Data Visualization 3", "Data Visualization 4",
    "Data Visualization 5", "Data Visualization 6", "Data Visualization 7", "Comparative Study",
]
section_cols = st.columns(len(sections))
for col, sec in zip(section_cols, sections):
    with col:
        is_selected = st.session_state.selected_section == sec
        if st.button(
            sec,
            key=f"sectionbtn_{sec}",
            use_container_width=True,
            type="primary" if is_selected else "secondary",
        ):
            st.session_state.selected_section = sec

st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

if st.session_state.selected_section == "Data Visualization 2":
    # Three market-cap-banded ticker groups from the full returns panel (see
    # the GROUPS/GROUP_COMPANY_NAMES comment near the top of the file for
    # why this section can't show the left/right interpretation-vs-generated
    # comparison the way Data Visualization does -- that content doesn't
    # exist for these companies). Same nav-bar-then-chart presentation,
    # 10 observations per ticker (centered on the panel's 2010-2024
    # midpoint -- see middle_n_quarters) instead of every quarter, since
    # these tickers have 40-60 quarters each rather than ~14.
    if "selected_group" not in st.session_state:
        st.session_state.selected_group = list(GROUPS.keys())[0]

    group_cols = st.columns(len(GROUPS))
    for col, g in zip(group_cols, GROUPS.keys()):
        with col:
            is_selected = st.session_state.selected_group == g
            g_label = f"{g} ({GROUP_MARKET_CAP_LABELS[g]})"
            if st.button(
                g_label,
                key=f"groupbtn_{g}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_group = g
                # Selecting a new group resets the ticker nav to that
                # group's first ticker, same as switching sections does.
                st.session_state.selected_group_ticker = GROUPS[g][0]

    def _group_wsj_coverage_pct(group_name):
        # Denominator matches exactly what's shown per ticker below (the
        # middle 10 quarters), not the ticker's full quarter history, so
        # this percentage lines up with what a viewer can actually click
        # through and check.
        covered, total = 0, 0
        for t in GROUPS[group_name]:
            sub = middle_n_quarters(group_df[group_df["ticker"] == t], n=10)
            for _, row in sub.iterrows():
                total += 1
                entry = group_wsj_coverage_lookup.get(f"{t}_{row['fiscal_yearquarter']}")
                if entry and (entry.get("summary_analysis") or entry.get("why_moved")):
                    covered += 1
        return covered, total

    _cov_covered, _cov_total = _group_wsj_coverage_pct(st.session_state.selected_group)
    _cov_pct = (_cov_covered / _cov_total * 100) if _cov_total else 0.0
    st.markdown(
        f"<div style=\"text-align:center; color:#FFFFFF; font-size:1.6rem; font-style:italic; "
        f"font-family:'Cormorant Garamond', serif; margin:0.6rem 0;\">"
        f"WSJ coverage for {st.session_state.selected_group}: {_cov_pct:.0f}% "
        f"({_cov_covered} of {_cov_total} observations)</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    selected_group = st.session_state.selected_group
    group_tickers = GROUPS[selected_group]

    if "selected_group_ticker" not in st.session_state or st.session_state.selected_group_ticker not in group_tickers:
        st.session_state.selected_group_ticker = group_tickers[0]

    group_ticker_cols = st.columns(len(group_tickers))
    for col, t in zip(group_ticker_cols, group_tickers):
        with col:
            is_selected = st.session_state.selected_group_ticker == t
            if st.button(
                t,
                key=f"groupnavbtn_{t}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
                help=GROUP_COMPANY_NAMES.get(t, t),
            ):
                st.session_state.selected_group_ticker = t

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    g_ticker = st.session_state.selected_group_ticker
    g_sub_full = group_df[group_df["ticker"] == g_ticker].reset_index(drop=True)

    if g_sub_full.empty:
        st.info(f"No returns data available for {g_ticker}.")
        st.stop()

    g_sub_middle10 = middle_n_quarters(g_sub_full, n=10).reset_index(drop=True)
    g_company_name = GROUP_COMPANY_NAMES.get(g_ticker, g_ticker)
    g_period_start = g_sub_middle10["earnings_date"].min().strftime("%Y-%m-%d")
    g_period_end = g_sub_middle10["earnings_date"].max().strftime("%Y-%m-%d")

    (
        g_filter_spacer_l,
        g_filter_col1,
        g_filter_col2,
        g_filter_col3,
        g_filter_spacer_r,
    ) = st.columns([1, 2.3, 3, 3.8, 1])
    with g_filter_col1:
        g_filter_wsj = st.checkbox("Context Analysis + WSJ Coverage", key="g_filter_context_wsj")
    with g_filter_col2:
        g_filter_djnw = st.checkbox(
            "Context Analysis + Dow Jones Newswires Coverage",
            key="g_filter_context_djnw",
        )
    with g_filter_col3:
        g_filter_all_coverage = st.checkbox(
            "Context Analysis + WSJ Coverage + Dow Jones Newswires Coverage",
            key="g_filter_context_wsj_djnw",
        )

    st.markdown(
        f"<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>{g_ticker} — {g_company_name}</div>",
        unsafe_allow_html=True,
    )

    g_third_column_source = st.radio(
        "Third-column news source",
        ["Dow Jones Newswires", "Massive / Benzinga", "Alpha News Stream"],
        horizontal=True,
        key=f"g_third_column_source_{g_ticker}",
    )

    def _quarter_has_coverage(fiscal_yearquarter, need_wsj, need_djnw):
        # Unchecking all filters resets to "All" -- the default -- rather
        # than needing a separate "All" option, per how these were asked
        # for. Selecting both individual source filters is equivalent to the
        # combined context + WSJ + DJNW option.
        key = f"{g_ticker}_{fiscal_yearquarter}"
        if not group_context_lookup.get(key):
            return False
        if need_wsj:
            e = group_wsj_coverage_lookup.get(key)
            if not (e and (e.get("summary_analysis") or e.get("why_moved"))):
                return False
        if need_djnw:
            e = group_djnw_coverage_lookup.get(key)
            if not (e and (e.get("summary_analysis") or e.get("why_moved"))):
                return False
        return True

    if g_filter_all_coverage or (g_filter_wsj and g_filter_djnw):
        g_sub = g_sub_middle10[
            g_sub_middle10["fiscal_yearquarter"].apply(lambda fq: _quarter_has_coverage(fq, True, True))
        ].reset_index(drop=True)
    elif g_filter_djnw:
        g_sub = g_sub_middle10[
            g_sub_middle10["fiscal_yearquarter"].apply(lambda fq: _quarter_has_coverage(fq, False, True))
        ].reset_index(drop=True)
    elif g_filter_wsj:
        g_sub = g_sub_middle10[
            g_sub_middle10["fiscal_yearquarter"].apply(lambda fq: _quarter_has_coverage(fq, True, False))
        ].reset_index(drop=True)
    else:
        g_sub = g_sub_middle10

    st.markdown(
        f"<div style='text-align:center; color:rgba(214,228,240,0.7); font-size:0.85rem;'>"
        f"Showing {len(g_sub_middle10)} of {len(g_sub_full)} quarters covered ({g_sub_full['earnings_date'].min().strftime('%Y-%m-%d')} "
        f"to {g_sub_full['earnings_date'].max().strftime('%Y-%m-%d')}), centered on {g_period_start} – {g_period_end}</div>",
        unsafe_allow_html=True,
    )
    if g_filter_wsj or g_filter_djnw or g_filter_all_coverage:
        st.markdown(
            f"<div style='text-align:center; color:rgba(214,228,240,0.6); font-size:0.8rem;'>"
            f"{len(g_sub)} of these {len(g_sub_middle10)} match the selected coverage filter</div>",
            unsafe_allow_html=True,
        )
        if g_sub.empty:
            st.info("No quarters in this ticker's displayed window match the selected coverage filter.")

    render_price_chart(g_ticker, group_price_history, g_sub)

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    g_sp_df_for_headers = None
    if group_price_history is not None:
        g_sp_df_for_headers = pd.DataFrame(group_price_history["sp500"])
        g_sp_df_for_headers["date"] = pd.to_datetime(g_sp_df_for_headers["date"])
        g_sp_df_for_headers = g_sp_df_for_headers.sort_values("date").reset_index(drop=True)

    for g_idx, g_row in g_sub.iterrows():
        g_ret_pct = g_row["ret_2day"] * 100
        g_ret_str = f"{g_ret_pct:+.2f}%"

        g_sp_ret = sp_return_2day(g_sp_df_for_headers, g_row["earnings_date"]) if g_sp_df_for_headers is not None else None
        g_sp_ret_str = f"{g_sp_ret:+.2f}%" if g_sp_ret is not None else "n/a"
        g_excess_str = excess_return_str(g_ret_pct, g_sp_ret)
        g_note_key_lookup = f"{g_ticker}_{g_row['fiscal_yearquarter']}"
        g_abnormal_info = group_abnormal_returns_lookup.get(g_note_key_lookup, {})
        g_abnormal_str = abnormal_return_str(g_abnormal_info.get("market_model"))
        g_ma_z_suffix = market_adjusted_z_suffix(g_abnormal_info.get("market_adjusted"))

        st.markdown(
            f"<div class='quarter-header' style='text-align:center;'>{g_row['fiscal_yearquarter'].upper()} "
            f"&nbsp;|&nbsp; earnings {g_row['earnings_date'].strftime('%Y-%m-%d')}</div>"
            f"<div class='quarter-header' style='text-align:center;'>2-day return {g_ret_str} "
            f"&nbsp;|&nbsp; S&amp;P 2-day return {g_sp_ret_str}</div>"
            f"<div style=\"text-align:center; font-size:1.5rem; font-family:'Cormorant Garamond', serif; color:rgba(214,228,240,0.9); margin-bottom:0.3rem;\">"
            f"Excess return {g_excess_str}{g_ma_z_suffix} &nbsp;|&nbsp; "
            f"Beta-adjusted abnormal return {g_abnormal_str}</div>",
            unsafe_allow_html=True,
        )

        g_note_key = f"group2_{g_ticker}_{g_row['fiscal_yearquarter']}"
        with st.container(key=f"gviz_{g_note_key}"):
            g_viz_toggle_id = f"gviz_toggle_{g_note_key}"
            st.html(
                f"<input type='checkbox' id='{g_viz_toggle_id}' class='visualize-checkbox'>"
                f"<label for='{g_viz_toggle_id}' class='visualize-label'>Visualize</label>"
            )
            g_viz_fig = build_quarter_visualize_fig(g_ticker, group_price_history, g_sub, g_idx)
            if g_viz_fig is not None:
                st.plotly_chart(g_viz_fig, use_container_width=True, key=f"gviz_chart_{g_note_key}")

        g_context_key = f"{g_ticker}_{g_row['fiscal_yearquarter']}"

        # Rendered as one combined HTML block (a 3-row CSS grid), not three
        # independent st.columns() -- Streamlit columns are separate DOM
        # subtrees with independent heights, so there's no way to line up
        # "Possible Drivers" (left) with "Why The Stock Moved" (WSJ/DJNW)
        # when the preceding content's length varies per observation.
        # Row 1 = the three section headers (fixed). Row 2 = everything
        # before "Possible Drivers"/"Why The Stock Moved". Row 3 = those
        # sections onward. Each row auto-sizes to its tallest cell, so row
        # 3 always starts at the same Y in every column -- no JS needed.
        g_context_sections = group_context_lookup.get(g_context_key)
        if g_context_sections:
            g_left_pre, g_left_post = format_websearch_context_split(g_context_sections, g_note_key)
            g_left_post += coverage_accuracy_html(g_context_key, "contextual_analysis")
        else:
            g_left_pre = "<p><em>No contextual interpretation available for this observation.</em></p>"
            g_left_post = ""

        g_wsj_entry = group_wsj_coverage_lookup.get(g_context_key)
        if g_wsj_entry and (g_wsj_entry.get("summary_analysis") or g_wsj_entry.get("why_moved")):
            g_wsj_pre_inner = ""
            if g_wsj_entry.get("summary_analysis"):
                g_wsj_pre_inner = (
                    "<div class='context-heading'>Summary Analysis</div>"
                    f"<p style='margin-bottom:0.8rem; font-size:1.1rem; text-align:justify;'>"
                    f"{render_inline_markdown(g_wsj_entry['summary_analysis'])}</p>"
                )
            g_wsj_post_inner = ""
            if g_wsj_entry.get("why_moved"):
                g_wsj_post_inner = (
                    "<div class='context-heading'>Why The Stock Moved</div>"
                    f"<p style='margin-bottom:0.8rem; font-size:1.1rem; text-align:justify;'>"
                    f"{render_inline_markdown(g_wsj_entry['why_moved'])}</p>"
                )
            g_static_slug = GROUP_WSJ_STATIC_SLUGS.get(selected_group)
            g_wsj_post_inner += "".join(
                render_wsj_pdf_link_html(s, g_static_slug) for s in g_wsj_entry.get("sources", [])
            )
            g_wsj_post_inner += coverage_accuracy_html(g_context_key, "wsj")
            g_wsj_pre = f"<div class='format-body'>{g_wsj_pre_inner}</div>"
            g_wsj_post = f"<div class='format-body'>{g_wsj_post_inner}</div>"
        else:
            g_wsj_pre = "<p><em>No WSJ coverage found for this observation.</em></p>"
            g_wsj_post = ""

        g_third_column_lookups = {
            "Dow Jones Newswires": (group_djnw_coverage_lookup, "djnw", "No Dow Jones Newswires coverage"),
            "Massive / Benzinga": (
                group_massive_benzinga_display_lookup,
                "massive_benzinga",
                "No Massive / Benzinga coverage",
            ),
            "Alpha News Stream": (
                group_alphanews_coverage_lookup,
                "alphanews",
                "No Alpha News Stream coverage",
            ),
        }
        g_third_column_lookup, g_third_column_accuracy_key, g_third_column_none_text = g_third_column_lookups[
            g_third_column_source
        ]
        g_third_column_label = f"{g_third_column_source} Coverage"
        if g_third_column_source == "Massive / Benzinga" and g_context_key in viz2_chatgpt_coverage_lookup:
            g_third_column_label = "Massive / Benzinga Coverage — ChatGPT"

        g_djnw_entry = g_third_column_lookup.get(g_context_key)
        if g_djnw_entry and (g_djnw_entry.get("summary_analysis") or g_djnw_entry.get("why_moved")):
            g_djnw_pre_inner = ""
            if g_djnw_entry.get("summary_analysis"):
                g_djnw_pre_inner = (
                    "<div class='context-heading'>Summary Analysis</div>"
                    f"<p style='margin-bottom:0.8rem; font-size:1.1rem; text-align:justify;'>"
                    f"{render_inline_markdown(g_djnw_entry['summary_analysis'])}</p>"
                )
            g_djnw_post_inner = ""
            if g_djnw_entry.get("why_moved"):
                g_djnw_post_inner = (
                    "<div class='context-heading'>Why The Stock Moved</div>"
                    f"<p style='margin-bottom:0.8rem; font-size:1.1rem; text-align:justify;'>"
                    f"{render_inline_markdown(g_djnw_entry['why_moved'])}</p>"
                )
            g_djnw_post_inner += "".join(render_djnw_source_link_html(s) for s in g_djnw_entry.get("sources", []))
            g_djnw_post_inner += coverage_accuracy_html(g_context_key, g_third_column_accuracy_key)
            g_djnw_pre = f"<div class='format-body'>{g_djnw_pre_inner}</div>"
            g_djnw_post = f"<div class='format-body'>{g_djnw_post_inner}</div>"
        else:
            g_djnw_pre = f"<p><em>{g_third_column_none_text} found for this observation.</em></p>"
            g_djnw_post = ""

        st.html(
            "<div style='display:grid; grid-template-columns: 1fr 1fr 1fr; "
            "column-gap:2.5rem; align-items:start;'>"
            "<div style='text-align:center; font-weight:bold; grid-column:1; grid-row:1;'>"
            "Contextualized interpretation</div>"
            "<div style='text-align:center; font-weight:bold; grid-column:2; grid-row:1;'>WSJ Coverage</div>"
            f"<div style='text-align:center; font-weight:bold; grid-column:3; grid-row:1;'>"
            f"{g_third_column_label}</div>"
            f"<div style='grid-column:1; grid-row:2;'>{g_left_pre}</div>"
            f"<div style='grid-column:2; grid-row:2;'>{g_wsj_pre}</div>"
            f"<div style='grid-column:3; grid-row:2;'>{g_djnw_pre}</div>"
            f"<div style='grid-column:1; grid-row:3;'>{g_left_post}</div>"
            f"<div style='grid-column:2; grid-row:3;'>{g_wsj_post}</div>"
            f"<div style='grid-column:3; grid-row:3;'>{g_djnw_post}</div>"
            "</div>"
        )

        g_action_spacer_l, g_pdcat_btn_col, g_first_order_btn_col, g_action_spacer_r = st.columns(
            [1.5, 1, 1, 1.5]
        )
        with g_pdcat_btn_col:
            if st.button("PD Data Categories", key=f"pdcat_btn_{g_note_key}", use_container_width=True):
                _show_pd_categories_dialog(g_context_key)
        with g_first_order_btn_col:
            if st.button(
                "First Order Categories",
                key=f"first_order_btn_{g_note_key}",
                use_container_width=True,
            ):
                _show_first_order_categories_dialog(g_context_key)

        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    st.stop()

if st.session_state.selected_section == "Data Visualization 3":
    # 4 subgroups, none needing new ticker selection or market-cap
    # screening -- "Data Viz 1 (Post-2019)" reuses Data Visualization 1's
    # existing 17 tickers, filtered to observations from 2019 onward (when
    # StockNews API's news archive starts being usable); "Group 1"/"Group
    # 2"/"Group 3" reuse the exact same 30 tickers and market-cap bands as
    # Data Visualization 2 (see GROUPS/GROUP_MARKET_CAP_LABELS), just over
    # a different, non-overlapping observation window -- 2021-2023 instead
    # of the panel-midpoint-centered quarters shown there -- via
    # load_group3_band_observations().
    DATAVIZ3_GROUPS = {
        "Data Viz 1 (Post-2019)": list(tickers),
        "Group 1": GROUPS["Group 1"],
        "Group 2": GROUPS["Group 2"],
        "Group 3": GROUPS["Group 3"],
    }
    DATAVIZ3_BAND_LABELS = {
        "Data Viz 1 (Post-2019)": "existing tickers, 2019+",
        "Group 1": f"{GROUP_MARKET_CAP_LABELS['Group 1']}, 2021-2023",
        "Group 2": f"{GROUP_MARKET_CAP_LABELS['Group 2']}, 2021-2023",
        "Group 3": f"{GROUP_MARKET_CAP_LABELS['Group 3']}, 2021-2023",
    }
    DATAVIZ3_POST_2019_CUTOFF = pd.Timestamp("2019-01-01")

    if "selected_g3_group" not in st.session_state:
        st.session_state.selected_g3_group = list(DATAVIZ3_GROUPS)[0]

    g3_group_cols = st.columns(len(DATAVIZ3_GROUPS))
    for col, g in zip(g3_group_cols, DATAVIZ3_GROUPS.keys()):
        with col:
            is_selected = st.session_state.selected_g3_group == g
            g3_group_label = f"{g} ({DATAVIZ3_BAND_LABELS[g]})"
            if st.button(
                g3_group_label,
                key=f"g3_groupbtn_{g}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_g3_group = g
                g3_tickers_for_new_group = DATAVIZ3_GROUPS[g]
                if g3_tickers_for_new_group:
                    st.session_state.selected_g3_ticker = g3_tickers_for_new_group[0]

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    selected_g3_group = st.session_state.selected_g3_group
    g3_group_tickers = DATAVIZ3_GROUPS[selected_g3_group]

    if not g3_group_tickers:
        st.info(
            f"Candidate tickers for \"{selected_g3_group}\" ({DATAVIZ3_BAND_LABELS[selected_g3_group]}) "
            "haven't been selected yet -- this group is coming soon."
        )
        st.stop()

    if (
        "selected_g3_ticker" not in st.session_state
        or st.session_state.selected_g3_ticker not in g3_group_tickers
    ):
        st.session_state.selected_g3_ticker = g3_group_tickers[0]

    g3_ticker_cols = st.columns(len(g3_group_tickers))
    for col, t in zip(g3_ticker_cols, g3_group_tickers):
        with col:
            is_selected = st.session_state.selected_g3_ticker == t
            if st.button(
                t,
                key=f"g3_navbtn_{t}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_g3_ticker = t

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    g3_ticker = st.session_state.selected_g3_ticker

    if selected_g3_group == "Data Viz 1 (Post-2019)":
        g3_sub = df[
            (df["ticker"] == g3_ticker) & (df["earnings_date"] >= DATAVIZ3_POST_2019_CUTOFF)
        ].reset_index(drop=True)
        g3_company_name = df[df["ticker"] == g3_ticker]["company_name"].iloc[0]
        g3_price_history = price_history
        g3_abnormal_lookup = abnormal_returns_lookup
    else:
        g3_sub = group3_band_observations[
            group3_band_observations["ticker"] == g3_ticker
        ].reset_index(drop=True)
        g3_company_name = GROUP_COMPANY_NAMES.get(g3_ticker, g3_ticker)
        g3_price_history = group_price_history
        g3_abnormal_lookup = group_abnormal_returns_lookup

    if g3_sub.empty:
        st.info(f"No post-2019 observations available for {g3_ticker}.")
        st.stop()

    st.markdown(
        f"<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>{g3_ticker} — {g3_company_name}</div>",
        unsafe_allow_html=True,
    )
    g3_period_start = g3_sub["earnings_date"].min().strftime("%Y-%m-%d")
    g3_period_end = g3_sub["earnings_date"].max().strftime("%Y-%m-%d")
    st.markdown(
        f"<div style='text-align:center; color:rgba(214,228,240,0.7); font-size:0.85rem;'>"
        f"{len(g3_sub)} observations, {g3_period_start} to {g3_period_end}</div>",
        unsafe_allow_html=True,
    )

    render_price_chart(g3_ticker, g3_price_history, g3_sub)

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    g3_sp_df_for_headers = None
    if g3_price_history is not None:
        g3_sp_df_for_headers = pd.DataFrame(g3_price_history["sp500"])
        g3_sp_df_for_headers["date"] = pd.to_datetime(g3_sp_df_for_headers["date"])
        g3_sp_df_for_headers = g3_sp_df_for_headers.sort_values("date").reset_index(drop=True)

    for g3_idx, g3_row in g3_sub.iterrows():
        g3_note_key = f"{g3_row['ticker']}_{g3_row['fiscal_yearquarter']}"
        g3_ret_pct = g3_row["ret_2day"] * 100
        g3_ret_str = f"{g3_ret_pct:+.2f}%"
        g3_sp_ret = (
            sp_return_2day(g3_sp_df_for_headers, g3_row["earnings_date"])
            if g3_sp_df_for_headers is not None
            else None
        )
        g3_sp_ret_str = f"{g3_sp_ret:+.2f}%" if g3_sp_ret is not None else "n/a"
        g3_excess_str = excess_return_str(g3_ret_pct, g3_sp_ret)
        g3_abnormal_info = g3_abnormal_lookup.get(g3_note_key, {})
        g3_abnormal_str = abnormal_return_str(g3_abnormal_info.get("market_model"))
        g3_ma_z_suffix = market_adjusted_z_suffix(g3_abnormal_info.get("market_adjusted"))

        st.markdown(
            f"<div class='quarter-header' style='text-align:center;'>{g3_row['fiscal_yearquarter'].upper()} "
            f"&nbsp;|&nbsp; earnings {g3_row['earnings_date'].strftime('%Y-%m-%d')}</div>"
            f"<div class='quarter-header' style='text-align:center;'>2-day return {g3_ret_str} "
            f"&nbsp;|&nbsp; S&amp;P 2-day return {g3_sp_ret_str}</div>"
            f"<div style=\"text-align:center; font-size:1.3rem; font-family:'Cormorant Garamond', serif; "
            f"color:rgba(214,228,240,0.9); margin-bottom:0.3rem;\">Excess return {g3_excess_str}{g3_ma_z_suffix} "
            f"&nbsp;|&nbsp; Beta-adjusted abnormal return {g3_abnormal_str}</div>",
            unsafe_allow_html=True,
        )

        with st.container(key=f"g3viz_{g3_note_key}"):
            g3_viz_toggle_id = f"g3viz_toggle_{g3_note_key}"
            st.html(
                f"<input type='checkbox' id='{g3_viz_toggle_id}' class='visualize-checkbox'>"
                f"<label for='{g3_viz_toggle_id}' class='visualize-label'>Visualize</label>"
            )
            g3_viz_fig = build_quarter_visualize_fig(g3_ticker, g3_price_history, g3_sub, g3_idx)
            if g3_viz_fig is not None:
                st.plotly_chart(g3_viz_fig, use_container_width=True, key=f"g3viz_chart_{g3_note_key}")

        g3_left, g3_right = st.columns(2, gap="large")
        with g3_left:
            st.markdown(
                "<div style='text-align:center; font-weight:bold;'>Selected Coverage</div>",
                unsafe_allow_html=True,
            )
            st.write("*No coverage available yet for this observation.*")
        with g3_right:
            st.markdown(
                "<div style='text-align:center; font-weight:bold;'>High-Tier Coverage</div>",
                unsafe_allow_html=True,
            )
            st.write("*No coverage available yet for this observation.*")

        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    st.stop()

if st.session_state.selected_section == "Data Visualization 4":
    # Focused copy of Data Visualization 1: only post-March-2019 earnings
    # observations for which the StockNews / Why Moved 2 pipeline retained at
    # least one quality article.  The three columns preserve Data Viz 1's
    # comparison while fixing StockNews as the coverage source.
    dv4_rows = df[df["earnings_date"] >= pd.Timestamp("2019-04-01")].copy()
    dv4_rows["note_key"] = dv4_rows["ticker"] + "_" + dv4_rows["fiscal_yearquarter"]
    dv4_rows = dv4_rows[dv4_rows["note_key"].isin(stocknews_coverage_lookup)].reset_index(drop=True)
    dv4_tickers = [ticker for ticker in tickers if ticker in set(dv4_rows["ticker"])]

    if not dv4_tickers:
        st.info("No post-March-2019 StockNews observations are available.")
        st.stop()

    dv4_nav_items = dv4_tickers + ["Data Analysis"]
    if "selected_dv4_ticker" not in st.session_state or st.session_state.selected_dv4_ticker not in dv4_nav_items:
        st.session_state.selected_dv4_ticker = dv4_tickers[0]

    dv4_nav_cols = st.columns(len(dv4_nav_items))
    for col, ticker in zip(dv4_nav_cols, dv4_nav_items):
        with col:
            selected = st.session_state.selected_dv4_ticker == ticker
            if st.button(
                ticker,
                key=f"dv4_navbtn_{ticker}",
                use_container_width=True,
                type="primary" if selected else "secondary",
                help=ticker_labels.get(ticker, "Analyze StockNews categories and abnormal returns"),
            ):
                st.session_state.selected_dv4_ticker = ticker

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    dv4_ticker = st.session_state.selected_dv4_ticker
    if dv4_ticker == "Data Analysis":
        selected_analysis_categories = st.multiselect(
            "Categories included in ranking",
            WHY_MOVED_2_CATEGORIES,
            default=WHY_MOVED_2_CATEGORIES,
            key="dv4_analysis_categories",
            help=(
                "Unselect any category to remove it from both the numerator and denominator. "
                "Immediate reaction divergence identifies observations where the article's "
                "immediate reaction and the computed two-day return have opposite signs."
            ),
        )
        analysis_rows = []
        analysis_excluded_no_category = 0
        for _, analysis_row in dv4_rows.iterrows():
            analysis_key = analysis_row["note_key"]
            category_cells = stocknews_coverage_lookup[analysis_key].get("categories", {})
            active_cells = [
                category_cells.get(category)
                for category in selected_analysis_categories
                if category_cells.get(category)
            ]
            positive_count = sum(cell.get("direction") == "positive" for cell in active_cells)
            negative_count = sum(cell.get("direction") == "negative" for cell in active_cells)
            explicit_count = sum(cell.get("attribution") == "explicit" for cell in active_cells)
            implicit_count = sum(cell.get("attribution") == "implicit" for cell in active_cells)
            active_count = len(active_cells)
            if active_count == 0:
                # Has StockNews coverage, but none of the selected categories
                # were tied to the move -- excluded rather than plotted at a
                # neutral score, since a 0.0 category score would otherwise
                # be indistinguishable from a genuinely neutral/mixed result.
                analysis_excluded_no_category += 1
                continue
            category_sum = sum(
                (1 if cell.get("direction") == "positive" else -1)
                * (2 if cell.get("attribution") == "explicit" else 1)
                for cell in active_cells
            )
            category_score = category_sum / active_count
            return_metrics = abnormal_returns_lookup.get(analysis_key, {})
            market_model = return_metrics.get("market_model") or {}
            market_adjusted = return_metrics.get("market_adjusted") or {}
            analysis_rows.append(
                {
                    "note_key": analysis_key,
                    "ticker": analysis_row["ticker"],
                    "quarter": analysis_row["fiscal_yearquarter"].upper(),
                    "earnings_date": analysis_row["earnings_date"],
                    "category_score": category_score,
                    "category_sum": category_sum,
                    "active_categories": active_count,
                    "positive_categories": positive_count,
                    "negative_categories": negative_count,
                    "explicit_categories": explicit_count,
                    "implicit_categories": implicit_count,
                    "abnormal_return_pct": market_model.get("abnormal_return_pct"),
                    "abnormal_z_score": market_model.get("z_score"),
                    "excess_return_pct": market_adjusted.get("excess_return_pct"),
                    "excess_z_score": market_adjusted.get("z_score"),
                }
            )

        analysis_df = pd.DataFrame(analysis_rows)

        if analysis_df.empty:
            st.info("No StockNews observations with an active category in the selected set.")
            st.stop()

        return_method = st.radio(
            "Return measure",
            ["Excess return", "Abnormal return"],
            horizontal=True,
            key="dv4_analysis_return_method",
        )
        if return_method == "Excess return":
            z_column = "excess_z_score"
            return_column = "excess_return_pct"
            method_description = "market-adjusted excess return"
        else:
            z_column = "abnormal_z_score"
            return_column = "abnormal_return_pct"
            method_description = "beta-adjusted abnormal return"

        absolute_filter_col1, absolute_filter_col2, absolute_filter_col3 = st.columns([1.2, 1, 1])
        with absolute_filter_col1:
            absolute_filter_mode = st.radio(
                "Absolute graph Z-score filter",
                ["Include", "Exclude"],
                horizontal=True,
                key="dv4_absolute_z_filter_mode",
            )
        with absolute_filter_col2:
            absolute_z_lower = st.number_input(
                "Lower Z-score", value=-10.0, step=0.5, key="dv4_absolute_z_lower"
            )
        with absolute_filter_col3:
            absolute_z_upper = st.number_input(
                "Upper Z-score", value=10.0, step=0.5, key="dv4_absolute_z_upper"
            )
        absolute_z_min, absolute_z_max = sorted((absolute_z_lower, absolute_z_upper))

        chart_df = analysis_df.dropna(subset=[z_column]).copy()
        absolute_inside = chart_df[z_column].between(absolute_z_min, absolute_z_max, inclusive="both")
        chart_df = chart_df[absolute_inside if absolute_filter_mode == "Include" else ~absolute_inside].copy()
        chart_df["absolute_z_score"] = chart_df[z_column].abs()

        st.markdown(
            "<div class='quarter-header' style='font-size:1.5rem; text-align:center;'>"
            f"Absolute {return_method} Z-Scores and StockNews Category Ranking</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='max-width:920px; margin:0 auto 1rem auto; text-align:center; "
            "color:rgba(214,228,240,0.82);'>"
            "Category score = signed weighted category sum ÷ total active categories. "
            "Explicit categories receive twice the numerator weight (±2) of implicit categories (±1). "
            "Only categories selected above enter the numerator and denominator. "
            "The score ranges from −2 to +2. Observations with StockNews coverage but no active "
            "category are excluded from both graphs.</div>",
            unsafe_allow_html=True,
        )

        analysis_fig = go.Figure()
        for analysis_ticker in sorted(chart_df["ticker"].unique()):
            ticker_points = chart_df[chart_df["ticker"] == analysis_ticker]
            customdata = [
                [
                    row.note_key,
                    row.quarter,
                    row.earnings_date.strftime("%Y-%m-%d"),
                    row.category_sum,
                    row.active_categories,
                    row.positive_categories,
                    row.negative_categories,
                    getattr(row, z_column),
                    getattr(row, return_column),
                    row.explicit_categories,
                    row.implicit_categories,
                ]
                for row in ticker_points.itertuples()
            ]
            analysis_fig.add_trace(
                go.Scatter(
                    x=ticker_points["category_score"],
                    y=ticker_points["absolute_z_score"],
                    mode="markers",
                    name=analysis_ticker,
                    customdata=customdata,
                    marker={"size": 10, "opacity": 0.78, "line": {"width": 0.6, "color": "#D6E4F0"}},
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Earnings: %{customdata[2]}<br>"
                        "Absolute Z-score: %{y:.2f}σ<br>"
                        "Signed Z-score: %{customdata[7]:+.2f}σ<br>"
                        f"{method_description.capitalize()}: %{{customdata[8]:+.2f}}%<br>"
                        "Category score: %{x:.3f} "
                        "(%{customdata[3]}/%{customdata[4]})<br>"
                        "Positive: %{customdata[5]} | Negative: %{customdata[6]}<br>"
                        "Explicit: %{customdata[9]} | Implicit: %{customdata[10]}"
                        "<extra></extra>"
                    ),
                )
            )
        if len(chart_df) >= 3 and chart_df["category_score"].nunique() >= 3:
            regression_x = np.linspace(
                chart_df["category_score"].min(), chart_df["category_score"].max(), 200
            )
            regression_coefficients = np.polyfit(
                chart_df["category_score"], chart_df["absolute_z_score"], 2
            )
            regression_y = np.polyval(regression_coefficients, regression_x)
            fitted_y = np.polyval(regression_coefficients, chart_df["category_score"])
            residuals = np.asarray(chart_df["absolute_z_score"] - fitted_y, dtype=float)
            observed_x = np.asarray(chart_df["category_score"], dtype=float)
            local_x_half_window = 0.5
            local_std = []
            for point in regression_x:
                local_residuals = residuals[np.abs(observed_x - point) <= local_x_half_window]
                if len(local_residuals) < 3:
                    nearest = np.argsort(np.abs(observed_x - point))[:min(5, len(residuals))]
                    local_residuals = residuals[nearest]
                local_std.append(float(np.std(local_residuals, ddof=1)))
            local_std = np.asarray(local_std)
            analysis_fig.add_trace(
                go.Scatter(
                    x=regression_x,
                    y=regression_y + local_std,
                    mode="lines",
                    line={"width": 0},
                    hoverinfo="skip",
                    showlegend=False,
                    legendgroup="absolute-regression-band",
                )
            )
            analysis_fig.add_trace(
                go.Scatter(
                    x=regression_x,
                    y=regression_y - local_std,
                    mode="lines",
                    line={"width": 0},
                    fill="tonexty",
                    fillcolor="rgba(255,209,102,0.18)",
                    name="Local ±1 SD",
                    hoverinfo="skip",
                    legendgroup="absolute-regression-band",
                )
            )
            analysis_fig.add_trace(
                go.Scatter(
                    x=regression_x,
                    y=regression_y,
                    mode="lines",
                    name="Quadratic regression",
                    line={"color": "#FFD166", "width": 3},
                    hovertemplate="Quadratic regression<br>Category score: %{x:.3f}<br>Predicted |Z|: %{y:.2f}σ<extra></extra>",
                )
            )
        analysis_fig.add_vline(x=0, line_dash="dash", line_color="rgba(214,228,240,0.45)")
        analysis_fig.update_layout(
            xaxis_title="StockNews category ranking",
            yaxis_title=f"Absolute {method_description} Z-score (σ)",
            xaxis={"range": [-2.08, 2.08], "tickmode": "linear", "dtick": 0.5},
            hovermode="closest",
            legend_title_text="Ticker",
            height=650,
            margin={"l": 65, "r": 35, "t": 35, "b": 65},
        )
        st.plotly_chart(analysis_fig, use_container_width=True, key="dv4_category_abnormal_scatter")
        st.caption(
            f"{len(chart_df)} StockNews observations plotted. "
            f"{absolute_filter_mode} signed Z-scores from {absolute_z_min:+.2f}σ to {absolute_z_max:+.2f}σ. "
            "Regression band: local ±1 return SD using a ±0.5 category-ranking window. "
            f"{analysis_excluded_no_category} observations have StockNews coverage but no active "
            "category and are excluded from both graphs."
        )

        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)
        signed_filter_col1, signed_filter_col2, signed_filter_col3 = st.columns([1.2, 1, 1])
        with signed_filter_col1:
            signed_filter_mode = st.radio(
                "Signed graph Z-score filter",
                ["Include", "Exclude"],
                horizontal=True,
                key="dv4_signed_z_filter_mode",
            )
        with signed_filter_col2:
            signed_z_lower = st.number_input(
                "Lower Z-score", value=-10.0, step=0.5, key="dv4_signed_z_lower"
            )
        with signed_filter_col3:
            signed_z_upper = st.number_input(
                "Upper Z-score", value=10.0, step=0.5, key="dv4_signed_z_upper"
            )
        signed_z_min, signed_z_max = sorted((signed_z_lower, signed_z_upper))

        st.markdown(
            f"<div class='quarter-header' style='font-size:1.5rem; text-align:center;'>"
            f"Signed {return_method} Z-Scores and StockNews Category Ranking</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='max-width:920px; margin:0 auto 1rem auto; text-align:center; "
            "color:rgba(214,228,240,0.82);'>"
            "This graph uses the signed Z-score rather than its absolute value. Positive and negative "
            "standardized market reactions therefore appear above and below zero.</div>",
            unsafe_allow_html=True,
        )

        return_chart_df = analysis_df.dropna(subset=[z_column]).copy()
        signed_inside = return_chart_df[z_column].between(signed_z_min, signed_z_max, inclusive="both")
        return_chart_df = return_chart_df[
            signed_inside if signed_filter_mode == "Include" else ~signed_inside
        ].copy()
        return_fig = go.Figure()
        for analysis_ticker in sorted(return_chart_df["ticker"].unique()):
            ticker_points = return_chart_df[return_chart_df["ticker"] == analysis_ticker]
            customdata = [
                [
                    row.note_key,
                    row.quarter,
                    row.earnings_date.strftime("%Y-%m-%d"),
                    row.category_sum,
                    row.active_categories,
                    row.positive_categories,
                    row.negative_categories,
                    getattr(row, z_column),
                    row.explicit_categories,
                    row.implicit_categories,
                ]
                for row in ticker_points.itertuples()
            ]
            return_fig.add_trace(
                go.Scatter(
                    x=ticker_points["category_score"],
                    y=ticker_points[z_column],
                    mode="markers",
                    name=analysis_ticker,
                    customdata=customdata,
                    marker={"size": 10, "opacity": 0.78, "line": {"width": 0.6, "color": "#D6E4F0"}},
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Earnings: %{customdata[2]}<br>"
                        "Signed Z-score: %{y:+.2f}σ<br>"
                        "Category score: %{x:.3f} "
                        "(%{customdata[3]}/%{customdata[4]})<br>"
                        "Positive: %{customdata[5]} | Negative: %{customdata[6]}<br>"
                        "Explicit: %{customdata[8]} | Implicit: %{customdata[9]}"
                        "<extra></extra>"
                    ),
                )
            )
        if len(return_chart_df) >= 3 and return_chart_df["category_score"].nunique() >= 3:
            regression_x = np.linspace(
                return_chart_df["category_score"].min(), return_chart_df["category_score"].max(), 200
            )
            regression_coefficients = np.polyfit(
                return_chart_df["category_score"], return_chart_df[z_column], 2
            )
            regression_y = np.polyval(regression_coefficients, regression_x)
            fitted_y = np.polyval(regression_coefficients, return_chart_df["category_score"])
            residuals = np.asarray(return_chart_df[z_column] - fitted_y, dtype=float)
            observed_x = np.asarray(return_chart_df["category_score"], dtype=float)
            local_x_half_window = 0.5
            local_std = []
            for point in regression_x:
                local_residuals = residuals[np.abs(observed_x - point) <= local_x_half_window]
                if len(local_residuals) < 3:
                    nearest = np.argsort(np.abs(observed_x - point))[:min(5, len(residuals))]
                    local_residuals = residuals[nearest]
                local_std.append(float(np.std(local_residuals, ddof=1)))
            local_std = np.asarray(local_std)
            return_fig.add_trace(
                go.Scatter(
                    x=regression_x,
                    y=regression_y + local_std,
                    mode="lines",
                    line={"width": 0},
                    hoverinfo="skip",
                    showlegend=False,
                    legendgroup="signed-regression-band",
                )
            )
            return_fig.add_trace(
                go.Scatter(
                    x=regression_x,
                    y=regression_y - local_std,
                    mode="lines",
                    line={"width": 0},
                    fill="tonexty",
                    fillcolor="rgba(255,209,102,0.18)",
                    name="Local ±1 SD",
                    hoverinfo="skip",
                    legendgroup="signed-regression-band",
                )
            )
            return_fig.add_trace(
                go.Scatter(
                    x=regression_x,
                    y=regression_y,
                    mode="lines",
                    name="Quadratic regression",
                    line={"color": "#FFD166", "width": 3},
                    hovertemplate="Quadratic regression<br>Category score: %{x:.3f}<br>Predicted Z: %{y:+.2f}σ<extra></extra>",
                )
            )
        return_fig.add_hline(y=0, line_dash="dash", line_color="rgba(214,228,240,0.45)")
        return_fig.add_vline(x=0, line_dash="dash", line_color="rgba(214,228,240,0.45)")
        return_fig.update_layout(
            xaxis_title="StockNews category ranking",
            yaxis_title=f"Signed {method_description} Z-score (σ)",
            xaxis={"range": [-2.08, 2.08], "tickmode": "linear", "dtick": 0.5},
            hovermode="closest",
            legend_title_text="Ticker",
            height=650,
            margin={"l": 65, "r": 35, "t": 35, "b": 65},
        )
        st.plotly_chart(return_fig, use_container_width=True, key="dv4_category_return_scatter")
        st.caption(
            f"{len(return_chart_df)} StockNews observations plotted with the signed "
            f"{method_description} Z-score. {signed_filter_mode} signed Z-scores from "
            f"{signed_z_min:+.2f}σ to {signed_z_max:+.2f}σ. "
            "Regression band: local ±1 return SD using a ±0.5 category-ranking window."
        )
        st.stop()

    dv4_sub = dv4_rows[dv4_rows["ticker"] == dv4_ticker].reset_index(drop=True)
    dv4_company_name = dv4_sub["company_name"].iloc[0]
    dv4_period_start = dv4_sub["earnings_date"].min().strftime("%Y-%m-%d")
    dv4_period_end = dv4_sub["earnings_date"].max().strftime("%Y-%m-%d")

    st.markdown(
        f"<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>"
        f"{dv4_ticker} — {dv4_company_name}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='text-align:center; color:rgba(214,228,240,0.7); font-size:0.85rem;'>"
        f"{len(dv4_sub)} StockNews observations, {dv4_period_start} to {dv4_period_end}</div>",
        unsafe_allow_html=True,
    )

    render_price_chart(dv4_ticker, price_history, dv4_sub)
    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    dv4_sp_df = None
    if price_history is not None:
        dv4_sp_df = pd.DataFrame(price_history["sp500"])
        dv4_sp_df["date"] = pd.to_datetime(dv4_sp_df["date"])
        dv4_sp_df = dv4_sp_df.sort_values("date").reset_index(drop=True)

    for dv4_idx, dv4_row in dv4_sub.iterrows():
        dv4_note_key = dv4_row["note_key"]
        dv4_ret_pct = dv4_row["ret_2day"] * 100
        dv4_sp_ret = sp_return_2day(dv4_sp_df, dv4_row["earnings_date"]) if dv4_sp_df is not None else None
        dv4_sp_ret_str = f"{dv4_sp_ret:+.2f}%" if dv4_sp_ret is not None else "n/a"
        dv4_abnormal = abnormal_returns_lookup.get(dv4_note_key, {})

        st.markdown(
            f"<div class='quarter-header' style='text-align:center;'>{dv4_row['fiscal_yearquarter'].upper()} "
            f"&nbsp;|&nbsp; earnings {dv4_row['earnings_date'].strftime('%Y-%m-%d')}</div>"
            f"<div class='quarter-header' style='text-align:center;'>2-day return {dv4_ret_pct:+.2f}% "
            f"&nbsp;|&nbsp; S&amp;P 2-day return {dv4_sp_ret_str}</div>"
            f"<div style=\"text-align:center; font-size:1.5rem; font-family:'Cormorant Garamond', serif; "
            f"color:rgba(214,228,240,0.9); margin-bottom:0.3rem;\">"
            f"Excess return {excess_return_str(dv4_ret_pct, dv4_sp_ret)}"
            f"{market_adjusted_z_suffix(dv4_abnormal.get('market_adjusted'))} &nbsp;|&nbsp; "
            f"Beta-adjusted abnormal return {abnormal_return_str(dv4_abnormal.get('market_model'))}</div>",
            unsafe_allow_html=True,
        )

        dv4_context_summary = context_summaries_lookup.get(dv4_note_key)
        with st.container(key=f"dv4_viz_{dv4_note_key}"):
            dv4_toggle_id = f"dv4_viz_toggle_{dv4_note_key}"
            st.html(
                f"<input type='checkbox' id='{dv4_toggle_id}' class='visualize-checkbox'>"
                f"<label for='{dv4_toggle_id}' class='visualize-label'>Visualize</label>"
            )
            dv4_fig = build_quarter_visualize_fig(
                dv4_ticker, price_history, dv4_sub, dv4_idx, dv4_context_summary
            )
            if dv4_fig is not None:
                st.plotly_chart(dv4_fig, use_container_width=True, key=f"dv4_chart_{dv4_note_key}")

        dv4_context_col, dv4_generated_col, dv4_stocknews_col = st.columns(3, gap="large")
        dv4_websearch_sections = websearch_long_lookup.get(dv4_note_key)
        dv4_existing_note = notes_lookup.get(dv4_note_key, "")

        with dv4_context_col:
            st.markdown(
                "<div style='text-align:center; font-weight:bold;'>Contextualized interpretation</div>",
                unsafe_allow_html=True,
            )
            if dv4_websearch_sections:
                st.html(format_websearch_context(dv4_websearch_sections, dv4_note_key))
            elif dv4_existing_note:
                st.html(format_context_text(dv4_existing_note))
                dv4_sources = sources_lookup.get(dv4_note_key, [])
                if dv4_sources:
                    dv4_links = "".join(
                        f"<a href='{source['url']}' target='_blank' rel='noopener noreferrer' "
                        f"style='display:block; color:#4A90D9; font-size:0.82rem; "
                        f"margin-bottom:0.4rem; text-decoration:none;'>{source['label']}</a>"
                        for source in dv4_sources
                    )
                    dv4_verify_id = f"dv4_verify_{dv4_note_key}"
                    st.html(
                        f"<div class='verify-toggle-wrap'><input type='checkbox' id='{dv4_verify_id}'>"
                        f"<label for='{dv4_verify_id}'>Verify</label>"
                        f"<div class='verify-content'>{dv4_links}</div></div>"
                    )
            else:
                st.write("*No interpretation written yet for this quarter.*")

        with dv4_generated_col:
            st.markdown(
                "<div style='text-align:center; font-weight:bold;'>Generated text</div>",
                unsafe_allow_html=True,
            )
            dv4_paragraph = str(dv4_row["final_paragraph"]).replace("$", "&#36;")
            if dv4_websearch_sections:
                dv4_spacer = (
                    f"<div class='context-heading' style='visibility:hidden;'>"
                    f"{dv4_websearch_sections[0]['heading']}</div>"
                )
            elif dv4_existing_note:
                dv4_spacer = "<div class='context-heading' style='visibility:hidden;'>Prior Context</div>"
            else:
                dv4_spacer = ""
            st.html(f"{dv4_spacer}<p style='margin:0 0 0.6rem 0; text-align:justify;'>{dv4_paragraph}</p>")
            dv4_bullets = bullets_lookup.get((dv4_row["ticker"], dv4_row["fiscal_yearquarter"]), [])
            if dv4_bullets:
                st.html(
                    "<div style='display:flex; flex-direction:column; align-items:center; margin:1.2rem 0;'>"
                    "<div style='width:2px; height:36px; background:#FFD700;'></div>"
                    "<div style='width:0; height:0; border-left:7px solid transparent; "
                    "border-right:7px solid transparent; border-top:11px solid #FFD700;'></div></div>"
                )
                dv4_bullet_items = "".join(
                    f"<li style='margin-bottom:0.3rem;'>{bullet.replace('$', '&#36;')}</li>"
                    for bullet in dv4_bullets
                )
                st.html(
                    f"<ul style='color:#D6E4F0; font-size:0.9rem; padding-left:1.2rem;'>"
                    f"{dv4_bullet_items}</ul>"
                )

        with dv4_stocknews_col:
            st.markdown(
                "<div style='text-align:center; font-weight:bold;'>StockNews API Coverage</div>",
                unsafe_allow_html=True,
            )
            dv4_stocknews = stocknews_coverage_lookup[dv4_note_key]
            for field, heading in [
                ("summary_analysis", "Summary Analysis"),
                ("explicit_reasons", "Explicit Reasons"),
                ("implicit_reasons", "Implicit Reasons"),
            ]:
                if dv4_stocknews.get(field):
                    st.html(
                        f"<div class='context-heading'>{heading}</div>"
                        f"<p style='margin-bottom:0.8rem; text-align:justify;'>"
                        f"{render_inline_markdown(dv4_stocknews[field])}</p>"
                    )
            dv4_source_links = "".join(
                render_djnw_source_link_html(source) for source in dv4_stocknews.get("sources", [])
            )
            if dv4_source_links:
                st.html(dv4_source_links)
            if st.button(
                "StockNews Categories",
                key=f"dv4_stocknews_cat_{dv4_note_key}",
                use_container_width=True,
            ):
                _show_why_moved_2_categories_dialog(dv4_stocknews, "StockNews API")

        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    st.stop()

if st.session_state.selected_section == "Data Visualization 5":
    # 2 subgroups, both with newly-selected tickers excluded from Data Viz
    # 1/2/3 (see GROUP4_GROUPS above): "Small & Mid Cap" ($250M-$10B) and
    # "Large Cap" ($100B-$1T, merged from the original separate Large/Mega
    # split once Mega Cap proved too scarce a pool to fill on its own).
    # Same nav/chart/Visualize-toggle pattern and empty "Selected
    # Coverage"/"High-Tier Coverage" columns as Data Visualization 3.
    g4_band_tabs = list(GROUP4_GROUPS.keys()) + ["Data Analysis"]
    if "selected_g4_group" not in st.session_state:
        st.session_state.selected_g4_group = g4_band_tabs[0]

    g4_group_cols = st.columns(len(g4_band_tabs))
    for col, g in zip(g4_group_cols, g4_band_tabs):
        with col:
            is_selected = st.session_state.selected_g4_group == g
            if st.button(
                g,
                key=f"g4_groupbtn_{g}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_g4_group = g
                if g in GROUP4_GROUPS:
                    st.session_state.selected_g4_ticker = GROUP4_GROUPS[g][0]

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    selected_g4_group = st.session_state.selected_g4_group

    if selected_g4_group == "Data Analysis":
        g4_cap_scope = st.radio(
            "Market-cap scope",
            ["Small & Mid Cap only", "Large Cap only", "Both"],
            horizontal=True,
            key="g4_analysis_cap_scope",
        )
        if g4_cap_scope == "Small & Mid Cap only":
            g4_scope_tickers = set(GROUP4_GROUPS["Small & Mid Cap"])
        elif g4_cap_scope == "Large Cap only":
            g4_scope_tickers = set(GROUP4_GROUPS["Large Cap"])
        else:
            g4_scope_tickers = set(GROUP4_GROUPS["Small & Mid Cap"]) | set(GROUP4_GROUPS["Large Cap"])

        g4_analysis_categories = st.multiselect(
            "Categories included in ranking",
            WHY_MOVED_2_CATEGORIES,
            default=WHY_MOVED_2_CATEGORIES,
            key="g4_analysis_categories",
            help=(
                "Unselect any category to remove it from both the numerator and denominator. "
                "Immediate reaction divergence identifies observations where the article's "
                "immediate reaction and the computed two-day return have opposite signs."
            ),
        )
        g4_analysis_rows = []
        g4_analysis_excluded_no_category = 0
        g4_analysis_source = group4_band_observations[group4_band_observations["ticker"].isin(g4_scope_tickers)]
        for _, g4_analysis_row in g4_analysis_source.iterrows():
            g4_analysis_key = f"{g4_analysis_row['ticker']}_{g4_analysis_row['fiscal_yearquarter']}"
            g4_stocknews_entry = group4_stocknews_v2_lookup.get(g4_analysis_key)
            if not g4_stocknews_entry:
                continue
            g4_category_cells = g4_stocknews_entry.get("categories", {})
            g4_active_cells = [
                g4_category_cells.get(category)
                for category in g4_analysis_categories
                if g4_category_cells.get(category)
            ]
            g4_positive_count = sum(cell.get("direction") == "positive" for cell in g4_active_cells)
            g4_negative_count = sum(cell.get("direction") == "negative" for cell in g4_active_cells)
            g4_explicit_count = sum(cell.get("attribution") == "explicit" for cell in g4_active_cells)
            g4_implicit_count = sum(cell.get("attribution") == "implicit" for cell in g4_active_cells)
            g4_active_count = len(g4_active_cells)
            if g4_active_count == 0:
                # Has StockNews coverage, but none of the selected categories
                # were tied to the move -- excluded rather than plotted at a
                # neutral score, since a 0.0 category score would otherwise
                # be indistinguishable from a genuinely neutral/mixed result.
                g4_analysis_excluded_no_category += 1
                continue
            g4_category_sum = sum(
                (1 if cell.get("direction") == "positive" else -1)
                * (2 if cell.get("attribution") == "explicit" else 1)
                for cell in g4_active_cells
            )
            g4_category_score = g4_category_sum / g4_active_count
            g4_return_metrics = group4_abnormal_returns_lookup.get(g4_analysis_key, {})
            g4_market_model = g4_return_metrics.get("market_model") or {}
            g4_market_adjusted = g4_return_metrics.get("market_adjusted") or {}
            g4_analysis_rows.append(
                {
                    "note_key": g4_analysis_key,
                    "ticker": g4_analysis_row["ticker"],
                    "quarter": g4_analysis_row["fiscal_yearquarter"].upper(),
                    "earnings_date": g4_analysis_row["earnings_date"],
                    "category_score": g4_category_score,
                    "category_sum": g4_category_sum,
                    "active_categories": g4_active_count,
                    "positive_categories": g4_positive_count,
                    "negative_categories": g4_negative_count,
                    "explicit_categories": g4_explicit_count,
                    "implicit_categories": g4_implicit_count,
                    "abnormal_return_pct": g4_market_model.get("abnormal_return_pct"),
                    "abnormal_z_score": g4_market_model.get("z_score"),
                    "excess_return_pct": g4_market_adjusted.get("excess_return_pct"),
                    "excess_z_score": g4_market_adjusted.get("z_score"),
                }
            )

        g4_analysis_df = pd.DataFrame(g4_analysis_rows)

        if g4_analysis_df.empty:
            st.info("No StockNews-covered observations in this market-cap scope yet.")
            st.stop()

        g4_return_method = st.radio(
            "Return measure",
            ["Excess return", "Abnormal return"],
            horizontal=True,
            key="g4_analysis_return_method",
        )
        if g4_return_method == "Excess return":
            g4_z_column = "excess_z_score"
            g4_return_column = "excess_return_pct"
            g4_method_description = "market-adjusted excess return"
        else:
            g4_z_column = "abnormal_z_score"
            g4_return_column = "abnormal_return_pct"
            g4_method_description = "beta-adjusted abnormal return"

        g4_absolute_filter_col1, g4_absolute_filter_col2, g4_absolute_filter_col3 = st.columns([1.2, 1, 1])
        with g4_absolute_filter_col1:
            g4_absolute_filter_mode = st.radio(
                "Absolute graph Z-score filter",
                ["Include", "Exclude"],
                horizontal=True,
                key="g4_absolute_z_filter_mode",
            )
        with g4_absolute_filter_col2:
            g4_absolute_z_lower = st.number_input(
                "Lower Z-score", value=-10.0, step=0.5, key="g4_absolute_z_lower"
            )
        with g4_absolute_filter_col3:
            g4_absolute_z_upper = st.number_input(
                "Upper Z-score", value=10.0, step=0.5, key="g4_absolute_z_upper"
            )
        g4_absolute_z_min, g4_absolute_z_max = sorted((g4_absolute_z_lower, g4_absolute_z_upper))

        g4_chart_df = g4_analysis_df.dropna(subset=[g4_z_column]).copy()
        g4_absolute_inside = g4_chart_df[g4_z_column].between(g4_absolute_z_min, g4_absolute_z_max, inclusive="both")
        g4_chart_df = g4_chart_df[
            g4_absolute_inside if g4_absolute_filter_mode == "Include" else ~g4_absolute_inside
        ].copy()
        g4_chart_df["absolute_z_score"] = g4_chart_df[g4_z_column].abs()

        st.markdown(
            "<div class='quarter-header' style='font-size:1.5rem; text-align:center;'>"
            f"Absolute {g4_return_method} Z-Scores and StockNews Category Ranking</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='max-width:920px; margin:0 auto 1rem auto; text-align:center; "
            "color:rgba(214,228,240,0.82);'>"
            "Category score = signed weighted category sum ÷ total active categories. "
            "Explicit categories receive twice the numerator weight (±2) of implicit categories (±1). "
            "Only categories selected above enter the numerator and denominator. "
            "The score ranges from −2 to +2. Observations with StockNews coverage but no active "
            "category are excluded from both graphs.</div>",
            unsafe_allow_html=True,
        )

        g4_analysis_fig = go.Figure()
        for g4_analysis_ticker in sorted(g4_chart_df["ticker"].unique()):
            g4_ticker_points = g4_chart_df[g4_chart_df["ticker"] == g4_analysis_ticker]
            g4_customdata = [
                [
                    row.note_key,
                    row.quarter,
                    row.earnings_date.strftime("%Y-%m-%d"),
                    row.category_sum,
                    row.active_categories,
                    row.positive_categories,
                    row.negative_categories,
                    getattr(row, g4_z_column),
                    getattr(row, g4_return_column),
                    row.explicit_categories,
                    row.implicit_categories,
                ]
                for row in g4_ticker_points.itertuples()
            ]
            g4_analysis_fig.add_trace(
                go.Scatter(
                    x=g4_ticker_points["category_score"],
                    y=g4_ticker_points["absolute_z_score"],
                    mode="markers",
                    name=g4_analysis_ticker,
                    customdata=g4_customdata,
                    marker={"size": 10, "opacity": 0.78, "line": {"width": 0.6, "color": "#D6E4F0"}},
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Earnings: %{customdata[2]}<br>"
                        "Absolute Z-score: %{y:.2f}σ<br>"
                        "Signed Z-score: %{customdata[7]:+.2f}σ<br>"
                        f"{g4_method_description.capitalize()}: %{{customdata[8]:+.2f}}%<br>"
                        "Category score: %{x:.3f} "
                        "(%{customdata[3]}/%{customdata[4]})<br>"
                        "Positive: %{customdata[5]} | Negative: %{customdata[6]}<br>"
                        "Explicit: %{customdata[9]} | Implicit: %{customdata[10]}"
                        "<extra></extra>"
                    ),
                )
            )
        if len(g4_chart_df) >= 3 and g4_chart_df["category_score"].nunique() >= 3:
            g4_regression_x = np.linspace(
                g4_chart_df["category_score"].min(), g4_chart_df["category_score"].max(), 200
            )
            g4_regression_coefficients = np.polyfit(
                g4_chart_df["category_score"], g4_chart_df["absolute_z_score"], 2
            )
            g4_regression_y = np.polyval(g4_regression_coefficients, g4_regression_x)
            g4_fitted_y = np.polyval(g4_regression_coefficients, g4_chart_df["category_score"])
            g4_residuals = np.asarray(g4_chart_df["absolute_z_score"] - g4_fitted_y, dtype=float)
            g4_observed_x = np.asarray(g4_chart_df["category_score"], dtype=float)
            g4_local_x_half_window = 0.5
            g4_local_std = []
            for point in g4_regression_x:
                g4_local_residuals = g4_residuals[np.abs(g4_observed_x - point) <= g4_local_x_half_window]
                if len(g4_local_residuals) < 3:
                    g4_nearest = np.argsort(np.abs(g4_observed_x - point))[:min(5, len(g4_residuals))]
                    g4_local_residuals = g4_residuals[g4_nearest]
                g4_local_std.append(float(np.std(g4_local_residuals, ddof=1)))
            g4_local_std = np.asarray(g4_local_std)
            g4_analysis_fig.add_trace(
                go.Scatter(
                    x=g4_regression_x,
                    y=g4_regression_y + g4_local_std,
                    mode="lines",
                    line={"width": 0},
                    hoverinfo="skip",
                    showlegend=False,
                    legendgroup="absolute-regression-band",
                )
            )
            g4_analysis_fig.add_trace(
                go.Scatter(
                    x=g4_regression_x,
                    y=g4_regression_y - g4_local_std,
                    mode="lines",
                    line={"width": 0},
                    fill="tonexty",
                    fillcolor="rgba(255,209,102,0.18)",
                    name="Local ±1 SD",
                    hoverinfo="skip",
                    legendgroup="absolute-regression-band",
                )
            )
            g4_analysis_fig.add_trace(
                go.Scatter(
                    x=g4_regression_x,
                    y=g4_regression_y,
                    mode="lines",
                    name="Quadratic regression",
                    line={"color": "#FFD166", "width": 3},
                    hovertemplate="Quadratic regression<br>Category score: %{x:.3f}<br>Predicted |Z|: %{y:.2f}σ<extra></extra>",
                )
            )
        g4_analysis_fig.add_vline(x=0, line_dash="dash", line_color="rgba(214,228,240,0.45)")
        g4_analysis_fig.update_layout(
            xaxis_title="StockNews category ranking",
            yaxis_title=f"Absolute {g4_method_description} Z-score (σ)",
            xaxis={"range": [-2.08, 2.08], "tickmode": "linear", "dtick": 0.5},
            hovermode="closest",
            legend_title_text="Ticker",
            height=650,
            margin={"l": 65, "r": 35, "t": 35, "b": 65},
        )
        st.plotly_chart(g4_analysis_fig, use_container_width=True, key="g4_category_abnormal_scatter")
        st.caption(
            f"{len(g4_chart_df)} StockNews observations plotted. "
            f"{g4_absolute_filter_mode} signed Z-scores from {g4_absolute_z_min:+.2f}σ to {g4_absolute_z_max:+.2f}σ. "
            "Regression band: local ±1 return SD using a ±0.5 category-ranking window. "
            f"{g4_analysis_excluded_no_category} observations have StockNews coverage but no active "
            "category and are excluded from both graphs."
        )

        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)
        g4_signed_filter_col1, g4_signed_filter_col2, g4_signed_filter_col3 = st.columns([1.2, 1, 1])
        with g4_signed_filter_col1:
            g4_signed_filter_mode = st.radio(
                "Signed graph Z-score filter",
                ["Include", "Exclude"],
                horizontal=True,
                key="g4_signed_z_filter_mode",
            )
        with g4_signed_filter_col2:
            g4_signed_z_lower = st.number_input(
                "Lower Z-score", value=-10.0, step=0.5, key="g4_signed_z_lower"
            )
        with g4_signed_filter_col3:
            g4_signed_z_upper = st.number_input(
                "Upper Z-score", value=10.0, step=0.5, key="g4_signed_z_upper"
            )
        g4_signed_z_min, g4_signed_z_max = sorted((g4_signed_z_lower, g4_signed_z_upper))

        st.markdown(
            f"<div class='quarter-header' style='font-size:1.5rem; text-align:center;'>"
            f"Signed {g4_return_method} Z-Scores and StockNews Category Ranking</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='max-width:920px; margin:0 auto 1rem auto; text-align:center; "
            "color:rgba(214,228,240,0.82);'>"
            "This graph uses the signed Z-score rather than its absolute value. Positive and negative "
            "standardized market reactions therefore appear above and below zero.</div>",
            unsafe_allow_html=True,
        )

        g4_return_chart_df = g4_analysis_df.dropna(subset=[g4_z_column]).copy()
        g4_signed_inside = g4_return_chart_df[g4_z_column].between(g4_signed_z_min, g4_signed_z_max, inclusive="both")
        g4_return_chart_df = g4_return_chart_df[
            g4_signed_inside if g4_signed_filter_mode == "Include" else ~g4_signed_inside
        ].copy()
        g4_return_fig = go.Figure()
        for g4_analysis_ticker in sorted(g4_return_chart_df["ticker"].unique()):
            g4_ticker_points = g4_return_chart_df[g4_return_chart_df["ticker"] == g4_analysis_ticker]
            g4_customdata = [
                [
                    row.note_key,
                    row.quarter,
                    row.earnings_date.strftime("%Y-%m-%d"),
                    row.category_sum,
                    row.active_categories,
                    row.positive_categories,
                    row.negative_categories,
                    getattr(row, g4_z_column),
                    row.explicit_categories,
                    row.implicit_categories,
                ]
                for row in g4_ticker_points.itertuples()
            ]
            g4_return_fig.add_trace(
                go.Scatter(
                    x=g4_ticker_points["category_score"],
                    y=g4_ticker_points[g4_z_column],
                    mode="markers",
                    name=g4_analysis_ticker,
                    customdata=g4_customdata,
                    marker={"size": 10, "opacity": 0.78, "line": {"width": 0.6, "color": "#D6E4F0"}},
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Earnings: %{customdata[2]}<br>"
                        "Signed Z-score: %{y:+.2f}σ<br>"
                        "Category score: %{x:.3f} "
                        "(%{customdata[3]}/%{customdata[4]})<br>"
                        "Positive: %{customdata[5]} | Negative: %{customdata[6]}<br>"
                        "Explicit: %{customdata[8]} | Implicit: %{customdata[9]}"
                        "<extra></extra>"
                    ),
                )
            )
        if len(g4_return_chart_df) >= 3 and g4_return_chart_df["category_score"].nunique() >= 3:
            g4_regression_x = np.linspace(
                g4_return_chart_df["category_score"].min(), g4_return_chart_df["category_score"].max(), 200
            )
            g4_regression_coefficients = np.polyfit(
                g4_return_chart_df["category_score"], g4_return_chart_df[g4_z_column], 2
            )
            g4_regression_y = np.polyval(g4_regression_coefficients, g4_regression_x)
            g4_fitted_y = np.polyval(g4_regression_coefficients, g4_return_chart_df["category_score"])
            g4_residuals = np.asarray(g4_return_chart_df[g4_z_column] - g4_fitted_y, dtype=float)
            g4_observed_x = np.asarray(g4_return_chart_df["category_score"], dtype=float)
            g4_local_x_half_window = 0.5
            g4_local_std = []
            for point in g4_regression_x:
                g4_local_residuals = g4_residuals[np.abs(g4_observed_x - point) <= g4_local_x_half_window]
                if len(g4_local_residuals) < 3:
                    g4_nearest = np.argsort(np.abs(g4_observed_x - point))[:min(5, len(g4_residuals))]
                    g4_local_residuals = g4_residuals[g4_nearest]
                g4_local_std.append(float(np.std(g4_local_residuals, ddof=1)))
            g4_local_std = np.asarray(g4_local_std)
            g4_return_fig.add_trace(
                go.Scatter(
                    x=g4_regression_x,
                    y=g4_regression_y + g4_local_std,
                    mode="lines",
                    line={"width": 0},
                    hoverinfo="skip",
                    showlegend=False,
                    legendgroup="signed-regression-band",
                )
            )
            g4_return_fig.add_trace(
                go.Scatter(
                    x=g4_regression_x,
                    y=g4_regression_y - g4_local_std,
                    mode="lines",
                    line={"width": 0},
                    fill="tonexty",
                    fillcolor="rgba(255,209,102,0.18)",
                    name="Local ±1 SD",
                    hoverinfo="skip",
                    legendgroup="signed-regression-band",
                )
            )
            g4_return_fig.add_trace(
                go.Scatter(
                    x=g4_regression_x,
                    y=g4_regression_y,
                    mode="lines",
                    name="Quadratic regression",
                    line={"color": "#FFD166", "width": 3},
                    hovertemplate="Quadratic regression<br>Category score: %{x:.3f}<br>Predicted Z: %{y:+.2f}σ<extra></extra>",
                )
            )
        g4_return_fig.add_hline(y=0, line_dash="dash", line_color="rgba(214,228,240,0.45)")
        g4_return_fig.add_vline(x=0, line_dash="dash", line_color="rgba(214,228,240,0.45)")
        g4_return_fig.update_layout(
            xaxis_title="StockNews category ranking",
            yaxis_title=f"Signed {g4_method_description} Z-score (σ)",
            xaxis={"range": [-2.08, 2.08], "tickmode": "linear", "dtick": 0.5},
            hovermode="closest",
            legend_title_text="Ticker",
            height=650,
            margin={"l": 65, "r": 35, "t": 35, "b": 65},
        )
        st.plotly_chart(g4_return_fig, use_container_width=True, key="g4_category_return_scatter")
        st.caption(
            f"{len(g4_return_chart_df)} StockNews observations plotted with the signed "
            f"{g4_method_description} Z-score. {g4_signed_filter_mode} signed Z-scores from "
            f"{g4_signed_z_min:+.2f}σ to {g4_signed_z_max:+.2f}σ. "
            "Regression band: local ±1 return SD using a ±0.5 category-ranking window."
        )
        st.stop()

    g4_group_tickers = GROUP4_GROUPS[selected_g4_group]

    if (
        "selected_g4_ticker" not in st.session_state
        or st.session_state.selected_g4_ticker not in g4_group_tickers
    ):
        st.session_state.selected_g4_ticker = g4_group_tickers[0]

    g4_ticker_cols = st.columns(len(g4_group_tickers))
    for col, t in zip(g4_ticker_cols, g4_group_tickers):
        with col:
            is_selected = st.session_state.selected_g4_ticker == t
            if st.button(
                t,
                key=f"g4_navbtn_{t}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
                help=GROUP4_COMPANY_NAMES.get(t, t),
            ):
                st.session_state.selected_g4_ticker = t

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    g4_ticker = st.session_state.selected_g4_ticker
    g4_sub = group4_band_observations[group4_band_observations["ticker"] == g4_ticker].reset_index(drop=True)
    g4_company_name = GROUP4_COMPANY_NAMES.get(g4_ticker, g4_ticker)

    if g4_sub.empty:
        st.info(f"No 2021-2023 observations available for {g4_ticker}.")
        st.stop()

    st.markdown(
        f"<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>{g4_ticker} — {g4_company_name}</div>",
        unsafe_allow_html=True,
    )
    g4_period_start = g4_sub["earnings_date"].min().strftime("%Y-%m-%d")
    g4_period_end = g4_sub["earnings_date"].max().strftime("%Y-%m-%d")
    st.markdown(
        f"<div style='text-align:center; color:rgba(214,228,240,0.7); font-size:0.85rem;'>"
        f"{len(g4_sub)} observations, {g4_period_start} to {g4_period_end}</div>",
        unsafe_allow_html=True,
    )

    render_price_chart(g4_ticker, group4_price_history, g4_sub)

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    g4_sp_df_for_headers = None
    if group4_price_history is not None:
        g4_sp_df_for_headers = pd.DataFrame(group4_price_history["sp500"])
        g4_sp_df_for_headers["date"] = pd.to_datetime(g4_sp_df_for_headers["date"])
        g4_sp_df_for_headers = g4_sp_df_for_headers.sort_values("date").reset_index(drop=True)

    for g4_idx, g4_row in g4_sub.iterrows():
        g4_note_key = f"{g4_row['ticker']}_{g4_row['fiscal_yearquarter']}"
        g4_ret_pct = g4_row["ret_2day"] * 100
        g4_ret_str = f"{g4_ret_pct:+.2f}%"
        g4_sp_ret = (
            sp_return_2day(g4_sp_df_for_headers, g4_row["earnings_date"])
            if g4_sp_df_for_headers is not None
            else None
        )
        g4_sp_ret_str = f"{g4_sp_ret:+.2f}%" if g4_sp_ret is not None else "n/a"
        g4_excess_str = excess_return_str(g4_ret_pct, g4_sp_ret)
        g4_abnormal_info = group4_abnormal_returns_lookup.get(g4_note_key, {})
        g4_abnormal_str = abnormal_return_str(g4_abnormal_info.get("market_model"))
        g4_ma_z_suffix = market_adjusted_z_suffix(g4_abnormal_info.get("market_adjusted"))

        st.markdown(
            f"<div class='quarter-header' style='text-align:center;'>{g4_row['fiscal_yearquarter'].upper()} "
            f"&nbsp;|&nbsp; earnings {g4_row['earnings_date'].strftime('%Y-%m-%d')}</div>"
            f"<div class='quarter-header' style='text-align:center;'>2-day return {g4_ret_str} "
            f"&nbsp;|&nbsp; S&amp;P 2-day return {g4_sp_ret_str}</div>"
            f"<div style=\"text-align:center; font-size:1.3rem; font-family:'Cormorant Garamond', serif; "
            f"color:rgba(214,228,240,0.9); margin-bottom:0.3rem;\">Excess return {g4_excess_str}{g4_ma_z_suffix} "
            f"&nbsp;|&nbsp; Beta-adjusted abnormal return {g4_abnormal_str}</div>",
            unsafe_allow_html=True,
        )

        with st.container(key=f"g4viz_{g4_note_key}"):
            g4_viz_toggle_id = f"g4viz_toggle_{g4_note_key}"
            st.html(
                f"<input type='checkbox' id='{g4_viz_toggle_id}' class='visualize-checkbox'>"
                f"<label for='{g4_viz_toggle_id}' class='visualize-label'>Visualize</label>"
            )
            g4_viz_fig = build_quarter_visualize_fig(g4_ticker, group4_price_history, g4_sub, g4_idx)
            if g4_viz_fig is not None:
                st.plotly_chart(g4_viz_fig, use_container_width=True, key=f"g4viz_chart_{g4_note_key}")

        g4_left, g4_right = st.columns(2, gap="large")
        with g4_left:
            st.markdown(
                "<div style='text-align:center; font-weight:bold;'>Selected Coverage</div>"
                "<div style='text-align:center; color:#FFD166; font-size:0.9rem; margin-bottom:0.7rem;'>"
                "StockNews API</div>",
                unsafe_allow_html=True,
            )
            g4_stocknews = group4_stocknews_v2_lookup.get(g4_note_key)
            if g4_stocknews:
                for field, heading in [
                    ("summary_analysis", "Summary Analysis"),
                    ("explicit_reasons", "Explicit Reasons"),
                    ("implicit_reasons", "Implicit Reasons"),
                ]:
                    if g4_stocknews.get(field):
                        st.html(
                            f"<div class='context-heading'>{heading}</div>"
                            f"<p style='margin-bottom:0.8rem; text-align:justify;'>"
                            f"{render_inline_markdown(g4_stocknews[field])}</p>"
                        )
                g4_source_links = "".join(
                    render_djnw_source_link_html(source) for source in g4_stocknews.get("sources", [])
                )
                if g4_source_links:
                    st.html(g4_source_links)
                if st.button(
                    "StockNews Categories", key=f"g4_stocknews_cat_{g4_note_key}", use_container_width=True
                ):
                    _show_why_moved_2_categories_dialog(g4_stocknews, "StockNews API")
            else:
                st.write("*No validated StockNews API coverage available for this observation.*")
        with g4_right:
            st.markdown(
                "<div style='text-align:center; font-weight:bold;'>High-Tier Coverage</div>",
                unsafe_allow_html=True,
            )
            st.write("*No coverage available yet for this observation.*")

        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    st.stop()

if st.session_state.selected_section == "Data Visualization 6":
    # Same pattern as Data Visualization 5: 2 subgroups, "Small & Mid Cap"
    # ($250M-$10B) and "Large Cap" ($100B-$1T), with 20 more newly-
    # selected tickers excluded from Data Viz 1/2/3/4 (see GROUP5_GROUPS
    # above).
    if "selected_g5_group" not in st.session_state:
        st.session_state.selected_g5_group = list(GROUP5_GROUPS)[0]

    g5_group_cols = st.columns(len(GROUP5_GROUPS))
    for col, g in zip(g5_group_cols, GROUP5_GROUPS.keys()):
        with col:
            is_selected = st.session_state.selected_g5_group == g
            if st.button(
                g,
                key=f"g5_groupbtn_{g}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_g5_group = g
                st.session_state.selected_g5_ticker = GROUP5_GROUPS[g][0]

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    selected_g5_group = st.session_state.selected_g5_group
    g5_group_tickers = GROUP5_GROUPS[selected_g5_group]

    if (
        "selected_g5_ticker" not in st.session_state
        or st.session_state.selected_g5_ticker not in g5_group_tickers
    ):
        st.session_state.selected_g5_ticker = g5_group_tickers[0]

    g5_ticker_cols = st.columns(len(g5_group_tickers))
    for col, t in zip(g5_ticker_cols, g5_group_tickers):
        with col:
            is_selected = st.session_state.selected_g5_ticker == t
            if st.button(
                t,
                key=f"g5_navbtn_{t}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
                help=GROUP5_COMPANY_NAMES.get(t, t),
            ):
                st.session_state.selected_g5_ticker = t

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    g5_ticker = st.session_state.selected_g5_ticker
    g5_sub = group5_band_observations[group5_band_observations["ticker"] == g5_ticker].reset_index(drop=True)
    g5_company_name = GROUP5_COMPANY_NAMES.get(g5_ticker, g5_ticker)

    if g5_sub.empty:
        st.info(f"No 2021-2023 observations available for {g5_ticker}.")
        st.stop()

    st.markdown(
        f"<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>{g5_ticker} — {g5_company_name}</div>",
        unsafe_allow_html=True,
    )
    g5_period_start = g5_sub["earnings_date"].min().strftime("%Y-%m-%d")
    g5_period_end = g5_sub["earnings_date"].max().strftime("%Y-%m-%d")
    st.markdown(
        f"<div style='text-align:center; color:rgba(214,228,240,0.7); font-size:0.85rem;'>"
        f"{len(g5_sub)} observations, {g5_period_start} to {g5_period_end}</div>",
        unsafe_allow_html=True,
    )

    render_price_chart(g5_ticker, group5_price_history, g5_sub)

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    g5_sp_df_for_headers = None
    if group5_price_history is not None:
        g5_sp_df_for_headers = pd.DataFrame(group5_price_history["sp500"])
        g5_sp_df_for_headers["date"] = pd.to_datetime(g5_sp_df_for_headers["date"])
        g5_sp_df_for_headers = g5_sp_df_for_headers.sort_values("date").reset_index(drop=True)

    for g5_idx, g5_row in g5_sub.iterrows():
        g5_note_key = f"{g5_row['ticker']}_{g5_row['fiscal_yearquarter']}"
        g5_ret_pct = g5_row["ret_2day"] * 100
        g5_ret_str = f"{g5_ret_pct:+.2f}%"
        g5_sp_ret = (
            sp_return_2day(g5_sp_df_for_headers, g5_row["earnings_date"])
            if g5_sp_df_for_headers is not None
            else None
        )
        g5_sp_ret_str = f"{g5_sp_ret:+.2f}%" if g5_sp_ret is not None else "n/a"
        g5_excess_str = excess_return_str(g5_ret_pct, g5_sp_ret)
        g5_abnormal_info = group5_abnormal_returns_lookup.get(g5_note_key, {})
        g5_abnormal_str = abnormal_return_str(g5_abnormal_info.get("market_model"))
        g5_ma_z_suffix = market_adjusted_z_suffix(g5_abnormal_info.get("market_adjusted"))

        st.markdown(
            f"<div class='quarter-header' style='text-align:center;'>{g5_row['fiscal_yearquarter'].upper()} "
            f"&nbsp;|&nbsp; earnings {g5_row['earnings_date'].strftime('%Y-%m-%d')}</div>"
            f"<div class='quarter-header' style='text-align:center;'>2-day return {g5_ret_str} "
            f"&nbsp;|&nbsp; S&amp;P 2-day return {g5_sp_ret_str}</div>"
            f"<div style=\"text-align:center; font-size:1.3rem; font-family:'Cormorant Garamond', serif; "
            f"color:rgba(214,228,240,0.9); margin-bottom:0.3rem;\">Excess return {g5_excess_str}{g5_ma_z_suffix} "
            f"&nbsp;|&nbsp; Beta-adjusted abnormal return {g5_abnormal_str}</div>",
            unsafe_allow_html=True,
        )

        with st.container(key=f"g4viz_{g5_note_key}"):
            g5_viz_toggle_id = f"g4viz_toggle_{g5_note_key}"
            st.html(
                f"<input type='checkbox' id='{g5_viz_toggle_id}' class='visualize-checkbox'>"
                f"<label for='{g5_viz_toggle_id}' class='visualize-label'>Visualize</label>"
            )
            g5_viz_fig = build_quarter_visualize_fig(g5_ticker, group5_price_history, g5_sub, g5_idx)
            if g5_viz_fig is not None:
                st.plotly_chart(g5_viz_fig, use_container_width=True, key=f"g4viz_chart_{g5_note_key}")

        g5_left, g5_right = st.columns(2, gap="large")
        with g5_left:
            st.markdown(
                "<div style='text-align:center; font-weight:bold;'>Selected Coverage</div>"
                "<div style='text-align:center; color:#FFD166; font-size:0.9rem; margin-bottom:0.7rem;'>"
                "ChatGPT — Massive / Benzinga</div>",
                unsafe_allow_html=True,
            )
            g5_chatgpt = viz45_chatgpt_coverage_lookup.get(g5_note_key)
            if g5_chatgpt:
                st.markdown(
                    "<div class='context-heading'>Why The Stock Moved</div>",
                    unsafe_allow_html=True,
                )
                st.write(g5_chatgpt.get("final_paragraph", ""))
                for source in g5_chatgpt.get("sources", []):
                    source_html = render_djnw_source_link_html(source)
                    if source_html:
                        st.markdown(source_html, unsafe_allow_html=True)
            else:
                st.write("*ChatGPT pilot coverage is available for CYH, MATW, and INDI.*")
        with g5_right:
            st.markdown(
                "<div style='text-align:center; font-weight:bold;'>High-Tier Coverage</div>",
                unsafe_allow_html=True,
            )
            st.write("*No coverage available yet for this observation.*")

        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    st.stop()

if st.session_state.selected_section == "Data Visualization 7":
    # Same pattern as Data Visualization 5/6: 2 subgroups, "Small & Mid Cap"
    # ($250M-$10B) and "Large Cap" ($100B-$1T), with 20 more newly-
    # selected tickers excluded from Data Viz 1/2/3/4/5 (see GROUP6_GROUPS
    # above).
    if "selected_g6_group" not in st.session_state:
        st.session_state.selected_g6_group = list(GROUP6_GROUPS)[0]

    g6_group_cols = st.columns(len(GROUP6_GROUPS))
    for col, g in zip(g6_group_cols, GROUP6_GROUPS.keys()):
        with col:
            is_selected = st.session_state.selected_g6_group == g
            if st.button(
                g,
                key=f"g6_groupbtn_{g}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_g6_group = g
                st.session_state.selected_g6_ticker = GROUP6_GROUPS[g][0]

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    selected_g6_group = st.session_state.selected_g6_group
    g6_group_tickers = GROUP6_GROUPS[selected_g6_group]

    if (
        "selected_g6_ticker" not in st.session_state
        or st.session_state.selected_g6_ticker not in g6_group_tickers
    ):
        st.session_state.selected_g6_ticker = g6_group_tickers[0]

    g6_ticker_cols = st.columns(len(g6_group_tickers))
    for col, t in zip(g6_ticker_cols, g6_group_tickers):
        with col:
            is_selected = st.session_state.selected_g6_ticker == t
            if st.button(
                t,
                key=f"g6_navbtn_{t}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
                help=GROUP6_COMPANY_NAMES.get(t, t),
            ):
                st.session_state.selected_g6_ticker = t

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    g6_ticker = st.session_state.selected_g6_ticker
    g6_sub = group6_band_observations[group6_band_observations["ticker"] == g6_ticker].reset_index(drop=True)
    g6_company_name = GROUP6_COMPANY_NAMES.get(g6_ticker, g6_ticker)

    if g6_sub.empty:
        st.info(f"No 2021-2023 observations available for {g6_ticker}.")
        st.stop()

    st.markdown(
        f"<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>{g6_ticker} — {g6_company_name}</div>",
        unsafe_allow_html=True,
    )
    g6_period_start = g6_sub["earnings_date"].min().strftime("%Y-%m-%d")
    g6_period_end = g6_sub["earnings_date"].max().strftime("%Y-%m-%d")
    st.markdown(
        f"<div style='text-align:center; color:rgba(214,228,240,0.7); font-size:0.85rem;'>"
        f"{len(g6_sub)} observations, {g6_period_start} to {g6_period_end}</div>",
        unsafe_allow_html=True,
    )

    render_price_chart(g6_ticker, group6_price_history, g6_sub)

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    g6_sp_df_for_headers = None
    if group6_price_history is not None:
        g6_sp_df_for_headers = pd.DataFrame(group6_price_history["sp500"])
        g6_sp_df_for_headers["date"] = pd.to_datetime(g6_sp_df_for_headers["date"])
        g6_sp_df_for_headers = g6_sp_df_for_headers.sort_values("date").reset_index(drop=True)

    for g6_idx, g6_row in g6_sub.iterrows():
        g6_note_key = f"{g6_row['ticker']}_{g6_row['fiscal_yearquarter']}"
        g6_ret_pct = g6_row["ret_2day"] * 100
        g6_ret_str = f"{g6_ret_pct:+.2f}%"
        g6_sp_ret = (
            sp_return_2day(g6_sp_df_for_headers, g6_row["earnings_date"])
            if g6_sp_df_for_headers is not None
            else None
        )
        g6_sp_ret_str = f"{g6_sp_ret:+.2f}%" if g6_sp_ret is not None else "n/a"
        g6_excess_str = excess_return_str(g6_ret_pct, g6_sp_ret)
        g6_abnormal_info = group6_abnormal_returns_lookup.get(g6_note_key, {})
        g6_abnormal_str = abnormal_return_str(g6_abnormal_info.get("market_model"))
        g6_ma_z_suffix = market_adjusted_z_suffix(g6_abnormal_info.get("market_adjusted"))

        st.markdown(
            f"<div class='quarter-header' style='text-align:center;'>{g6_row['fiscal_yearquarter'].upper()} "
            f"&nbsp;|&nbsp; earnings {g6_row['earnings_date'].strftime('%Y-%m-%d')}</div>"
            f"<div class='quarter-header' style='text-align:center;'>2-day return {g6_ret_str} "
            f"&nbsp;|&nbsp; S&amp;P 2-day return {g6_sp_ret_str}</div>"
            f"<div style=\"text-align:center; font-size:1.3rem; font-family:'Cormorant Garamond', serif; "
            f"color:rgba(214,228,240,0.9); margin-bottom:0.3rem;\">Excess return {g6_excess_str}{g6_ma_z_suffix} "
            f"&nbsp;|&nbsp; Beta-adjusted abnormal return {g6_abnormal_str}</div>",
            unsafe_allow_html=True,
        )

        with st.container(key=f"g6viz_{g6_note_key}"):
            g6_viz_toggle_id = f"g6viz_toggle_{g6_note_key}"
            st.html(
                f"<input type='checkbox' id='{g6_viz_toggle_id}' class='visualize-checkbox'>"
                f"<label for='{g6_viz_toggle_id}' class='visualize-label'>Visualize</label>"
            )
            g6_viz_fig = build_quarter_visualize_fig(g6_ticker, group6_price_history, g6_sub, g6_idx)
            if g6_viz_fig is not None:
                st.plotly_chart(g6_viz_fig, use_container_width=True, key=f"g6viz_chart_{g6_note_key}")

        g6_left, g6_right = st.columns(2, gap="large")
        with g6_left:
            st.markdown(
                "<div style='text-align:center; font-weight:bold;'>Selected Coverage</div>",
                unsafe_allow_html=True,
            )
            st.write("*No coverage available yet for this observation.*")
        with g6_right:
            st.markdown(
                "<div style='text-align:center; font-weight:bold;'>High-Tier Coverage</div>",
                unsafe_allow_html=True,
            )
            st.write("*No coverage available yet for this observation.*")

        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    st.stop()

if st.session_state.selected_section == "Comparative Study":
    if "selected_comparative_subsection" not in st.session_state:
        st.session_state.selected_comparative_subsection = "Data Visualization 1"

    comp_section_cols = st.columns(2)
    for col, subsection in zip(comp_section_cols, ("Data Visualization 1", "Data Visualization 2")):
        with col:
            is_selected = st.session_state.selected_comparative_subsection == subsection
            if st.button(
                subsection,
                key=f"comparative_subsection_{subsection}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.selected_comparative_subsection = subsection

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    if st.session_state.selected_comparative_subsection == "Data Visualization 2":
        accuracy_options = ["Not yet rated", "Accurate", "Not accurate"]
        accuracy_sources = (
            ("contextual_analysis", "Contextualized interpretation"),
            ("wsj", "WSJ Coverage"),
            ("djnw", "Dow Jones Newswires Coverage"),
        )

        if "selected_accuracy_group" not in st.session_state:
            st.session_state.selected_accuracy_group = list(GROUPS)[0]

        accuracy_group_cols = st.columns(len(GROUPS))
        for col, group_name in zip(accuracy_group_cols, GROUPS):
            with col:
                is_selected = st.session_state.selected_accuracy_group == group_name
                if st.button(
                    f"{group_name} ({GROUP_MARKET_CAP_LABELS[group_name]})",
                    key=f"accuracy_group_{group_name}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    st.session_state.selected_accuracy_group = group_name
                    st.session_state.selected_accuracy_ticker = GROUPS[group_name][0]

        accuracy_group = st.session_state.selected_accuracy_group
        accuracy_tickers = GROUPS[accuracy_group]
        if (
            "selected_accuracy_ticker" not in st.session_state
            or st.session_state.selected_accuracy_ticker not in accuracy_tickers + ["All"]
        ):
            st.session_state.selected_accuracy_ticker = accuracy_tickers[0]

        accuracy_nav_items = accuracy_tickers + ["All"]
        accuracy_nav_cols = st.columns(len(accuracy_nav_items))
        for col, ticker in zip(accuracy_nav_cols, accuracy_nav_items):
            with col:
                is_selected = st.session_state.selected_accuracy_ticker == ticker
                if st.button(
                    ticker,
                    key=f"accuracy_ticker_{ticker}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                    help=GROUP_COMPANY_NAMES.get(ticker, "All tickers — coverage accuracy overview"),
                ):
                    st.session_state.selected_accuracy_ticker = ticker

        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)
        accuracy_ticker = st.session_state.selected_accuracy_ticker

        def _coverage_available(note_key, source_key):
            if source_key == "contextual_analysis":
                return bool(group_context_lookup.get(note_key))
            lookup = group_wsj_coverage_lookup if source_key == "wsj" else group_djnw_coverage_lookup
            entry = lookup.get(note_key)
            return bool(entry and (entry.get("summary_analysis") or entry.get("why_moved")))

        if accuracy_ticker == "All":
            st.markdown(
                "<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>"
                f"{accuracy_group} — Coverage Accuracy Overview</div>",
                unsafe_allow_html=True,
            )
            overview_cols = st.columns(len(accuracy_tickers))
            for col, ticker in zip(overview_cols, accuracy_tickers):
                with col:
                    ticker_rows = middle_n_quarters(group_df[group_df["ticker"] == ticker], n=10)
                    dots_html = (
                        f"<div style='text-align:center; font-weight:600; color:#f4c542; "
                        f"margin-bottom:0.5rem;'>{ticker}</div>"
                    )
                    for _, row in ticker_rows.iterrows():
                        note_key = f"{ticker}_{row['fiscal_yearquarter']}"
                        answer = group_coverage_accuracy_lookup.get(note_key, {})
                        available = [key for key, _ in accuracy_sources if _coverage_available(note_key, key)]
                        rated = [answer.get(key, "Not yet rated") for key in available]
                        if rated and all(value == "Accurate" for value in rated):
                            color = "#2ecc71"
                        elif not any(value != "Not yet rated" for value in rated):
                            color = "#e74c3c"
                        else:
                            color = "#f39c12"
                        dots_html += (
                            f"<div title='{row['fiscal_yearquarter'].upper()}' "
                            f"style='width:14px; height:14px; border-radius:50%; "
                            f"background:{color}; margin:4px auto;'></div>"
                        )
                    st.markdown(dots_html, unsafe_allow_html=True)
            st.stop()

        accuracy_rows = middle_n_quarters(
            group_df[group_df["ticker"] == accuracy_ticker], n=10
        ).reset_index(drop=True)
        st.markdown(
            f"<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>"
            f"{accuracy_ticker} — {GROUP_COMPANY_NAMES.get(accuracy_ticker, accuracy_ticker)}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

        accuracy_changed = False
        for _, row in accuracy_rows.iterrows():
            note_key = f"{accuracy_ticker}_{row['fiscal_yearquarter']}"
            st.markdown(
                f"<div class='quarter-header' style='text-align:center;'>"
                f"{row['fiscal_yearquarter'].upper()} &nbsp;|&nbsp; "
                f"earnings {row['earnings_date'].strftime('%Y-%m-%d')} &nbsp;|&nbsp; "
                f"2-day return {row['ret_2day'] * 100:+.2f}%</div>",
                unsafe_allow_html=True,
            )
            current = group_coverage_accuracy_lookup.get(note_key, {})
            rating_cols = st.columns(3)
            updated = dict(current)
            for col, (source_key, source_label) in zip(rating_cols, accuracy_sources):
                with col:
                    if not _coverage_available(note_key, source_key):
                        st.markdown(f"**{source_label}**")
                        st.caption("No coverage available for this observation.")
                        continue
                    current_value = current.get(source_key, "Not yet rated")
                    value = st.radio(
                        source_label,
                        accuracy_options,
                        index=accuracy_options.index(current_value),
                        key=f"coverage_accuracy_{source_key}_{note_key}",
                        horizontal=True,
                    )
                    updated[source_key] = value
                    if value != current_value:
                        accuracy_changed = True
            if updated != current:
                group_coverage_accuracy_lookup[note_key] = updated
            st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

        if accuracy_changed:
            save_group_coverage_accuracy(group_coverage_accuracy_lookup)
        st.stop()

    # Same 17-ticker nav bar as Data Visualization, but tracked with its own
    # session-state key so switching sections doesn't lose your place in
    # either one. Selecting a ticker here lists every one of its quarters
    # with just the two rating questions -- no chart, no context text, no
    # generated text -- and every answer is written back to disk immediately
    # so Data Visualization's read-only display picks it up on next rerun.
    if "selected_comparative_ticker" not in st.session_state:
        st.session_state.selected_comparative_ticker = tickers[0]

    comp_nav_items = tickers + ["All"]
    comp_cols = st.columns(len(comp_nav_items))
    for col, t in zip(comp_cols, comp_nav_items):
        with col:
            is_selected = st.session_state.selected_comparative_ticker == t
            if st.button(
                t,
                key=f"compnavbtn_{t}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
                help=ticker_labels.get(t, "All tickers — rating overview"),
            ):
                st.session_state.selected_comparative_ticker = t

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    comp_ticker = st.session_state.selected_comparative_ticker

    if comp_ticker == "All":
        # Overview grid: one column per ticker, one dot per observation
        # (top = earliest quarter). Dot color reflects the two Comparative
        # Study answers for that observation -- green when both are the
        # fully-positive answer, red when neither question has been rated
        # yet, orange for every in-between combination.
        def _comp_dot_color(answer):
            q1 = answer.get("q1", "Not yet rated")
            q2 = answer.get("q2", "Not yet rated")
            if q1 == "Not yet rated" and q2 == "Not yet rated":
                return "#e74c3c"
            if q1 == "True" and q2 == "Accurate":
                return "#2ecc71"
            return "#f39c12"

        st.markdown(
            "<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>"
            "All Tickers — Rating Overview</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

        all_cols = st.columns(len(tickers))
        for col, t in zip(all_cols, tickers):
            with col:
                t_sub = df[df["ticker"] == t].reset_index(drop=True)
                dots_html = (
                    f"<div style='text-align:center; font-weight:600; "
                    f"color:#f4c542; margin-bottom:0.5rem;'>{t}</div>"
                )
                for _, row in t_sub.iterrows():
                    note_key = f"{row['ticker']}_{row['fiscal_yearquarter']}"
                    answer = comparative_answers_lookup.get(note_key, {})
                    color = _comp_dot_color(answer)
                    dots_html += (
                        f"<div title='{row['fiscal_yearquarter'].upper()}' "
                        f"style='width:14px; height:14px; border-radius:50%; "
                        f"background:{color}; margin:4px auto;'></div>"
                    )
                st.markdown(dots_html, unsafe_allow_html=True)

        st.stop()

    comp_sub = df[df["ticker"] == comp_ticker].reset_index(drop=True)
    comp_company_name = comp_sub["company_name"].iloc[0]

    st.markdown(
        f"<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>"
        f"{comp_ticker} — {comp_company_name}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    answers_changed = False
    for _, row in comp_sub.iterrows():
        comp_note_key = f"{row['ticker']}_{row['fiscal_yearquarter']}"
        comp_ret_pct = row["ret_2day"] * 100

        st.markdown(
            f"<div class='quarter-header' style='text-align:center;'>{row['fiscal_yearquarter'].upper()} "
            f"&nbsp;|&nbsp; earnings {row['earnings_date'].strftime('%Y-%m-%d')} "
            f"&nbsp;|&nbsp; 2-day return {comp_ret_pct:+.2f}%</div>",
            unsafe_allow_html=True,
        )

        current_answer = comparative_answers_lookup.get(comp_note_key, {})
        q_col1, q_col2 = st.columns(2)
        with q_col1:
            q1_value = st.radio(
                Q1_QUESTION,
                Q1_OPTIONS,
                index=Q1_OPTIONS.index(current_answer.get("q1", "Not yet rated")),
                key=f"q1_{comp_note_key}",
                horizontal=True,
            )
        with q_col2:
            q2_value = st.radio(
                Q2_QUESTION,
                Q2_OPTIONS,
                index=Q2_OPTIONS.index(current_answer.get("q2", "Not yet rated")),
                key=f"q2_{comp_note_key}",
                horizontal=True,
            )

        if current_answer.get("q1", "Not yet rated") != q1_value or current_answer.get("q2", "Not yet rated") != q2_value:
            comparative_answers_lookup[comp_note_key] = {"q1": q1_value, "q2": q2_value}
            answers_changed = True

        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    if answers_changed:
        save_comparative_answers(comparative_answers_lookup)

    st.stop()

# ── All 17 tickers on a single horizontal line ──
cols = st.columns(len(tickers))
for col, t in zip(cols, tickers):
    with col:
        is_selected = st.session_state.selected_ticker == t
        if st.button(
            t,
            key=f"navbtn_{t}",
            use_container_width=True,
            type="primary" if is_selected else "secondary",
            help=ticker_labels[t],
        ):
            st.session_state.selected_ticker = t

st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

# ── Selected ticker's header + full-history chart ──
selected_ticker = st.session_state.selected_ticker
sub = df[df["ticker"] == selected_ticker].reset_index(drop=True)
company_name = sub["company_name"].iloc[0]
period_start = sub["earnings_date"].min().strftime("%Y-%m-%d")
period_end = sub["earnings_date"].max().strftime("%Y-%m-%d")

st.markdown(
    f"<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>{selected_ticker} — {company_name}</div>",
    unsafe_allow_html=True,
)

third_column_source = st.radio(
    "Third-column news source",
    ["Dow Jones Newswires", "Massive / Benzinga", "Massive", "StockNews API"],
    horizontal=True,
    key=f"third_column_source_{selected_ticker}",
)

if st.checkbox("Only show observations from April 2019 onward", key="dv1_from_april_2019"):
    sub = sub[sub["earnings_date"] >= pd.Timestamp("2019-04-01")].reset_index(drop=True)
    period_start = sub["earnings_date"].min().strftime("%Y-%m-%d")
    period_end = sub["earnings_date"].max().strftime("%Y-%m-%d")

company_info = company_info_lookup.get(selected_ticker)
if company_info:
    st.markdown(
        f"<div style='text-align:center; color:rgba(214,228,240,0.75); font-size:0.85rem; "
        f"font-style:italic; max-width:700px; margin:0 auto 0.3rem auto;'>"
        f"{company_info['description']} It's a {company_info['cap_size']} company with a "
        f"market cap of approximately {company_info['market_cap']}.</div>",
        unsafe_allow_html=True,
    )

st.markdown(
    f"<div style='text-align:center; color:rgba(214,228,240,0.7); font-size:0.85rem;'>"
    f"{len(sub)} quarters covered, {period_start} to {period_end}</div>",
    unsafe_allow_html=True,
)

render_price_chart(selected_ticker, price_history, sub)

st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

# S&P 500's own 2-day return for each quarter's earnings date, for display
# in the quarter header next to the stock's own 2-day return -- built once
# here rather than inside the loop below.
sp_df_for_headers = None
if price_history is not None:
    sp_df_for_headers = pd.DataFrame(price_history["sp500"])
    sp_df_for_headers["date"] = pd.to_datetime(sp_df_for_headers["date"])
    sp_df_for_headers = sp_df_for_headers.sort_values("date").reset_index(drop=True)

# ── Per-quarter loop: one earnings report per iteration, rendering the
# "Visualize" chart toggle followed by the left/right column comparison. ──
for idx, row in sub.iterrows():
    note_key = f"{row['ticker']}_{row['fiscal_yearquarter']}"
    ret_pct = row["ret_2day"] * 100
    ret_str = f"{ret_pct:+.2f}%"

    sp_ret = sp_return_2day(sp_df_for_headers, row["earnings_date"]) if sp_df_for_headers is not None else None
    sp_ret_str = f"{sp_ret:+.2f}%" if sp_ret is not None else "n/a"
    excess_str = excess_return_str(ret_pct, sp_ret)
    abnormal_info = abnormal_returns_lookup.get(note_key, {})
    abnormal_str = abnormal_return_str(abnormal_info.get("market_model"))
    ma_z_suffix = market_adjusted_z_suffix(abnormal_info.get("market_adjusted"))

    st.html(f"<div id='{anchor_id(row['ticker'], row['fiscal_yearquarter'])}'></div>")

    st.markdown(
        f"<div class='quarter-header' style='text-align:center;'>{row['fiscal_yearquarter'].upper()} "
        f"&nbsp;|&nbsp; earnings {row['earnings_date'].strftime('%Y-%m-%d')}</div>"
        f"<div class='quarter-header' style='text-align:center;'>2-day return {ret_str} "
        f"&nbsp;|&nbsp; S&amp;P 2-day return {sp_ret_str}</div>"
        f"<div style=\"text-align:center; font-size:1.5rem; font-family:'Cormorant Garamond', serif; color:rgba(214,228,240,0.9); margin-bottom:0.3rem;\">"
        f"Excess return {excess_str}{ma_z_suffix} &nbsp;|&nbsp; "
        f"Beta-adjusted abnormal return {abnormal_str}</div>",
        unsafe_allow_html=True,
    )

    existing_note = notes_lookup.get(note_key, "")
    context_summary_text = context_summaries_lookup.get(note_key)

    with st.container(key=f"viz_{note_key}"):
        viz_toggle_id = f"viz_toggle_{note_key}"
        st.html(
            f"<input type='checkbox' id='{viz_toggle_id}' class='visualize-checkbox'>"
            f"<label for='{viz_toggle_id}' class='visualize-label'>Visualize</label>"
        )

        viz_fig = build_quarter_visualize_fig(selected_ticker, price_history, sub, idx, context_summary_text)
        if viz_fig is not None:
            st.plotly_chart(viz_fig, use_container_width=True, key=f"viz_chart_{note_key}")

    left, right, djnw_col = st.columns(3, gap="large")

    # LEFT: what was already known/priced-in, from real web-search research
    # (or the legacy fallback -- see section 4 above for which one fires).
    with left:
        st.markdown(
            "<div style='text-align:center; font-weight:bold;'>Contextualized interpretation</div>",
            unsafe_allow_html=True,
        )
        websearch_sections = websearch_long_lookup.get(note_key)
        if websearch_sections:
            st.html(format_websearch_context(websearch_sections, note_key))
        elif existing_note:
            st.html(format_context_text(existing_note))

            row_sources = sources_lookup.get(note_key, [])
            if row_sources:
                links_html = "".join(
                    f"<a href='{s['url']}' target='_blank' rel='noopener noreferrer' "
                    f"style='display:block; color:#4A90D9; font-size:0.82rem; "
                    f"margin-bottom:0.4rem; text-decoration:none;'>{s['label']}</a>"
                    for s in row_sources
                )
                verify_id = f"verify_{note_key}"
                st.html(
                    f"<div class='verify-toggle-wrap'>"
                    f"<input type='checkbox' id='{verify_id}'>"
                    f"<label for='{verify_id}'>Verify</label>"
                    f"<div class='verify-content'>{links_html}</div>"
                    f"</div>"
                )
        else:
            st.write("*No interpretation written yet for this quarter.*")

    # RIGHT: the AI-generated paragraph explaining the stock's 2-day move
    # (from earnings_241.json's final_paragraph) plus its neutral bullet-point
    # summary, for comparison against the left column's grounded context.
    with right:
        st.markdown(
            "<div class='right-panel'>"
            "<div style='text-align:center; font-weight:bold;'>Generated text</div>",
            unsafe_allow_html=True,
        )
        # Escape $ so it renders literally rather than as LaTeX math (the same
        # issue and fix used for the bullets below). Rendered via st.html, not
        # st.write/markdown, so it can be merged into one element together
        # with the spacer below -- keeping the paragraph text as its own
        # separate st.write() call would reintroduce an extra Streamlit
        # inter-element gap that the left column's version (heading + text in
        # one st.html call) doesn't have, throwing the two paragraphs' start
        # positions out of alignment again.
        paragraph_html = row["final_paragraph"].replace("$", "&#36;")
        if websearch_sections:
            # Matches the left column's first heading, hidden, so the
            # paragraph starts at the same height as the left column's text.
            first_heading = websearch_sections[0]["heading"]
            spacer_html = f"<div class='context-heading' style='visibility:hidden;'>{first_heading}</div>"
        elif existing_note:
            spacer_html = "<div class='context-heading' style='visibility:hidden;'>Prior Context</div>"
        else:
            spacer_html = ""
        st.html(
            f"{spacer_html}<p style='margin:0 0 0.6rem 0; text-align:justify;'>{paragraph_html}</p>"
        )

        bullets = bullets_lookup.get((row["ticker"], row["fiscal_yearquarter"]), [])
        if bullets:
            st.html(
                "<div style='display:flex; flex-direction:column; align-items:center; "
                "margin:1.2rem 0;'>"
                "<div style='width:2px; height:36px; background:#FFD700;'></div>"
                "<div style='width:0; height:0; "
                "border-left:7px solid transparent; border-right:7px solid transparent; "
                "border-top:11px solid #FFD700;'></div>"
                "</div>"
            )
            bullet_items = "".join(
                f"<li style='margin-bottom:0.3rem;'>{b.replace('$', '&#36;')}</li>"
                for b in bullets
            )
            st.html(
                f"<ul style='color:#D6E4F0; font-size:0.9rem; padding-left:1.2rem;'>"
                f"{bullet_items}</ul>"
            )

        # Read-only display of the human rating collected in the
        # "Comparative Study" section -- answers can only be set/changed
        # there, never here.
        comp_answer = comparative_answers_lookup.get(note_key, {})
        q1_answer = comp_answer.get("q1", "Not yet rated")
        q2_answer = comp_answer.get("q2", "Not yet rated")
        answer_text_style = "color:#FFFFFF; text-align:center;"
        st.html(
            "<div class='context-heading' style='margin-top:3rem; padding-top:1rem; "
            "border-top:1px solid rgba(74,144,217,0.3); text-align:center;'>Comparative Analysis</div>"
            f"<p style='margin-bottom:0.4rem; font-size:1.2rem; {answer_text_style}'>"
            f"<strong>1. {Q1_QUESTION}</strong><br>{q1_answer}</p>"
            f"<p style='margin-bottom:0; font-size:1.2rem; {answer_text_style}'>"
            f"<strong>2. {Q2_QUESTION}</strong><br>{q2_answer}</p>"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Selectable third-column coverage. All datasets are cached locally;
    # dashboard reruns never consume API calls.
    with djnw_col:
        third_column_labels = {
            "Dow Jones Newswires": "Dow Jones Newswires Coverage",
            "Massive / Benzinga": "Massive / Benzinga Coverage",
            "Massive": "Massive Coverage",
            "StockNews API": "StockNews API Coverage",
        }
        third_column_label = third_column_labels[third_column_source]
        st.markdown(
            f"<div style='text-align:center; font-weight:bold;'>{third_column_label}</div>",
            unsafe_allow_html=True,
        )
        third_column_lookups = {
            "Dow Jones Newswires": group_djnw_coverage_lookup,
            "Massive / Benzinga": massive_benzinga_coverage_lookup,
            "Massive": massive_news_coverage_lookup,
            "StockNews API": stocknews_coverage_lookup,
        }
        source_entry = third_column_lookups[third_column_source].get(note_key)
        if third_column_source == "StockNews API":
            # Written with the Why Moved 2 prompt: summary + explicit and
            # implicit reasons, plus a category table shown in a dialog.
            if source_entry:
                for field, heading in [
                    ("summary_analysis", "Summary Analysis"),
                    ("explicit_reasons", "Explicit Reasons"),
                    ("implicit_reasons", "Implicit Reasons"),
                ]:
                    if source_entry.get(field):
                        st.html(
                            f"<div class='context-heading'>{heading}</div>"
                            f"<p style='margin-bottom:0.8rem; text-align:justify;'>"
                            f"{render_inline_markdown(source_entry[field])}</p>"
                        )
                source_links = "".join(
                    render_djnw_source_link_html(source) for source in source_entry.get("sources", [])
                )
                if source_links:
                    st.html(source_links)
                if st.button("StockNews Categories", key=f"stocknews_cat_btn_{note_key}", use_container_width=True):
                    _show_why_moved_2_categories_dialog(source_entry, "StockNews API")
            else:
                st.write(f"*No {third_column_label} found for this observation.*")
        elif source_entry and (source_entry.get("summary_analysis") or source_entry.get("why_moved")):
            if source_entry.get("summary_analysis"):
                st.html(
                    "<div class='context-heading'>Summary Analysis</div>"
                    f"<p style='margin-bottom:0.8rem; text-align:justify;'>"
                    f"{render_inline_markdown(source_entry['summary_analysis'])}</p>"
                )
            if source_entry.get("why_moved"):
                st.html(
                    "<div class='context-heading'>Why The Stock Moved</div>"
                    f"<p style='margin-bottom:0.8rem; text-align:justify;'>"
                    f"{render_inline_markdown(source_entry['why_moved'])}</p>"
                )
            source_links = "".join(
                render_djnw_source_link_html(source)
                for source in source_entry.get("sources", [])
            )
            if source_links:
                st.html(source_links)
        else:
            st.write(f"*No {third_column_label} found for this observation.*")

    if note_key in group_pd_categories_lookup:
        action_spacer_l, pdcat_col, first_order_col, action_spacer_r = st.columns([1.5, 1, 1, 1.5])
        with pdcat_col:
            if st.button("PD Data Categories", key=f"main_pdcat_btn_{note_key}", use_container_width=True):
                _show_pd_categories_dialog(note_key)
        with first_order_col:
            if st.button(
                "First Order Categories",
                key=f"main_first_order_btn_{note_key}",
                use_container_width=True,
            ):
                _show_first_order_categories_dialog(note_key)

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)
