#!/usr/bin/env python3
"""Fetch and cache Massive/Benzinga coverage for Data Visualization 2's 30
market-cap-group tickers (group_observations.csv -- the middle-10-quarters
subset actually shown per ticker, not each ticker's full history).

Same fetch/scoring/narrative-synthesis logic as build_massive_benzinga_
coverage.py (the Data Visualization 1 version of this script), just
retargeted at a different ticker set and observation source, with its own
COMPANY_TERMS built from this project's existing NVDA/AAPL/... alt-name
list (see match_wsj_pdfs.py's ALT_NAMES, which this mirrors).

Run:
    python3 scripts/build_group_massive_benzinga_coverage.py
"""

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "group_observations.csv"
OUTPUT_PATH = ROOT / "data" / "group_massive_benzinga_coverage.json"
API_URL = "https://api.massive.com/benzinga/v2/news"

# Mirrors match_wsj_pdfs.py's ALT_NAMES -- the same alt-name list already
# validated against real WSJ/DJNW headline text for these 30 tickers.
COMPANY_TERMS = {
    "NVDA": ("nvidia",),
    "AAPL": ("apple",),
    "GOOGL": ("google", "alphabet"),
    "MSFT": ("microsoft",),
    "AMZN": ("amazon",),
    "AVGO": ("broadcom",),
    "FB": ("facebook",),
    "TSLA": ("tesla",),
    "LLY": ("eli lilly", "lilly"),
    "WMT": ("walmart", "wal-mart", "wal mart"),
    "CAT": ("caterpillar",),
    "GE": ("general electric", "ge"),
    "PG": ("procter & gamble", "procter and gamble", "p&g"),
    "NFLX": ("netflix",),
    "HD": ("home depot",),
    "PANW": ("palo alto networks",),
    "PM": ("philip morris",),
    "TXN": ("texas instruments",),
    "KLAC": ("kla",),
    "AMAT": ("applied materials",),
    "TJX": ("tjx", "t.j. maxx", "marshalls"),
    "NEM": ("newmont",),
    "ISRG": ("intuitive surgical",),
    "LMT": ("lockheed martin", "lockheed"),
    "SBUX": ("starbucks",),
    "CVS": ("cvs",),
    "LOW": ("lowe's", "lowes"),
    "ADBE": ("adobe",),
    "MAR": ("marriott",),
    "F": ("ford motor", "ford"),
}

EVENT_TERMS = re.compile(
    r"\b(earnings?|eps|revenue|sales|results?|quarter|guidance|outlook|forecast|profit|loss(?:es)?)\b",
    re.I,
)
MOVE_TERMS = re.compile(
    r"\b(why.{0,8}mov|mover|shares?|stock|rose|rises?|jump|gain|fell|falls?|drop|declin|slid|surge)\b",
    re.I,
)
EXPECTATION_TERMS = re.compile(
    r"\b(beat|beats|beating|miss|misses|missed|above|below|ahead|short|estimate|consensus|expected)\b",
    re.I,
)
CAUSE_TERMS = re.compile(r"\b(after|because|following|as|amid|despite|on|driven|due to|weigh|boost)\b", re.I)
EXPLICIT_CAUSE_TERMS = re.compile(
    r"\b(after|because|following|amid|despite|driven by|due to|on news of|on reports? of)\b",
    re.I,
)
PREVIEW_TERMS = re.compile(
    r"\b(preview|earnings scheduled|earnings preview|ahead of earnings|before the bell|after the bell|"
    r"imminent|analysts revise forecasts ahead|most accurate analysts)\b",
    re.I,
)
REACTION_TERMS = re.compile(
    r"\b(analyst|price target|maintains|raises|lowers|upgrades?|downgrades?|reiterates?)\b",
    re.I,
)
CONTEXT_TERMS = re.compile(
    r"\b(demand|orders?|backlog|margin|costs?|pricing|prices?|volume|traffic|customers?|"
    r"market|growth|decline|headwinds?|tailwinds?|supply|labor|wages?|product|segment|"
    r"management|CEO|expects?|strategy|competition|capacity|production|shipments?|"
    r"investment|acquisition|restructuring|currency|China|regulatory|outlook|guidance)\b",
    re.I,
)
BOILERPLATE_TERMS = re.compile(
    r"\b(earnings scheduled|companies reporting|stocks? moving|price action|"
    r"click here|read more|according to data from|benzinga pro|new investors should|"
    r"bulls will hope|past earnings performance|trading volume|after the closing bell|"
    r"before the opening bell|analysts expect .{0,80} to post quarterly)\b",
    re.I,
)


def load_api_key():
    value = os.environ.get("MASSIVE_API_KEY")
    if value:
        return value.strip()
    env_path = ROOT / ".env"
    for line in env_path.read_text().splitlines():
        name, separator, candidate = line.partition("=")
        if separator and name.strip() == "MASSIVE_API_KEY":
            return candidate.strip()
    raise RuntimeError("MASSIVE_API_KEY is not configured")


def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", html.unescape(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def clipped_sentence(value, limit=420):
    value = clean_text(value)
    if len(value) <= limit:
        return value
    shortened = value[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return shortened + "."


def sentences(value):
    text = clean_text(value)
    text = re.sub(r"(?<=\b[A-Z])\.(?=[A-Z]\b)", "<DOT>", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9$])", text)
    return [part.replace("<DOT>", ".").strip() for part in parts if len(part.strip()) >= 30]


def fetch_ticker(ticker, start, end, api_key):
    params = {
        "tickers": ticker,
        "published.gte": start.strftime("%Y-%m-%d"),
        "published.lte": end.strftime("%Y-%m-%d"),
        "limit": 50000,
        "sort": "published.asc",
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    # apiKey as a query param is silently rejected by this endpoint (the
    # connection is accepted then dropped with no HTTP response at all --
    # confirmed directly with curl). The key must be a Bearer token.
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    last_error = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.load(response)
            break
        except (ConnectionResetError, TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            delay = 5 * (attempt + 1)
            print(f"{ticker}: transient error ({exc}); retrying in {delay}s", flush=True)
            time.sleep(delay)
    else:
        raise RuntimeError(f"Benzinga request failed for {ticker} after retries: {last_error}")
    if payload.get("status") != "OK":
        raise RuntimeError(f"Benzinga request failed for {ticker}: {payload.get('error')}")
    return payload.get("results") or []


def mentions_company(article, ticker, title_only=True):
    fields = [clean_text(article.get("title"))]
    if not title_only:
        fields.extend((clean_text(article.get("teaser")), clean_text(article.get("body"))))
    text = " ".join(fields).lower()
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in COMPANY_TERMS[ticker])


def relevance(article, ticker):
    title = clean_text(article.get("title"))
    teaser = clean_text(article.get("teaser"))
    channels = " ".join(article.get("channels") or [])
    tags = " ".join(article.get("tags") or [])
    text = " ".join((title, teaser, channels, tags))
    return (
        8 * mentions_company(article, ticker)
        + 5 * bool(EVENT_TERMS.search(title))
        + 3 * bool(MOVE_TERMS.search(title))
        + 2 * bool(EVENT_TERMS.search(teaser))
        + 2 * bool(re.search(r"earnings|movers|after-hours|pre-market", channels, re.I))
        + bool(re.search(r"why.it.s.moving", tags, re.I))
    )


def article_date(article):
    return pd.to_datetime(article.get("published"), utc=True).tz_convert(None).normalize()


def evidence_sentences(article, ticker):
    direct_title = mentions_company(article, ticker)
    candidates = sentences(article.get("teaser")) + sentences(article.get("body"))
    result = []
    for sentence in candidates:
        mentions = any(
            re.search(rf"\b{re.escape(term)}\b", sentence, re.I)
            for term in COMPANY_TERMS[ticker]
        )
        if (mentions or direct_title) and (EVENT_TERMS.search(sentence) or MOVE_TERMS.search(sentence)):
            result.append(sentence)
    return result


def explicitly_about_company(sentence, ticker):
    return any(
        re.search(rf"\b{re.escape(term)}\b", sentence, re.I)
        for term in COMPANY_TERMS[ticker]
    )


def explicit_move_sentences(article, ticker):
    """Return only sentences that explicitly connect this company's move with news."""
    candidates = sentences(article.get("teaser")) + sentences(article.get("body"))
    result = []
    for sentence in candidates:
        if not explicitly_about_company(sentence, ticker) or not MOVE_TERMS.search(sentence):
            continue
        if EXPLICIT_CAUSE_TERMS.search(sentence) and (
            EVENT_TERMS.search(sentence) or EXPECTATION_TERMS.search(sentence)
        ):
            result.append(sentence)
    return result


def article_kind(article, ticker):
    title = clean_text(article.get("title"))
    direct = mentions_company(article, ticker)
    if PREVIEW_TERMS.search(title):
        return "preview"
    if direct and (
        REACTION_TERMS.search(title)
        or re.search(r"\b(landscape|insights?|exploring|deep dive|peeling back)\b", title, re.I)
    ):
        return "reaction"
    if explicit_move_sentences(article, ticker):
        return "mover"
    if direct and EVENT_TERMS.search(title):
        return "results"
    return "incidental"


def sentence_score(sentence, movement=False):
    return (
        5 * bool(EXPECTATION_TERMS.search(sentence))
        + 4 * bool(re.search(r"\b(guidance|outlook|forecast)\b", sentence, re.I))
        + 3 * bool(re.search(r"[$%]|\b\d+(?:\.\d+)?\b", sentence))
        + 2 * bool(EVENT_TERMS.search(sentence))
        + (6 * bool(MOVE_TERMS.search(sentence)) if movement else 0)
        + (4 * bool(CAUSE_TERMS.search(sentence)) if movement else 0)
    )


def unique_ranked(sentences_to_rank, limit, movement=False):
    ranked = sorted(sentences_to_rank, key=lambda text: sentence_score(text, movement), reverse=True)
    chosen = []
    normalized = []
    for sentence in ranked:
        key = re.sub(r"[^a-z0-9]+", " ", sentence.lower()).strip()
        if any(key in old or old in key for old in normalized):
            continue
        chosen.append(clipped_sentence(sentence, 440))
        normalized.append(key)
        if len(chosen) == limit:
            break
    return chosen


def contextual_highlights(ticker, selected, limit=5):
    candidates = []
    for article, kind in selected:
        if kind not in {"results", "mover"}:
            continue
        title_direct = mentions_company(article, ticker)
        for sentence in sentences(article.get("body")) + sentences(article.get("teaser")):
            if (
                BOILERPLATE_TERMS.search(sentence)
                or re.search(r"here's a look at|historical earnings performance|peer ratings overview|company consensus revenue", sentence, re.I)
                or re.search(r"\b(debt management|some analysts|consensus among analysts|total ratings|providing deeper insights)\b", sentence, re.I)
                or not CONTEXT_TERMS.search(sentence)
            ):
                continue
            if not (title_direct or explicitly_about_company(sentence, ticker)):
                continue
            if re.match(r"^(?:the company |\w+(?:,? inc\.?)? ).{0,35}reported quarterly", sentence, re.I):
                continue
            score = (
                5 * bool(re.search(r"\b(because|driven|attributed|citing|reflects?|due to|weigh|helped|amid)\b", sentence, re.I))
                + 4 * bool(re.search(r"\b(guidance|outlook|forecast|expects?|raised|lowered|reaffirmed)\b", sentence, re.I))
                + 3 * bool(re.search(r"\b(demand|orders?|backlog|margin|costs?|pricing|volume|traffic|supply|labor)\b", sentence, re.I))
                + 2 * bool(re.search(r"\b(analyst|CEO|management|investors?)\b", sentence, re.I))
                - 3 * bool(re.search(r"\b(?:EPS|revenue|sales) of \$?\d", sentence, re.I))
            )
            candidates.append((score, sentence))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return unique_ranked([sentence for _, sentence in candidates], limit)


def numerical_guidance_signal(titles):
    signals = []
    pattern = re.compile(
        r"(?:adjusted\s+)?(?:EPS|revenue|sales)[^$]{0,35}\$?(\d+(?:\.\d+)?)"
        r"(?:\s*[-–]\s*\$?(\d+(?:\.\d+)?))?.{0,45}?\bvs\.?\s*\$?(\d+(?:\.\d+)?)",
        re.I,
    )
    for title in titles:
        for low, high, consensus in pattern.findall(title):
            midpoint = (float(low) + float(high or low)) / 2
            estimate = float(consensus)
            if estimate and midpoint > estimate * 1.01:
                signals.append(1)
            elif estimate and midpoint < estimate * 0.99:
                signals.append(-1)
            else:
                signals.append(0)
    return sum(signals)


def coverage_narrative(ticker, selected):
    """Write an editorial synthesis; source metrics support rather than lead it."""
    titles = [clean_text(article.get("title")) for article, _ in selected]
    result_titles = [
        title for title in titles
        if re.search(r"\b(EPS|earnings|results?|profit|sales|revenue)\b", title, re.I)
        and not PREVIEW_TERMS.search(title)
        and not re.search(r"scheduled|stocks? to watch|biggest movers|moving in|market update", title, re.I)
    ]
    result_text = " ".join(result_titles)
    eps_beat = bool(re.search(r"EPS.{0,120}?\bbeats?\b", result_text, re.I))
    eps_miss = bool(re.search(r"EPS.{0,120}?\bmiss(?:es|ed)?\b", result_text, re.I))
    sales_beat = bool(re.search(r"(?:sales|revenue).{0,120}?\bbeats?\b", result_text, re.I))
    sales_miss = bool(re.search(r"(?:sales|revenue).{0,120}?\bmiss(?:es|ed)?\b", result_text, re.I))

    positives = sum((eps_beat, sales_beat))
    negatives = sum((eps_miss, sales_miss))
    if positives and not negatives:
        opening = "Coverage portrayed the quarter as broadly stronger than expected"
        detail = "both earnings and sales beat expectations" if positives == 2 else "the principal reported measure beat expectations"
    elif negatives and not positives:
        opening = "Coverage portrayed the quarter as weaker than expected"
        detail = "both earnings and sales missed expectations" if negatives == 2 else "a principal reported measure missed expectations"
    elif positives and negatives:
        opening = "Coverage portrayed the quarter as mixed"
        if eps_beat and sales_miss:
            detail = "earnings beat expectations but sales fell short"
        elif eps_miss and sales_beat:
            detail = "sales beat expectations but earnings fell short"
        else:
            detail = "the headline measures pointed in different directions"
    else:
        opening = "Coverage focused on the earnings release and its implications"
        detail = "the articles did not provide a consistent beat-or-miss framing"

    guidance_titles = [
        title for title in titles
        if re.search(r"\b(guidance|outlook|forecast|sees FY|sees Q[1-4])\b", title, re.I)
        and not PREVIEW_TERMS.search(title)
    ]
    guidance_text = " ".join(guidance_titles)
    numeric_signal = numerical_guidance_signal(guidance_titles)
    if re.search(r"\breaffirms?\b", guidance_text, re.I):
        forward = "Management reaffirmed its outlook, leaving the current quarter—not a guidance reset—as the main focus."
    elif re.search(r"\b(cuts?|lowers?|weak|below|down from|sales down)\b", guidance_text, re.I):
        forward = "The main forward-looking concern was reduced or below-expectation guidance."
    elif re.search(r"\b(raises?|boosts?|upbeat|tops?|above)\b", guidance_text, re.I):
        forward = "The forward-looking highlight was a raised or above-expectation outlook."
    elif numeric_signal < 0:
        forward = "The main forward-looking concern was reduced or below-expectation guidance."
    elif numeric_signal > 0:
        forward = "The forward-looking highlight was a raised or above-expectation outlook."
    elif guidance_titles:
        forward = "The coverage also emphasized management's outlook, but did not characterize it consistently as a clear positive or negative."
    else:
        forward = "The retrieved coverage did not identify a separate guidance change as a major theme."

    analyst_titles = [title for title in titles if REACTION_TERMS.search(title)]
    if analyst_titles:
        raised = sum(bool(re.search(r"raises?|upgrades?", title, re.I)) for title in analyst_titles)
        lowered = sum(bool(re.search(r"lowers?|downgrades?", title, re.I)) for title in analyst_titles)
        firms = []
        for title in analyst_titles:
            firm = re.split(r"\b(?:Maintains?|Upgrades?|Downgrades?|Raises?|Lowers?)\b", title, maxsplit=1, flags=re.I)[0]
            firm = re.sub(r"\b(?:What|Here|Analyst|Ratings?|Insights?).*$", "", firm, flags=re.I).strip(" :-")
            if firm and len(firm.split()) <= 5 and firm not in firms:
                firms.append(firm)
        firm_text = f" Firms represented included {', '.join(firms[:4])}." if firms else ""
        if raised > lowered:
            reaction = f"Post-release analyst coverage leaned constructive, with more upgrades or target increases than negative revisions.{firm_text}"
        elif lowered > raised:
            reaction = f"Post-release analyst coverage leaned cautious, with downgrades or target reductions outweighing positive revisions.{firm_text}"
        else:
            reaction = f"Post-release analyst reactions were mixed or largely unchanged.{firm_text}"
    else:
        reaction = ""
    highlights = contextual_highlights(ticker, selected, 5)
    context = ""
    if highlights:
        context = "Beyond the headline result, the articles supplied the following operating and market context: " + " ".join(highlights)
    return " ".join(
        part for part in (f"{opening}: {detail}.", forward, context, reaction) if part
    )


def movement_narrative(selected, explicit_drivers, observed_return, summary):
    direction = "rose" if observed_return > 0 else "fell" if observed_return < 0 else "was little changed"
    magnitude = abs(observed_return) * 100
    reaction = f"The stock {direction} {magnitude:.1f}% over the two-day earnings window."
    if explicit_drivers:
        evidence = " ".join(explicit_drivers).lower()
        if "better-than-expected" in evidence or "upbeat results" in evidence:
            attribution = "Benzinga explicitly attributed the move to better-than-expected quarterly results."
        elif "narrower" in evidence and "loss" in evidence:
            attribution = "Benzinga explicitly attributed the rise to a narrower quarterly loss."
        elif re.search(r"rais(?:ed|es|ing).{0,45}guidance", evidence):
            attribution = "Benzinga explicitly attributed the reaction to the earnings report and raised guidance."
        elif "downbeat" in evidence or "weaker-than-expected" in evidence:
            attribution = "Benzinga explicitly linked the decline to disappointing quarterly results."
        elif "mixed" in evidence:
            attribution = "Benzinga linked the reaction to a mixed earnings release."
        else:
            attribution = ""
        if attribution:
            explanation = f"{reaction} {attribution}"
            if "stronger than expected" in summary.lower() and direction == "rose":
                explanation += " The reporting presents the beat as the dominant surprise rather than simply recording the individual metrics."
            elif "mixed" in summary.lower():
                explanation += " That attribution indicates investors placed more weight on the cited catalyst than on the offsetting elements of the release."
            return explanation

    lower = summary.lower()
    if direction == "rose":
        if "raised or above-expectation outlook" in lower:
            implication = "The coverage therefore implies that the stronger outlook, reinforced by the reported results, was the first-order positive driver."
        elif "stronger than expected" in lower:
            implication = "The coverage therefore implies that the earnings performance was the first-order positive driver."
        else:
            implication = "The articles do not isolate a first-order catalyst, so the positive reaction cannot be attributed more precisely from this coverage."
    elif direction == "fell":
        if "reduced or below-expectation guidance" in lower:
            implication = "The coverage therefore implies that the weaker outlook outweighed the backward-looking results and was the first-order negative driver."
        elif "weaker than expected" in lower:
            implication = "The coverage therefore implies that the earnings disappointment was the first-order negative driver."
        elif "mixed" in lower:
            implication = "The coverage implies that investors prioritized the negative side of the mixed release, although no article explicitly confirms a single catalyst."
        else:
            implication = "The articles do not explicitly explain why investors sold the stock, so no specific first-order driver can be confirmed."
    else:
        implication = "The limited reaction suggests the positive and negative elements largely offset, but the articles do not explicitly confirm that interpretation."
    if (
        "stronger than expected" in lower
        and direction == "fell"
        and "reduced or below-expectation guidance" not in lower
    ):
        implication += " The negative reaction despite headline beats indicates that investors focused on a forward-looking or operating concern, but the API coverage does not identify it clearly enough to name it as confirmed."
    elif "weaker than expected" in lower and direction == "rose":
        implication += " The positive reaction despite weak headline results indicates that investors found a favorable offset elsewhere, but the retrieved articles do not identify it explicitly."
    return f"{reaction} {implication}"


KIND_PRIORITY = {"results": 0, "mover": 0, "reaction": 1, "preview": 2, "incidental": 3}


def build_entry(ticker, event_date, observed_return, articles):
    window = [
        article for article in articles
        if event_date - timedelta(days=1) <= article_date(article) <= event_date + timedelta(days=3)
    ]
    window.sort(key=lambda article: (relevance(article, ticker), article.get("published", "")), reverse=True)
    selected_pairs = [(article, article_kind(article, ticker)) for article in window]
    direct = [pair for pair in selected_pairs if mentions_company(pair[0], ticker)]
    selected = []
    seen_ids = set()
    for article, kind in direct + selected_pairs:
        identifier = article.get("benzinga_id") or article.get("url") or article.get("title")
        if identifier in seen_ids:
            continue
        selected.append((article, kind))
        seen_ids.add(identifier)
    if not selected:
        return None

    # Keep only the handful of articles that actually explain the results
    # and the stock's reaction -- keeping every deduped article in the
    # fetch window meant some observations linked 20+ sources, most of
    # them wire-service market roundups that only mention the ticker in
    # passing. Rank by how directly each article addresses the earnings
    # report/reaction (results/mover articles first, then analyst reaction
    # pieces, then previews, then incidental mentions), tie-broken by the
    # same relevance score used for windowing, and take at most 3 -- every
    # downstream synthesis step (summary, why_moved, linked sources) then
    # only ever draws on these few, so the links back up the text.
    selected.sort(key=lambda pair: (KIND_PRIORITY.get(pair[1], 4), -relevance(pair[0], ticker)))
    selected = selected[:3]

    primary = [article for article, kind in selected if kind in {"results", "mover"}]
    if not primary:
        primary = [article for article, kind in selected if kind != "incidental"]
    if not primary:
        primary = [article for article, _ in selected]
    summary = coverage_narrative(ticker, selected)

    movement_candidates = [
        sentence
        for article, kind in selected
        if kind == "mover"
        for sentence in explicit_move_sentences(article, ticker)
    ]
    drivers = unique_ranked(movement_candidates, 1, movement=True)
    why_moved = movement_narrative(selected, drivers, observed_return, summary)

    sources = [
        {
            "title": clean_text(article.get("title")),
            "published_date": article_date(article).strftime("%Y-%m-%d"),
            "url": article.get("url"),
            "benzinga_id": article.get("benzinga_id"),
        }
        for article, _ in selected
    ]
    return {
        "summary_analysis": summary,
        "why_moved": why_moved,
        "sources": sources,
    }


def main():
    api_key = load_api_key()
    frame = pd.read_csv(DATA_PATH, parse_dates=["earnings_date"])
    # Resumable: load whatever's already on disk and skip any ticker whose
    # full set of note_keys is already present, so a crash partway through
    # (a real risk with 30 sequential large fetches -- one connection reset
    # already lost an unwritten in-memory run) only costs the one ticker
    # in flight, not everything before it.
    output = json.loads(OUTPUT_PATH.read_text()) if OUTPUT_PATH.exists() else {}
    target_tickers = sorted(frame["ticker"].dropna().unique())
    for ticker in target_tickers:
        observations = frame[frame["ticker"].eq(ticker)].sort_values("earnings_date")
        ticker_keys = {f"{ticker}_{q}" for q in observations["fiscal_yearquarter"]}
        if ticker_keys and ticker_keys.issubset(output):
            print(f"{ticker}: already cached", flush=True)
            continue
        articles = fetch_ticker(
            ticker,
            observations["earnings_date"].min() - timedelta(days=2),
            observations["earnings_date"].max() + timedelta(days=3),
            api_key,
        )
        covered = 0
        for _, row in observations.iterrows():
            key = f"{ticker}_{row['fiscal_yearquarter']}"
            # ret_2day_pct is stored as a percentage point (e.g. 14.52 for
            # +14.52%), but build_entry/movement_narrative expect a fraction
            # (they multiply by 100 themselves) -- divide it back down.
            entry = build_entry(
                ticker,
                row["earnings_date"].normalize(),
                float(row.get("ret_2day_pct", 0.0)) / 100.0,
                articles,
            )
            if entry:
                output[key] = entry
                covered += 1
        with OUTPUT_PATH.open("w") as handle:
            json.dump(output, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print(f"{ticker}: {covered}/{len(observations)} observations covered from {len(articles)} articles", flush=True)
    print(f"Wrote {len(output)} observation records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
