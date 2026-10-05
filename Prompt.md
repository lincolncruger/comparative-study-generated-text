# "Prompt" summarization prompt template

Reusable prompt template for having an agent read raw news-article text (from any
provider — WSJ, DJNW, Massive/Benzinga, StockNews, etc.) and write grounded
`summary_analysis` + `why_moved` fields for an earnings observation. Originally
built for the WSJ Coverage column in Data Visualization 2, then reused as-is for
DJNW and Massive/Benzinga.

Replace the bracketed placeholders (`[SOURCE]`, `[input file path]`,
`[output file path]`) per batch. Everything else below is the reusable core —
edit it here as the approach evolves, and copy the updated version into future
batch-agent prompts.

---

```
You are writing [SOURCE]-grounded analysis for a financial dashboard's "[SOURCE] Coverage" column, for a set of companies' earnings observations.

Read: [input file path]

It's a JSON object keyed by note_key (e.g. "TJX_2016q2"). Each entry has: ticker, company_name, fiscal_yearquarter, earnings_date, ret_2day_pct/ret_1day_pct/ret_1daypost_pct/ret_3day_pct/ret_5day_pct (real market data -- for your own orientation only, see the critical rule below), and "articles": a list of zero or more [SOURCE] articles with full extracted text (filename, title, published_date, text) matched to that earnings event.

For EVERY observation with at least one article (skip any with an empty articles list entirely -- do not write anything for those), write two paragraphs:

1. "summary_analysis" (aim for 5-8 sentences, genuinely substantive): what the article reports about the quarter -- results, guidance, segment/product detail, analyst names and consensus figures where the article gives them, management quotes, historical/comparative framing the article itself supplies (e.g. "first decline since X"). Reconstruct as much of the article's own context as it actually contains, not just the headline beat/miss.

2. "why_moved" (aim for 4-6 sentences): what the article itself says drove the stock's reaction. This is the most important rule in this whole task:

   *** CRITICAL RULE: "why_moved" must talk EXCLUSIVELY about what the article itself states. NEVER mention, cite, or compare against the ret_1day_pct/ret_2day_pct/ret_3day_pct/ret_5day_pct figures given to you in the input data. Those are OUR OWN computed numbers from real market data -- they are not something the article reported, and including them (even as a "consistency check" like "consistent with the 2-day return of +7%") misleadingly makes it look like the article said something it never said. Only use those numbers for your own background orientation (e.g. to gauge whether the move was large or small) -- NEVER write them into the output text, and never use phrases like "consistent with the given return" or "contradicts the recorded return." ***

   If the article states a specific reaction (e.g. "shares rose 2.5% to $61.29 in after-hours trading"), report that verbatim-in-spirit, since that number IS from the article. If the article gives an explanation for the move (a beat, a guidance change, a specific quote), describe it, building naturally on what you established in summary_analysis. If the article does NOT state a reaction at all, or does not explain it, just say so plainly ("the article does not report how shares reacted to this specific release") -- do not pad this out by referencing our own return data instead.

General rules:
- Everything must be grounded ONLY in the article text. No outside knowledge about the company, competitors, or later events.
- Some observations have multiple articles -- if one is a pre-earnings preview (published before or same-day, discussing expectations rather than results) and another is a reaction piece, use the preview for context and the reaction piece for the actual explanation, and have summary_analysis synthesize both naturally. If multiple are reaction/analysis pieces, synthesize them together.
- If an article is an opinion/analyst-column piece rather than straight news, that's fine to use -- just represent its tone as the column's own view where relevant.
- Third person, plain prose, no markdown, no bullet points.

Output: write to [output file path] -- a JSON object keyed by note_key (only for observations you wrote), each value: {"summary_analysis": "...", "why_moved": "...", "sources": [{"filename":..., "title":..., "published_date":...} for each article used]}.

Before finishing, search your own output text for any of these patterns and confirm none remain: "day return", "ret_", a percentage in parentheses that isn't from the article. Report how many entries you completed.
```

---

## Why these rules exist (don't drop them when editing)

- **Article-only `why_moved`**: added after a real correction mid-project — an early
  WSJ pass leaked our own computed panel-return numbers into `why_moved`, making it
  look like the article said something it never did. This is the single most
  important rule in the template.
- **Two-part structure** (context-heavy summary, then a narrower causal paragraph)
  reads better than one blob and keeps the causal claim separately checkable.
- **"If the article doesn't state a reaction, say so plainly"** stops the model from
  inventing a causal story that isn't actually in the source text.
- **Self-verification grep pass** at the end (`"day return"`, `"ret_"`, stray
  parenthetical percentages) has caught real leaks in later batches — keep it.

## Adapting per source

- `[SOURCE]` — the provider name (WSJ, DJNW, Massive/Benzinga, StockNews, ...).
- Article schema (`filename`/`title`/`published_date`/`text`) may need adjusting per
  provider — e.g. Massive/Benzinga articles also carry `url`/`benzinga_id` instead
  of `filename`; StockNews articles carry `news_url`/`source_name` instead.
- The `ret_*_pct` field list matches this project's group_observations.csv schema;
  keep it in sync if that schema changes.
