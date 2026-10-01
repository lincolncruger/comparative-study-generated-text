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

## Required evidence pipeline before prompting

The writing prompt is the final stage, not the retrieval stage. Run the following
deterministic pipeline for every observation before sending anything to the model.
An observation that fails a gate is quarantined for review rather than converted
into polished prose.

1. **Fetch the complete result set.** Query every configured news provider for the
   observation's full event window and follow every pagination cursor/page until
   exhausted. Do not stop after the first page, the first three articles, or a
   provider-defined default limit. Preserve the raw response unchanged. Record the
   provider, provider article ID, query, event window and retrieval timestamp.
2. **Resolve and test every source URL.** Follow redirects, save the final URL and
   HTTP status, and mark paywalls, login pages, generic home pages, deleted pages
   and error pages. A URL merely being non-empty is not validation. Never invent a
   replacement URL.
3. **Verify article identity.** Confirm that the destination headline and company
   match the API record and that the publication date falls inside the intended
   event window. Reject wrong-company, wrong-quarter and unrelated-event pages.
4. **Acquire usable article text.** Prefer the provider's licensed full text. When
   permitted, retrieve the publisher page as a fallback and extract the article
   body rather than navigation, promotional or sidebar text. Store the API text
   and extracted text separately. Mark each article `full_text`, `partial_text` or
   `snippet_only`; never silently present a snippet as a full article.
5. **Normalize, deduplicate and retain all relevant evidence.** Canonicalize URLs,
   collapse true duplicates/syndicated copies while preserving their provenance,
   and remove market roundups that only mention the ticker in passing. Do not use
   an arbitrary article cap. Every distinct relevant article available for the
   observation must reach the prompt, including previews, the initial earnings
   report, follow-up reaction pieces and analyst commentary.
6. **Build one self-contained observation packet.** Sort all retained sources from
   oldest to newest and include their validation metadata. Previews may establish
   expectations; post-release and follow-up pieces may establish results and the
   market's interpretation. Do not split one observation across independent model
   runs, because no run should reason from only a subset of its available evidence.
7. **Apply deterministic output validation.** Every number, expectation, quotation,
   reaction and causal statement in the drafted output must be traceable to at
   least one retained source. Verify the category schema, explicit/implicit rules,
   source order and URLs mechanically. Reject and retry outputs with unsupported
   claims; if they still fail, quarantine the observation rather than publishing it.

Minimum publication gate: at least one retained source must contain usable article
text that substantively reports the earnings, analyzes the results, or explains the
reaction. Snippet-only evidence may help discover a source but is not sufficient by
itself for a published observation. Dead or mismatched links are never shown as
verified sources. The pipeline must emit a separate audit report listing fetched,
deduplicated, retained, rejected and unreachable sources for every observation.

---

```
You are writing [SOURCE]-grounded analysis for a financial dashboard, for a set of companies' earnings observations.

Read: [input file path]

It's a JSON object keyed by note_key (e.g. "TJX_2016q2"). Each entry has: ticker, company_name, fiscal_yearquarter, earnings_date, ret_1day_pct/ret_2day_pct/ret_3day_pct/ret_5day_pct (real market data -- see the critical rule below), "articles": every distinct relevant [SOURCE] article available for that earnings event after exhaustive pagination and deterministic validation, and optionally "filings": the company's 8-K / earnings press release for that quarter. Each article includes its provider ID, title, publication date/time, original URL, resolved URL, URL status, title/company/date match results, text-completeness status and article text.

*** CRITICAL RULE: only present what the articles say. NEVER mention, cite, or compare against the ret_1day_pct/ret_2day_pct/ret_3day_pct/ret_5day_pct figures. They are OUR OWN computed numbers, not something any article reported, and writing them into the output makes it look like the article said something it never said. Use them only for your own background orientation. If an article states the stock's reaction (e.g. "shares fell 6% in after-hours trading"), report that, since it IS from the article. ***

The articles list is the complete evidence set for the observation. Read every article before writing. Do not select only the first few, stop after finding one plausible explanation, or ignore later follow-up coverage. Work through each observation in five steps.

STEP 1 -- SELECT QUALITY ARTICLES.
Review every supplied article. Keep every distinct article with usable text that does at least one of:
  - details the earnings report (results, guidance, segment figures);
  - provides analysis of the results;
  - explains why the stock reacted;
  - establishes pre-release expectations used by a later results/reaction article.
Discard everything else: brief headline items with no detail, snippet-only records, unreachable or title-mismatched links, general market roundups that mention the company in passing, and articles about a different quarter or a different event. Do not impose an article-count cap and do not discard a relevant article merely because another source covers the same broad topic; retain it when it adds distinct figures, expectations, quotations, reaction details or analysis.
If no article passes, skip the observation entirely -- write nothing for it.
Everything below uses ONLY the kept articles.
Order the kept articles chronologically by publication date and time, earliest first: the articles published closest to the earnings release come first, and articles from subsequent days follow in date order. Read them in that order.

STEP 2 -- IDENTIFY THE CATEGORIES THAT EXPLAIN THE MOVE.
Use exactly these 10 categories, with these definitions:

  "Guidance" -- FORWARD-LOOKING statements about what management, analysts or the article expects after the reported quarter: future revenue, profit, margins, costs, demand, capex, economic conditions or other outlook. Forward-looking commentary is classified here even when its subject would otherwise resemble another category. For example, management saying economic conditions will worsen belongs in Guidance, not Macro and micro development.
  "Order book / backlog" -- whether the order book or backlog is growing or shrinking for companies that sell products. This category has no separate temporal classification; use the backlog or order-book comparison that the coverage ties to the move.
  "Revenue" -- BACKWARD-LOOKING statements about revenue reported for the corresponding completed quarter: whether revenue beat or missed and how segments performed. Sales figures go here even when the article names a product (e.g. "iPhone sales fell" is Revenue). Future revenue expectations belong in Guidance.
  "New Product Release / Users" -- BACKWARD-LOOKING, ONGOING or FORWARD-LOOKING statements about a product launch or unveiling (e.g. Apple unveiling a new iPhone), or user gains or losses for companies that monetize users (e.g. Facebook adding users). This category concerns the product or users themselves, not sales figures.
  "Profits, costs and margin" -- BACKWARD-LOOKING statements about profitability in the corresponding completed quarter: EPS, net income, realized margins and operating costs, including one-time accounting items such as write-downs, restructuring charges and tax hits. Forecast profit, costs or margins belong in Guidance.
  "Debt, leverage and capital raise" -- ONGOING or BACKWARD-LOOKING statements about borrowing, leverage, completed or active share issuance, buybacks and other capital-structure moves. A purely future capital-structure forecast belongs in Guidance.
  "Capex" -- BACKWARD-LOOKING capital expenditure incurred during the corresponding completed quarter. Future capex plans or forecasts belong in Guidance.
  "Management" -- ONGOING or BACKWARD-LOOKING management changes, actions, execution, tone or strategy that occurred during or relate to the corresponding completed quarter. Do not place a forward-looking operating or economic forecast here merely because management delivered it; classify the substance of that forecast as Guidance.
  "Litigation" -- BACKWARD-LOOKING, ONGOING or FORWARD-LOOKING lawsuits and legal or regulatory proceedings.
  "Macro and micro development" -- BACKWARD-LOOKING developments within the corresponding completed quarter. Macro includes economy-wide forces such as trade wars, currency moves or weather; micro includes idiosyncratic company or industry developments such as a supplier problem, recall, plant outage or competitor action. A prediction that economic, industry or company-specific conditions will improve or worsen after the quarter belongs in Guidance, not this category.

Temporal routing is mandatory. Classify a statement according to both its subject
and its time orientation. Do not duplicate one statement across Guidance and a
backward-looking category. When a sentence combines completed-quarter facts with
a future outlook, separate the evidence: classify the realized result in its
backward-looking category and the forecast in Guidance, provided each is tied to
the stock's move under the attribution rules below.

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

STEP 5 -- VERIFY EVERY CLAIM AGAINST THE COMPLETE EVIDENCE SET.
Before writing the output, trace every reported number, expectation, quotation, stock reaction and causal statement to one or more kept articles. Reconcile apparent conflicts by checking dates, periods, GAAP versus adjusted measures, and whether an article is describing the current or a prior quarter. When reliable sources genuinely disagree, describe the disagreement and attribute each version; never silently choose one. Remove any statement that cannot be supported by the supplied text. Confirm that the synthesis reflects all material relevant coverage, not only the most convenient article.

General rules:
- Everything must be grounded ONLY in the kept articles (plus filings, for figures only). No outside knowledge about the company, competitors, or later events.
- Use the entire retained evidence set. Sparse output is acceptable only when the exhaustive, validated source set is genuinely sparse; it is not acceptable because the first article was treated as sufficient.
- Never describe a dead, mismatched, generic or snippet-only source as verified coverage.
- Never use the same figure or sentence as the evidence for two categories.
- If an article is an opinion or analyst column, represent its view as the column's own view.
- Third person, plain prose, no markdown, no bullet points in the paragraphs.

Sources: every news source used must be linked. "sources" lists every kept article and every filing you used, in the same chronological order (earliest first, closest to the earnings release), each with its validated resolved "url" copied exactly from the input -- never construct, shorten, or guess a URL. Don't list discarded articles. A source without a working validated URL fails the publication gate and must not be presented as verified dashboard coverage.

Output: write to [output file path] -- a JSON object keyed by note_key (only for observations you wrote), each value:
{
  "summary_analysis": "...",
  "explicit_reasons": "...",
  "implicit_reasons": "...",
  "categories": {"Guidance": {...} or null, ... all 10 ...},
  "sources": [{"title": ..., "published_date": ..., "url": ...} for each kept article and each filing used]
}

Before finishing, check every entry:
- the output text contains none of: "day return", "ret_", or a percentage in parentheses that isn't from the articles;
- "categories" has exactly the 10 keys above, spelled exactly;
- every included category states what was expected, or says the articles give no expectation;
- every explicit category appears in explicit_reasons, every implicit one in implicit_reasons, and nothing else is given as a reason;
- no category is marked explicit unless an article states the link;
- every numerical and causal claim can be located in at least one kept article;
- conflicts across sources are reconciled or explicitly attributed rather than hidden;
- every kept article and every filing used is in "sources", in chronological order (earliest first), with its validated resolved URL copied exactly from the input.
Report how many observations you wrote, how many you skipped for having no quality article, how many have no explicit category, how many sources were rejected by the evidence pipeline, and how many retained sources have no working validated URL.
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
- **Temporal routing is part of the category definition**: Guidance owns
  forward-looking statements, including forecasts about revenue, margins,
  capex, demand and future macro or micro conditions. Revenue, profits/costs/
  margin, capex, and macro/micro developments describe the corresponding
  completed quarter. A statement is never duplicated merely because its
  subject and its time orientation point to different categories.
- **Sales figures are Revenue, not Product**: the older category data filed
  "iPhone sales fell" under Product / Users. New Product Release / Users is
  only for launches and user numbers.
- **Filings only confirm figures**: an 8-K or press release is factual, but it
  can't say what was expected or why the stock moved.
- **Every source linked, URLs copied exactly**: every claim can be checked
  against its source from the dashboard. The retrieval pipeline must resolve
  and verify the link first; a non-empty but dead or generic URL is not valid.
  Reconstructed links are never guessed.
- **Exhaustive retrieval before writing**: every page and every relevant source
  available for the event is collected before the observation is summarized.
  Arbitrary top-three or first-page caps create sparse, biased explanations.
- **Quality gates before and after the prompt**: deterministic retrieval checks
  precede generation and deterministic claim/schema checks follow it.
  Observations that fail either gate are quarantined, not padded or published.

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
