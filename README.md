# Earnings Reaction Review

Streamlit dashboard for reviewing and comparing earnings-reaction explanations
from the *Textual Analysis of Banks' Private Information* project pipeline.

The dashboard contains two datasets:

- The original 241-observation review covering 17 stocks from 2017–2024.
- A 300-observation comparative dataset covering 30 stocks, with ten
  observations per ticker centered on 2016–2018.

For each observation, the dashboard presents independently sourced coverage:

- **Contextualized interpretation** combines the current earnings release,
  observation-specific Possible Drivers analysis, and linked contemporary news.
- **WSJ Coverage** is derived exclusively from the corresponding Wall Street
  Journal PDF.
- **Dow Jones Newswires Coverage** is derived exclusively from the linked DJNW
  article when coverage is available.

Source links and PDF controls are included so the evidence can be checked
directly.

## PD Data Categories

The 300-observation dataset compares all three coverages across the same 11
categories:

1. Guidance
2. Order book / order backlog
3. Revenue
4. Product / Users
5. Profits and profitability
6. Costs
7. Debt, leverage and capital raise
8. Capex
9. Management
10. Litigation
11. Others, such as macroeconomic or exceptional events

Each populated category contains a positive or negative assessment followed by
a short factual summary. A category remains blank when that specific coverage
does not address it. **Product / Users** includes conventional product
performance and business-model-specific metrics such as MAUs, DAUs,
subscribers, members, engagement, and user growth.

## First Order Categories

The **First Order Categories** dialog identifies up to two categories that each
coverage most strongly implies were responsible for the stock's rise or fall.
These are not simply the most positive or negative categories in the report.
Selection follows the coverage's causal framing and is constrained to PD
evidence from that same source.

For contextualized coverage, the assessment uses all three evidence layers:
Possible Drivers, Current Earnings Release, and the linked reaction-news
article. WSJ and DJNW selections remain isolated to their respective coverage.
If an article reports a move without explaining its cause, the dashboard does
not force a First Order category.

The dialog also displays:

- Market-adjusted excess return and Z-score.
- Beta-adjusted abnormal return and Z-score.

Facebook observations retain their historical `FB` dashboard identifier, but
their price history is downloaded through `META`, which contains the same
security's pre-rename history.

## Comparative Study

The Comparative Study contains two subsections:

- **Data Visualization 1** lets reviewers assess whether generated text is true
  and whether it accurately explains the post-earnings move. Answers are stored
  in `data/comparative_answers_241.json`.
- **Data Visualization 2** lets reviewers independently rate the contextualized,
  WSJ, and DJNW coverage as **Accurate** or **Not accurate** for every available
  observation. Answers are stored in
  `data/group_coverage_accuracy_answers.json` and displayed beneath the matching
  coverage in the original Data Visualization 2 section.

Each subsection includes an **All** overview for quickly checking rating status.

## Rebuilding the data

Rebuild the complete PD and First Order datasets from the prepared,
source-specific records with:

```bash
python3 scripts/build_pd_category_review_set.py
```

This writes `data/group_pd_categories.json` and
`data/group_first_order_categories.json`.

Rebuild abnormal-return statistics with:

```bash
python3 compute_abnormal_returns.py
```

## Running the dashboard

Requires Python 3.9 or later.

```bash
pip install -r requirements.txt
streamlit run app.py
```

The dashboard opens at `http://localhost:8501` and runs locally.
