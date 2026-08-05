import json
import os

import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data", "earnings_241.json")
NOTES_PATH = os.path.join(HERE, "data", "my_notes.json")

st.set_page_config(page_title="Earnings Reaction Review", layout="wide")

st.markdown(
    """
    <style>
    .right-panel {
        border-left: 1px solid rgba(128,128,128,0.4);
        padding-left: 1.5rem;
    }
    .quarter-header {
        font-size: 0.85rem;
        color: rgba(128,128,128,0.9);
        margin-bottom: 0.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_data():
    with open(DATA_PATH) as f:
        rows = json.load(f)
    df = pd.DataFrame(rows)
    df["earnings_date"] = pd.to_datetime(df["earnings_date"])
    return df.sort_values(["ticker", "earnings_date"])


def load_notes():
    if os.path.exists(NOTES_PATH):
        with open(NOTES_PATH) as f:
            return json.load(f)
    return {}


def save_notes(notes):
    with open(NOTES_PATH, "w") as f:
        json.dump(notes, f, indent=2)


df = load_data()

if "notes" not in st.session_state:
    st.session_state.notes = load_notes()

tickers = sorted(df["ticker"].unique())
ticker_labels = {
    t: f"{t} — {df.loc[df['ticker'] == t, 'company_name'].iloc[0]}"
    for t in tickers
}

st.sidebar.title("Earnings Reaction Review")
st.sidebar.caption(
    "Left: my own read on what drove the move. "
    "Right: the pipeline's generated explanation. "
    "17 stocks, 241 earnings-day observations, 2017-2024."
)
selected_ticker = st.sidebar.radio(
    "Stock",
    tickers,
    format_func=lambda t: ticker_labels[t],
)

sub = df[df["ticker"] == selected_ticker].reset_index(drop=True)
company_name = sub["company_name"].iloc[0]
period_start = sub["earnings_date"].min().strftime("%Y-%m-%d")
period_end = sub["earnings_date"].max().strftime("%Y-%m-%d")

st.title(f"{selected_ticker} — {company_name}")
st.caption(f"{len(sub)} quarters covered, {period_start} to {period_end}")
st.divider()

for _, row in sub.iterrows():
    note_key = f"{row['ticker']}_{row['fiscal_yearquarter']}"
    ret_pct = row["ret_2day"] * 100
    ret_str = f"{ret_pct:+.2f}%"

    st.markdown(
        f"<div class='quarter-header'>{row['fiscal_yearquarter'].upper()} "
        f"&nbsp;|&nbsp; earnings {row['earnings_date'].strftime('%Y-%m-%d')} "
        f"&nbsp;|&nbsp; 2-day return {ret_str}</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    with left:
        st.markdown("**My context / interpretation**")
        existing_note = st.session_state.notes.get(note_key, "")
        new_note = st.text_area(
            "note",
            value=existing_note,
            key=f"input_{note_key}",
            height=200,
            label_visibility="collapsed",
            placeholder="Write your own read on what actually drove this move...",
        )
        if new_note != existing_note:
            st.session_state.notes[note_key] = new_note
            save_notes(st.session_state.notes)

    with right:
        st.markdown("<div class='right-panel'>", unsafe_allow_html=True)
        st.markdown("**Generated explanation**")
        st.write(row["final_paragraph"])
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
