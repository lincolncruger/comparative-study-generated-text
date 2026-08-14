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
BULLETS_PATH = os.path.join(HERE, "data", "bullets_241.json")
SOURCES_PATH = os.path.join(HERE, "data", "sources_241.json")
CONTEXT_SUMMARIES_PATH = os.path.join(HERE, "data", "context_summaries_241.json")
WEBSEARCH_LONG_PATH = os.path.join(HERE, "data", "websearch_long_241.json")
COMPANY_INFO_PATH = os.path.join(HERE, "data", "company_info_241.json")
COMPARATIVE_ANSWERS_PATH = os.path.join(HERE, "data", "comparative_answers_241.json")

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


def format_websearch_context(sections, note_key):
    """Render the web-search-sourced context as HTML: each section (Prior
    Context / Current Earnings Release / Possible Drivers) as individual
    paragraphs, each with its own Verify button when that specific
    paragraph cites sources (paragraphs with no citation get none)."""
    long_parts = []
    for si, section in enumerate(sections):
        long_parts.append(f"<div class='context-heading'>{section['heading']}</div>")
        # Every paragraph in "Possible Drivers" is a First/Second/Third-order
        # driver item -- indent them slightly so they read as sub-items under
        # the section heading rather than flush-left like the other sections.
        indent_style = "padding-left:1.2rem; font-size:0.88rem;" if section["heading"] == "Possible Drivers" else ""
        for pi, para in enumerate(section["paragraphs"]):
            long_parts.append(f"<p style='margin-bottom:0.3rem; {indent_style}'>{render_inline_markdown(para['text'])}</p>")
            if para["sources"]:
                links_html = "".join(
                    f"<a href='{s['url']}' target='_blank' rel='noopener noreferrer' "
                    f"style='display:block; color:#4A90D9; font-size:0.78rem; "
                    f"margin-bottom:0.3rem; text-decoration:none;'>{s['label']}</a>"
                    for s in para["sources"]
                )
                verify_id = f"verify_{note_key}_{si}_{pi}"
                long_parts.append(
                    f"<div class='verify-para-wrap' style='{indent_style}'>"
                    f"<input type='checkbox' id='{verify_id}'>"
                    f"<label for='{verify_id}'>Verify</label>"
                    f"<div class='verify-para-content'>{links_html}</div>"
                    f"</div>"
                )
    long_html = "".join(long_parts)
    return f"<div class='format-body'>{long_html}</div>"


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
bullets_lookup = load_bullets(_mtime(BULLETS_PATH))
sources_lookup = load_sources(_mtime(SOURCES_PATH))
context_summaries_lookup = load_context_summaries(_mtime(CONTEXT_SUMMARIES_PATH))
websearch_long_lookup = load_websearch_long(_mtime(WEBSEARCH_LONG_PATH))
company_info_lookup = load_company_info(_mtime(COMPANY_INFO_PATH))
comparative_answers_lookup = load_comparative_answers(_mtime(COMPARATIVE_ANSWERS_PATH))
notes_lookup = load_notes(_mtime(NOTES_PATH))

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

sections = ["Data Visualization", "Comparative Study"]
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

    sp_ret_str = "n/a"
    if sp_df_for_headers is not None:
        sp_ret = sp_return_2day(sp_df_for_headers, row["earnings_date"])
        if sp_ret is not None:
            sp_ret_str = f"{sp_ret:+.2f}%"

    st.html(f"<div id='{anchor_id(row['ticker'], row['fiscal_yearquarter'])}'></div>")

    st.markdown(
        f"<div class='quarter-header' style='text-align:center;'>{row['fiscal_yearquarter'].upper()} "
        f"&nbsp;|&nbsp; earnings {row['earnings_date'].strftime('%Y-%m-%d')} "
        f"&nbsp;|&nbsp; 2-day return {ret_str} &nbsp;|&nbsp; S&amp;P 2-day return {sp_ret_str}</div>",
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
