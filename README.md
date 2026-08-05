# Earnings Reaction Review

Interactive review of 241 AI-generated earnings-reaction explanations across
17 stocks (2017-2024), from the "Textual Analysis of Banks' Private
Information" project pipeline.

For each earnings-day observation: the pipeline's generated explanation of
the stock move (right) next to a space for your own read on what actually
drove it (left), so the two can be compared side by side.

## Running it

Requires Python 3.9+.

```bash
pip install -r requirements.txt
streamlit run app.py
```

This opens the dashboard in your browser at `http://localhost:8501`. Nothing
is hosted remotely — it runs entirely on your own machine.

## Notes

Anything typed into the left-hand "My context / interpretation" box is saved
locally to `data/my_notes.json` as you type. This file is local to whoever
is running the app — it does not sync back to anyone else automatically.
