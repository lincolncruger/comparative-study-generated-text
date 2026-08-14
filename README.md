# Earnings Reaction Review

Interactive review of 241 AI-generated earnings-reaction explanations across
17 stocks (2017-2024), from the "Textual Analysis of Banks' Private
Information" project pipeline.

For each earnings-day observation, the dashboard shows two things side by
side:

- **Left — Contextualized interpretation.** What was actually known or
  priced-in going into that earnings report, and the actual news around the
  reaction. This is **not** generated from an LLM's training-data memory —
  it is built by running a web search for each observation's specific date
  window and condensing what real financial-media sources (Zacks,
  StockStory, Benzinga, Insider Monkey, PR Newswire, Barchart, GuruFocus,
  Investing.com, and similar outlets) actually reported at the time. Each
  paragraph has a "Verify" toggle linking out to the original source
  articles used to write it, so the grounding can be checked directly.
- **Right — Generated text.** The pipeline's AI-generated explanation of the
  stock's 2-day move, the object being evaluated for accuracy against the
  grounded context on the left.

## Comparative Study

A separate "Comparative Study" section lets you rate each observation's
generated text on two questions — whether it's true, and whether it
accurately explains the stock's post-earnings move. Answers are saved to
`data/comparative_answers_241.json` and shown read-only back in the "Data
Visualization" section, so they persist and travel with the dashboard for
anyone who runs it. An "All" tab gives a one-glance overview: every ticker's
observations as a column of dots, colored by rating status.

## Running it

Requires Python 3.9+.

```bash
pip install -r requirements.txt
streamlit run app.py
```

This opens the dashboard in your browser at `http://localhost:8501`. Nothing
is hosted remotely — it runs entirely on your own machine.
