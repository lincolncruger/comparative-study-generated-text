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
GROUP_CONTEXT_PATH = os.path.join(HERE, "data", "group_context.json")
GROUP_WSJ_COVERAGE_PATH = os.path.join(HERE, "data", "group_wsj_coverage.json")
GROUP_DJNW_COVERAGE_PATH = os.path.join(HERE, "data", "group_djnw_coverage.json")
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
notes_lookup = load_notes(_mtime(NOTES_PATH))
group_df = load_group_returns(_mtime(GROUP_RETURNS_PATH))
group_price_history = load_group_price_history(_mtime(GROUP_PRICE_HISTORY_PATH))
group_context_lookup = load_group_context(_mtime(GROUP_CONTEXT_PATH))
group_abnormal_returns_lookup = load_group_abnormal_returns(_mtime(GROUP_ABNORMAL_RETURNS_PATH))
group_wsj_coverage_lookup = load_group_wsj_coverage(_mtime(GROUP_WSJ_COVERAGE_PATH))
group_djnw_coverage_lookup = load_group_djnw_coverage(_mtime(GROUP_DJNW_COVERAGE_PATH))

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

sections = ["Data Visualization", "Data Visualization 2", "Comparative Study"]
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

    g_filter_spacer, g_filter_col1, g_filter_col2 = st.columns([5, 2.3, 3.2])
    with g_filter_col1:
        g_filter_wsj = st.checkbox("Show Context Analysis + WSJ Coverage", key="g_filter_context_wsj")
    with g_filter_col2:
        g_filter_djnw = st.checkbox(
            "Show Context Analysis + WSJ Coverage + Dow Jones Newswires Coverage",
            key="g_filter_context_wsj_djnw",
        )

    st.markdown(
        f"<div class='quarter-header' style='font-size:1.4rem; text-align:center;'>{g_ticker} — {g_company_name}</div>",
        unsafe_allow_html=True,
    )

    def _quarter_has_coverage(fiscal_yearquarter, need_wsj, need_djnw):
        # Unchecking both filters resets to "All" -- the default -- rather
        # than needing a separate "All" option, per how these were asked
        # for. If both filters are checked at once, the stricter one
        # (context + WSJ + DJNW) wins, since it's a subset of the other.
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

    if g_filter_djnw:
        g_sub = g_sub_middle10[
            g_sub_middle10["fiscal_yearquarter"].apply(lambda fq: _quarter_has_coverage(fq, True, True))
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
    if g_filter_wsj or g_filter_djnw:
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
            g_wsj_pre = f"<div class='format-body'>{g_wsj_pre_inner}</div>"
            g_wsj_post = f"<div class='format-body'>{g_wsj_post_inner}</div>"
        else:
            g_wsj_pre = "<p><em>No WSJ coverage found for this observation.</em></p>"
            g_wsj_post = ""

        g_djnw_entry = group_djnw_coverage_lookup.get(g_context_key)
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
            g_djnw_pre = f"<div class='format-body'>{g_djnw_pre_inner}</div>"
            g_djnw_post = f"<div class='format-body'>{g_djnw_post_inner}</div>"
        else:
            g_djnw_pre = "<p><em>No Dow Jones Newswires coverage found for this observation.</em></p>"
            g_djnw_post = ""

        st.html(
            "<div style='display:grid; grid-template-columns: 1fr 1fr 1fr; "
            "column-gap:2.5rem; align-items:start;'>"
            "<div style='text-align:center; font-weight:bold; grid-column:1; grid-row:1;'>"
            "Contextualized interpretation</div>"
            "<div style='text-align:center; font-weight:bold; grid-column:2; grid-row:1;'>WSJ Coverage</div>"
            "<div style='text-align:center; font-weight:bold; grid-column:3; grid-row:1;'>"
            "Dow Jones Newswires Coverage</div>"
            f"<div style='grid-column:1; grid-row:2;'>{g_left_pre}</div>"
            f"<div style='grid-column:2; grid-row:2;'>{g_wsj_pre}</div>"
            f"<div style='grid-column:3; grid-row:2;'>{g_djnw_pre}</div>"
            f"<div style='grid-column:1; grid-row:3;'>{g_left_post}</div>"
            f"<div style='grid-column:2; grid-row:3;'>{g_wsj_post}</div>"
            f"<div style='grid-column:3; grid-row:3;'>{g_djnw_post}</div>"
            "</div>"
        )

        st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)

    st.stop()

if st.session_state.selected_section == "Comparative Study":
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

    left, right = st.columns(2, gap="large")

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

    st.markdown("<hr class='quarter-divider'/>", unsafe_allow_html=True)
