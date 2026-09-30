# "Why Moved 2" summarization prompt template

Builds on `Why Moved.md` (which stays unchanged). One prompt, run on the articles
fetched from a news provider's API for each earnings observation, that:

1. keeps only the quality articles,
2. writes three paragraphs: a summary, the explicit reasons for the stock's
   move, and the implicit reasons,
3. fills a category table saying which of 10 categories the articles tie to the
   move, in which direction relative to expectations, and whether the link is
   explicit or implicit.

Explicit categories are the first-order reasons for the move; implicit ones are
second- or third-order reasons.

Replace the bracketed placeholders (`[SOURCE]`, `[input file path]`,
`[output file path]`) per batch. Everything else below is the reusable core.
Edit it here as the approach evolves.

---

```
You are writing [SOURCE]-grounded analysis for a financial dashboard, for a set of companies' earnings observations.

Read: [input file path]

It's a JSON object keyed by note_key (e.g. "TJX_2016q2"). Each entry has: ticker, company_name, fiscal_yearquarter, earnings_date, ret_1day_pct/ret_2day_pct/ret_3day_pct/ret_5day_pct (real market data -- see the critical rule below), "articles": a list of zero or more [SOURCE] articles fetched for that earnings event, and optionally "filings": the company's 8-K / earnings press release for that quarter.

*** CRITICAL RULE: only present what the articles say. NEVER mention, cite, or compare against the ret_1day_pct/ret_2day_pct/ret_3day_pct/ret_5day_pct figures. They are OUR OWN computed numbers, not something any article reported, and writing them into the output makes it look like the article said something it never said. Use them only for your own background orientation. If an article states the stock's reaction (e.g. "shares fell 6% in after-hours trading"), report that, since it IS from the article. ***

Work through each observation in four steps.

STEP 1 -- SELECT QUALITY ARTICLES.
Keep an article only if it does at least one of:
  - details the earnings report (results, guidance, segment figures);
  - provides analysis of the results;
  - explains why the stock reacted.
Discard everything else: brief headline items with no detail, general market roundups that mention the company in passing, and articles about a different quarter or a different event.
If no article passes, skip the observation entirely -- write nothing for it.
Everything below uses ONLY the kept articles.

STEP 2 -- IDENTIFY THE CATEGORIES THAT EXPLAIN THE MOVE.
Use exactly these 10 categories, with these definitions:

  "Guidance" -- guidance on future revenue, profit, etc.
  "Order book / backlog" -- for companies that sell products: whether the order book or backlog is growing or shrinking.
  "Revenue" -- whether revenue beat or missed, and how segments performed. Sales figures go here even when the article names a product (e.g. "iPhone sales fell" is Revenue).
  "New Product Release / Users" -- a product launch or unveiling (e.g. Apple unveiling a new iPhone), or user gains or losses for companies that monetize users (e.g. Facebook adding users). About the product or the users themselves, not the sales figures.
  "Profits, costs and margin" -- anything related to profitability: EPS, net income, margins, operating costs. Also one-time accounting items such as write-downs, restructuring charges and tax hits.
  "Debt, leverage and capital raise" -- borrowing, leverage, share issuance, buybacks and other capital-structure moves.
  "Capex" -- capital expenditure (e.g. a company increasing capex on data centers).
  "Management" -- management changes (e.g. a change of CEO), and management commentary, tone or strategy that the article highlights.
  "Litigation" -- lawsuits and legal or regulatory proceedings.
  "Macro and micro development" -- macro: economy-wide forces such as trade wars, currency moves or weather. Micro: one-time, idiosyncratic problems specific to the company or its industry, such as a supplier problem, a recall, a plant outage or a competitor's move.

A category is included only if the articles attribute the stock's move to it, explicitly or implicitly. A category the articles mention without tying it to the move is omitted. Many observations will leave several categories out (Litigation, Capex, etc.) -- that is expected.

Attribution:
  - EXPLICIT: an article states a direct cause-and-effect link between the category and the stock's move. E.g. "shares fell because profit disappointed", "the guidance cut sent shares lower", "investors punished the stock for weak margins". A link stated by analysts or another source that the article quotes also counts as explicit (e.g. "analysts said the guidance cut drove the selloff"). Several categories can be explicit.
  - IMPLICIT: an article presents the category as contributing to the sentiment or pressure on the stock, without directly tying it to the price move. E.g. "another factor contributing to the negative sentiment was debt management", "also weighing on investors", "adding to concerns". Two facts simply placed next to each other with no stated link (e.g. "The company cut its forecast. Shares fell 5%.") are implicit, not explicit.
  - If no category is explicitly linked to the move, all included categories are implicit. Never promote an implicit category to explicit.

Expectations: stocks move on the gap between results and expectations, not on events themselves. Every included category must be judged against what was expected:
  - State what happened AND what was expected, e.g. "Revenue was $50.6 billion versus roughly $52 billion expected."
  - The expectation must come from the articles: a consensus figure, an analyst estimate, the company's own earlier guidance, or the article's wording ("disappointed", "beat", "stronger than feared", "investors had hoped", "widely anticipated"). Figures and wording are equally acceptable. Never use outside knowledge of what consensus was.
  - For categories without numbers (a product release, a CEO change, a lawsuit, a macro event), the expectation is whether the articles present it as anticipated or as a surprise.
  - If the articles give no expectation at all for an included category, say so in its text ("the articles give no expectation for this").
  - "direction" follows the gap, not the raw number: revenue up 10% against 15% expected is negative. Where the articles give no expectation, direction follows how the articles say the category affected the stock.

Filings (8-K / press release), when provided, may only be used to confirm or correct the reported figures. Expectations and reasons for the move come only from the articles.

STEP 3 -- WRITE THREE PARAGRAPHS. Stay brief and concise on each category -- one or two sentences each -- while always keeping the "what happened compared to what was expected" structure.

1. "summary_analysis": opens with what the company reported and what the stock did, as the articles state it -- "Company X reported [results], and its shares [the reaction the articles report]." If no article reports the reaction, say so in that opening sentence instead. Then give a short overview: the direction of the move, the main reasons, and the highlights.

2. "explicit_reasons": the explicit categories, most important first, each as what happened versus what was expected and how it moved the stock. If there are none, write one sentence saying the articles don't explicitly attribute the move to any specific factor.

3. "implicit_reasons": the implicit categories, the same way. If there are none, write one sentence saying so.

STEP 4 -- FILL THE CATEGORY TABLE.
"categories" is an object with all 10 category names as keys, in the order above. For an included category, the value is {"direction": "positive" or "negative", "attribution": "explicit" or "implicit", "text": "..."} where "text" is one to three sentences: what happened versus what was expected, with the articles' own figures or wording. For an omitted category, the value is null. The table and the paragraphs must match: every explicit category is discussed in explicit_reasons, every implicit one in implicit_reasons, and no paragraph gives a reason that isn't in the table.

General rules:
- Everything must be grounded ONLY in the kept articles (plus filings, for figures only). No outside knowledge about the company, competitors, or later events.
- Never use the same figure or sentence as the evidence for two categories.
- If an article is an opinion or analyst column, represent its view as the column's own view.
- Third person, plain prose, no markdown, no bullet points in the paragraphs.

Output: write to [output file path] -- a JSON object keyed by note_key (only for observations you wrote), each value:
{
  "summary_analysis": "...",
  "explicit_reasons": "...",
  "implicit_reasons": "...",
  "categories": {"Guidance": {...} or null, ... all 10 ...},
  "sources": [{"title": ..., "published_date": ..., "url": ...} for each KEPT article]
}

Before finishing, check every entry:
- the output text contains none of: "day return", "ret_", or a percentage in parentheses that isn't from the articles;
- "categories" has exactly the 10 keys above, spelled exactly;
- every included category states what was expected, or says the articles give no expectation;
- every explicit category appears in explicit_reasons, every implicit one in implicit_reasons, and nothing else is given as a reason;
- no category is marked explicit unless an article states the link.
Report how many observations you wrote, how many you skipped for having no quality article, and how many have no explicit category.
```

---

## Why these rules exist (don't drop them when editing)

- **Only what the articles say**: carried over from `Why Moved.md`. An early
  WSJ pass leaked our own computed returns into the text, making it look like
  the article said something it never said. This is still the single most
  important rule.
- **Expectations on every category**: stocks move on the difference between
  results and expectations, not on the events themselves. "Revenue was $X"
  explains nothing without what was expected.
- **Explicit vs. implicit**: separates first-order reasons for the move (the
  article states the link) from second- and third-order ones (the article only
  says it added to the sentiment). It's based on the article's wording, not on
  the model's own judgment of importance.
- **Two facts side by side count as implicit**: wire stories often place a
  result next to the stock move without saying one caused the other. Only a
  stated link counts as explicit.
- **Categories not tied to the move are omitted**: the table is about why the
  stock moved, not everything the quarter contained.
- **Sales figures are Revenue, not Product**: the older category data filed
  "iPhone sales fell" under Product / Users. New Product Release / Users is
  only for launches and user numbers.
- **Filings only confirm figures**: an 8-K or press release is factual, but it
  can't say what was expected or why the stock moved.
- **Quality filter in the same prompt**: keeps the pipeline to one call per
  batch; observations with no quality article are skipped, not padded.

## Adapting per source

- `[SOURCE]`: the provider name (WSJ, DJNW, Massive/Benzinga, Alpha News
  Stream, ...).
- The article fields differ by provider (e.g. Massive/Benzinga has
  `title`/`published_date`/`url`/`benzinga_id`; Alpha News Stream has
  `headline`/`date`/`source`/`url`/`summary`). Adjust the input description,
  and put `url` in `sources` whenever the provider gives one so the dashboard
  can link it.
- These 10 categories differ from the 11 in `PD_CATEGORIES` in `app.py`
  (Profits and Costs are merged, and three others are renamed). The dashboard's
  existing category table uses the old 11, so it will need updating before it
  can display output from this prompt.
- The `ret_*_pct` field list matches this project's `group_observations.csv`
  schema. Keep it in sync if that schema changes.
