#!/usr/bin/env python3
"""Build the full PD-category and first-order dataset from prepared source batches."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = ROOT / "wsj_extracted" / "pdcat_batches"
DEST = ROOT / "data" / "group_pd_categories.json"
FIRST_ORDER_DEST = ROOT / "data" / "group_first_order_categories.json"
REVIEW_DIR = ROOT / "wsj_extracted" / "pdcat_reviewed"

# Observation-level contextual selections reviewed against all three inputs:
# Possible Drivers, Current Earnings Release, and the linked reaction article.
# The article's causal framing controls; the release verifies the metric.
CONTEXT_FIRST_ORDER_REVIEW = {
    "AAPL_2016q2": ["Revenue", "Guidance"],
    "AAPL_2016q3": ["Product / Users", "Revenue"],
    "AAPL_2016q4": ["Guidance", "Costs"],
    "AAPL_2017q1": ["Revenue", "Profits and profitability"],
    "AAPL_2017q2": ["Product / Users", "Profits and profitability"],
    "AAPL_2017q3": ["Revenue", "Guidance"],
    "AAPL_2017q4": ["Profits and profitability", "Guidance"],
    "AAPL_2018q1": ["Product / Users", "Guidance"],
    "AAPL_2018q2": ["Profits and profitability", "Product / Users"],
    "AAPL_2018q3": ["Profits and profitability", "Guidance"],
    "ADBE_2016q2": ["Guidance"],
    "ADBE_2016q3": ["Profits and profitability", "Guidance"],
    "ADBE_2016q4": ["Guidance"],
    "ADBE_2017q1": ["Revenue", "Profits and profitability"],
    "ADBE_2017q2": ["Profits and profitability", "Guidance"],
    "ADBE_2017q3": ["Guidance"],
    "ADBE_2017q4": ["Revenue", "Product / Users"],
    "ADBE_2018q1": ["Revenue", "Profits and profitability"],
    "ADBE_2018q2": ["Guidance"],
    "ADBE_2018q3": ["Revenue", "Profits and profitability"],
    "AMZN_2016q2": ["Profits and profitability", "Product / Users"],
    "AMZN_2016q3": ["Profits and profitability", "Product / Users"],
    "AMZN_2016q4": ["Profits and profitability", "Guidance"],
    "AMZN_2017q1": ["Revenue", "Guidance"],
    "AMZN_2017q2": ["Profits and profitability", "Product / Users"],
    "AMZN_2017q3": ["Profits and profitability", "Costs"],
    "AMZN_2017q4": ["Profits and profitability", "Revenue"],
    "AMZN_2018q1": ["Profits and profitability", "Revenue"],
    "AMZN_2018q2": ["Profits and profitability", "Product / Users"],
    "AMZN_2018q3": ["Profits and profitability", "Product / Users"],
    "AVGO_2016q2": ["Profits and profitability", "Guidance"],
    "AVGO_2016q3": ["Product / Users"],
    "AVGO_2016q4": ["Profits and profitability", "Debt, leverage and capital raise"],
    "AVGO_2017q1": ["Guidance", "Product / Users"],
    "AVGO_2017q2": ["Profits and profitability", "Guidance"],
    "AVGO_2017q3": ["Guidance"],
    "AVGO_2017q4": ["Others: eg. Covid, or macro events"],
    "AVGO_2018q1": ["Others: eg. Covid, or macro events", "Product / Users"],
    "AVGO_2018q2": ["Others: eg. Covid, or macro events", "Profits and profitability"],
    "AVGO_2018q3": ["Profits and profitability", "Product / Users"],
    "NVDA_2016q2": ["Profits and profitability", "Guidance"],
    "NVDA_2016q3": ["Guidance", "Product / Users"],
    "NVDA_2016q4": ["Profits and profitability", "Guidance"],
    "NVDA_2017q1": ["Others: eg. Covid, or macro events"],
    "NVDA_2017q2": ["Profits and profitability", "Product / Users"],
    "NVDA_2017q3": ["Others: eg. Covid, or macro events", "Product / Users"],
    "NVDA_2017q4": ["Profits and profitability", "Product / Users"],
    "NVDA_2018q1": ["Profits and profitability", "Product / Users"],
    "NVDA_2018q2": ["Others: eg. Covid, or macro events", "Guidance"],
    "NVDA_2018q3": ["Guidance", "Others: eg. Covid, or macro events"],
}
TICKERS = tuple(
    sorted(
        path.stem
        for path in BATCH_DIR.glob("*.json")
        if not path.stem.endswith("_output")
    )
)

CATEGORIES = {
    "Guidance": ("guidance", "guided", "forecast", "outlook", "forward guide"),
    "Order book / order backlog": ("order book", "backlog", "book-to-bill"),
    "Revenue": ("revenue", "sales", "top line"),
    "Product / Users": (
        "product", "launch", "iphone", "ipad", "creative cloud", "pascal", "gpu", "subscription",
        "subscriber", "monthly active", "daily active", "mau", "dau", "member", "membership",
        "user growth", "user base", "active user", "million users", "billion users", "users reached",
        "users increased", "users grew", "users rose", "users fell", "users declined", "users added",
        "adding users", "customer count", "customer growth", "engagement", "audience",
    ),
    "Profits and profitability": ("profit", "earnings", "eps", "margin", "income"),
    "Costs": ("cost", "expense", "restructur", "layoff"),
    "Debt, leverage and capital raise": ("debt", "capital return", "buyback", "repurchase", "dividend"),
    "Capex": ("capex", "capital expenditure", "capital spending"),
    "Management": ("ceo", "management", "executive", "cook", "huang", "narayen", "hock tan"),
    "Litigation": ("litigation", "lawsuit", "legal", "court", "regulator", "antitrust"),
    "Others: eg. Covid, or macro events": ("macro", "currency", "dollar", "china", "economy", "economic", "competition", "competitive"),
}

FIRST_ORDER_KEYWORDS = {
    "Guidance": ("guidance", "guide", "outlook", "forecast", "forward"),
    "Order book / order backlog": ("order book", "backlog", "book-to-bill"),
    "Revenue": ("revenue", "sales", "top line"),
    "Product / Users": (
        "product", "iphone", "gpu", "cloud", "subscription", "subscriber", "aws", "data center", "gaming",
        "wireless", "monthly active", "daily active", "mau", "dau", "member", "membership", "user growth",
        "user base", "active user", "million users", "billion users", "users reached", "users increased",
        "users grew", "users rose", "users fell", "users declined", "users added", "adding users",
        "engagement", "audience",
    ),
    "Profits and profitability": ("profit", "earnings", "eps", "margin", "income", "bottom line"),
    "Costs": ("cost", "expense", "spending", "investment", "restructuring"),
    "Debt, leverage and capital raise": ("debt", "leverage", "dividend", "buyback", "capital return"),
    "Capex": ("capex", "capital expenditure", "capital spending", "warehouse", "infrastructure"),
    "Management": ("management", "ceo", "cfo", "tone"),
    "Litigation": ("litigation", "lawsuit", "legal", "court", "antitrust"),
    "Others: eg. Covid, or macro events": ("macro", "currency", "china", "valuation", "priced in", "competition", "regulatory", "trade", "m&a", "acquisition", "takeover", "strategic"),
}

NEGATIVE = (
    "below", "miss", "declin", "fell", "fall", "drop", "down", "weak", "soft", "loss", "slump",
    "pressure", "headwind", "challeng", "disappoint", "lower", "cut", "risk", "slow", "short",
    "shy", "reiterat", "uncertain", "slid", "plummet", "tough", "concern",
    "severe", "blow", "softer",
)
POSITIVE = (
    "above", "beat", "grew", "growth", "rose", "rise", "strong", "record", "exceed",
    "higher", "raised", "increase", "upbeat", "confident", "topped", "surged", "improv",
)


def sentences(text):
    text = re.sub(r"\*\*", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    abbreviations = ("Jan.", "Feb.", "Mar.", "Apr.", "Jun.", "Jul.", "Aug.", "Sep.", "Sept.", "Oct.", "Nov.", "Dec.", "U.S.", "Inc.")
    for abbreviation in abbreviations:
        text = text.replace(abbreviation, abbreviation.replace(".", "<DOT>"))
    parts = [s.strip(" -") for s in re.split(r"(?<=[.!?])\s+(?=[A-Za-z0-9\"'])", text) if s.strip()]
    return [part.replace("<DOT>", ".") for part in parts]


def evidence_units(text):
    """Return concise, self-contained evidence units rather than whole summaries."""
    units = []
    for sentence in sentences(text):
        pieces = re.split(
            r";\s+|,\s+(?=(?:while|with|but|though|although|even as|alongside|amid|whereas)\b)",
            sentence,
            flags=re.IGNORECASE,
        )
        for piece in pieces:
            piece = piece.strip(" ,-")
            piece = re.sub(r"^(?:while|with|but|though|although|even as|alongside|amid|whereas)\s+", "", piece, flags=re.I)
            if piece:
                piece = piece[0].upper() + piece[1:]
            # A split inside a quotation can leave an unmatched quote; the
            # evidence remains clearer without a dangling quotation mark.
            if piece.count('"') % 2:
                piece = piece.replace('"', '')
            if len(piece) >= 25:
                units.append(piece)
    return units


def source_text(entry, source):
    data = entry.get(source)
    if not data:
        return None
    if source == "contextual_analysis":
        parts = []
        for section in data.get("sections", []):
            if section.get("heading") in {"Current Earnings Release", "Possible Drivers"}:
                parts.extend(p.get("text", "") for p in section.get("paragraphs", []) if not p.get("sources"))
        return " ".join(parts)
    return " ".join(filter(None, (data.get("summary_analysis"), data.get("why_moved"))))


def score_rating(sentence, category):
    lower = sentence.lower()
    # Match from a word boundary so, for example, "rose" does not match
    # the middle of "gross". Tokens are stems by design (declin/grew/etc.).
    neg = sum(bool(re.search(rf"\b{re.escape(token)}\w*", lower)) for token in NEGATIVE)
    pos = sum(bool(re.search(rf"\b{re.escape(token)}\w*", lower)) for token in POSITIVE)
    # Surprise versus expectations is more informative than a year-over-year
    # comparison for earnings categories, matching the hand-reviewed entries.
    favorable_surprise = bool(re.search(r"\b(beat|beats|beating|above|exceed\w*|topp\w*|ahead of)\b", lower))
    adverse_surprise = bool(re.search(r"\b(miss\w*|below|fell short|disappoint\w*|shy of)\b", lower))
    if category in {"Guidance", "Revenue", "Profits and profitability"}:
        if adverse_surprise and not favorable_surprise:
            return "negative"
        if favorable_surprise and not adverse_surprise:
            return "positive"
    if category == "Debt, leverage and capital raise" and re.search(r"\b(dividend|buyback|repurchas\w*|capital.return)\b", lower):
        return "positive"
    if category == "Costs":
        if re.search(r"\b(higher|rising|rose|increased?)\s+(?:operating\s+)?(?:cost|expense)", lower):
            return "negative"
        if re.search(r"\b(cost|expense)\w*\s+(?:fell|declined|lower|decreased)", lower):
            return "positive"
    if category == "Management":
        if re.search(r"\b(cautio\w*|challeng\w*|concern\w*|uncertain\w*|warn\w*)\b", lower):
            return "negative"
        if re.search(r"\b(confident|bullish|optimistic|bright|encourag\w*)\b", lower):
            return "positive"
    return "negative" if neg and neg >= pos else "positive"


def qualitative_prefix(category, rating):
    labels = {
        "Guidance": ("Guidance was encouraging.", "Guidance was disappointing."),
        "Order book / order backlog": ("Demand visibility was encouraging.", "Demand visibility weakened."),
        "Revenue": ("Revenue performance was strong.", "Revenue performance was weak."),
        "Product / Users": ("Product and user momentum was encouraging.", "Product and user momentum weakened."),
        "Profits and profitability": ("Profitability was strong.", "Profitability was weak."),
        "Costs": ("Cost execution was favorable.", "Costs were a headwind."),
        "Debt, leverage and capital raise": ("Capital management was supportive.", "The capital position was a concern."),
        "Capex": ("Capital investment was constructive.", "Capital spending was a concern."),
        "Management": ("Management struck a confident tone.", "Management struck a cautious tone."),
        "Litigation": ("The legal development was favorable.", "Legal risk was a negative."),
        "Others: eg. Covid, or macro events": ("The broader backdrop was supportive.", "The broader backdrop was challenging."),
    }
    return labels[category][rating == "negative"]


def compact_evidence(chosen, keywords):
    if len(chosen) <= 420:
        return chosen
    lower = chosen.lower()
    positions = [lower.find(keyword) for keyword in keywords if lower.find(keyword) >= 0]
    anchor = min(positions) if positions else 0
    boundaries = [chosen.rfind(mark, 0, anchor) for mark in (". ", " — ", "; ")]
    start = max(boundaries) + (3 if max(boundaries) >= 0 else 0)
    excerpt = chosen[start:]
    if len(excerpt) > 420:
        stops = [excerpt.find(mark, 240) for mark in (". ", " — ", "; ")]
        stops = [stop for stop in stops if 0 < stop <= 520]
        excerpt = excerpt[: min(stops) + 1] if stops else excerpt[:420].rsplit(",", 1)[0]
    return excerpt.strip(" ,-")


def categorize(text):
    pool = evidence_units(text)
    result = {}
    used = set()
    for category, keywords in CATEGORIES.items():
        candidates = []
        for index, sentence in enumerate(pool):
            lower = sentence.lower()
            hits = sum(keyword in lower for keyword in keywords)
            if category == "Guidance" and "guided range" in lower and not re.search(
                r"\b(current|next|full.year|fiscal.year|outlook|forecast|forward)\b", lower
            ):
                hits = 0
            if category == "Management" and not re.search(r"\b(said|called|told|stated|argued|insisted|tone|bullish|confident|optimistic|cautio\w*)\b", lower):
                hits = 0
            if hits:
                candidates.append((hits, index, sentence))
        if not candidates:
            result[category] = {"rating": None, "reason": None}
            continue
        _, index, chosen = candidates[0]
        # Avoid repeating the same generic sentence across loosely related categories.
        if index in used and category in {"Costs", "Management", "Others: eg. Covid, or macro events"}:
            unused = [item for item in candidates if item[1] not in used]
            if unused:
                _, index, chosen = unused[0]
        used.add(index)
        rating = score_rating(chosen, category)
        if chosen and chosen[-1] not in ".!?":
            chosen += "."
        result[category] = {
            "rating": rating,
            "reason": f"{qualitative_prefix(category, rating)} {chosen}",
        }
    return result


def generated_ticker(ticker):
    with (BATCH_DIR / f"{ticker}.json").open() as handle:
        batch = json.load(handle)
    output = {}
    for key, entry in batch.items():
        output[key] = {}
        for source in ("contextual_analysis", "wsj", "djnw"):
            text = source_text(entry, source)
            output[key][source] = categorize(text) if text else None
    return output


def apply_manual_reviews(ticker, output):
    """Small hand-review layer for mixed-source cases requiring interpretation."""
    def set_cell(key, source, category, rating=None, reason=None):
        output[key][source][category] = {"rating": rating, "reason": reason}

    if ticker == "AAPL":
        set_cell("AAPL_2016q2", "wsj", "Others: eg. Covid, or macro events", "negative",
                 "Currency and economic conditions were headwinds. A strong dollar, difficult economic conditions, and tough comparisons contributed to the slowdown.")
        set_cell("AAPL_2016q3", "contextual_analysis", "Product / Users", "positive",
                 "Product performance was encouraging. The lower-priced iPhone SE supported demand, while Services revenue grew 19% year over year.")
        set_cell("AAPL_2016q4", "contextual_analysis", "Costs", "negative",
                 "Margins were a headwind. Apple's holiday-quarter gross-margin outlook of 38%–38.5% was slightly below investor expectations.")
        set_cell("AAPL_2016q3", "wsj", "Management", "positive",
                 "Management sounded encouraged. Tim Cook said customer demand and business performance were stronger than Apple anticipated at the quarter's start.")
        set_cell("AAPL_2016q4", "wsj", "Revenue", "negative",
                 "Revenue remained under pressure. Quarterly revenue fell 9% to $46.9 billion, contributing to Apple's first annual revenue decline in 15 years.")
        set_cell("AAPL_2016q4", "wsj", "Profits and profitability", "positive",
                 "EPS narrowly beat expectations despite a year-over-year decline. Apple earned $1.67 a share versus the $1.65 analysts expected, while net income fell 19%.")
        set_cell("AAPL_2016q4", "djnw", "Management", "positive",
                 "Management was optimistic about the next product cycle. Tim Cook described iPhone 7 customer response as off the charts and guided revenue above consensus.")
        set_cell("AAPL_2016q4", "wsj", "Management", "positive",
                 "Management expected a return to growth. Tim Cook forecast holiday-quarter growth despite supply shortages and highlighted 24% Services growth.")
        set_cell("AAPL_2016q4", "wsj", "Others: eg. Covid, or macro events", "negative",
                 "China remained a major headwind. Greater China sales fell 30% to $8.8 billion after growing 99% in the prior-year quarter.")
        set_cell("AAPL_2016q4", "djnw", "Others: eg. Covid, or macro events", "negative",
                 "China remained a major headwind. Greater China sales fell 30% to $8.8 billion after growing 99% one year earlier.")
        set_cell("AAPL_2017q1", "djnw", "Revenue", "positive",
                 "Revenue returned to growth and set a record. Fiscal first-quarter revenue reached $78.4 billion after three consecutive quarters of year-over-year declines.")
        set_cell("AAPL_2017q1", "djnw", "Profits and profitability", "positive",
                 "Profitability beat expectations. EPS of $3.38 exceeded the $3.22 analyst consensus even though total profit declined slightly year over year.")
        set_cell("AAPL_2017q1", "wsj", "Management", "negative",
                 "Management acknowledged execution constraints. Tim Cook said Apple underestimated iPhone 7 Plus demand and missed sales because of product shortages.")
        set_cell("AAPL_2017q1", "wsj", "Litigation", "negative",
                 "Legal risk increased. The article reported new Apple lawsuits against Qualcomm concerning patent-licensing fees.")
        set_cell("AAPL_2017q3", "wsj", "Revenue", "positive",
                 "Revenue was stronger than expected in a seasonally weak quarter, supporting confidence ahead of the next iPhone launch.")
        set_cell("AAPL_2017q2", "contextual_analysis", "Debt, leverage and capital raise", "positive",
                 "Capital returns increased. Apple raised its dividend 10.5% and expanded its buyback authorization by $35 billion to $210 billion.")
        set_cell("AAPL_2017q2", "contextual_analysis", "Revenue", "negative",
                 "Revenue came in slightly below expectations. Fiscal Q2 revenue was $52.9 billion versus consensus just under $53.0 billion.")
        set_cell("AAPL_2017q2", "wsj", "Revenue", "positive",
                 "Revenue beat expectations. It rose 4.6% to $52.90 billion, slightly ahead of consensus, despite softer iPhone shipments.")
        set_cell("AAPL_2017q2", "wsj", "Profits and profitability", "positive",
                 "Profitability beat expectations. EPS of $2.10 topped the $2.02 consensus, and profit rose 4.9% to $11.03 billion.")
        set_cell("AAPL_2017q2", "wsj", "Debt, leverage and capital raise", "positive",
                 "Capital returns expanded. Apple increased its dividend 10.5% and lifted the buyback authorization by $35 billion to $210 billion.")
        set_cell("AAPL_2017q3", "contextual_analysis", "Guidance", "positive",
                 "Guidance came in above expectations. Apple projected $49–$52 billion of fiscal Q4 revenue, with the midpoint above consensus.")
        set_cell("AAPL_2017q3", "wsj", "Management", "positive",
                 "Management reduced launch concerns. Tim Cook's inventory comments suggested Apple was not encountering major production problems with upcoming iPhones.")
        set_cell("AAPL_2018q1", "contextual_analysis", "Revenue", "positive",
                 "Revenue reached a record. Fiscal Q1 revenue was $88.3 billion even though iPhone unit shipments fell short of investor expectations.")
        set_cell("AAPL_2018q1", "contextual_analysis", "Guidance", "negative",
                 "Guidance came in below expectations. Apple projected $60–$62 billion of fiscal Q2 revenue versus consensus near $66.5 billion.")
        set_cell("AAPL_2018q1", "contextual_analysis", "Profits and profitability", "positive",
                 "Profitability was strong. Apple reported record fiscal Q1 revenue and EPS of $3.89, supported by a richer iPhone mix.")
        set_cell("AAPL_2018q1", "wsj", "Revenue", "positive",
                 "Revenue set a quarterly record. The $1,000 iPhone X lifted average selling prices enough to offset lower unit sales.")
        set_cell("AAPL_2018q1", "wsj", "Profits and profitability", "positive",
                 "Profit reached a quarterly record. Higher iPhone average selling prices supported earnings despite lower handset volumes.")
        set_cell("AAPL_2018q1", "wsj", "Product / Users", "positive",
                 "The premium iPhone X improved product mix. Its $1,000 price helped lift the average iPhone selling price by nearly 15%.")
        set_cell("AAPL_2018q2", "wsj", "Guidance", "positive",
                 "Guidance was reassuring rather than exceptional. The $51.5–$53.5 billion revenue range bracketed the $51.9 billion analyst consensus.")
        set_cell("AAPL_2018q2", "wsj", "Others: eg. Covid, or macro events")
        set_cell("AAPL_2017q2", "djnw", "Profits and profitability", "positive",
                 "Profit increased, but the positive earnings result was overshadowed by tepid iPhone demand and weakness across Apple suppliers.")
        set_cell("AAPL_2017q4", "djnw", "Profits and profitability")
        set_cell("AAPL_2017q4", "wsj", "Costs")
        set_cell("AAPL_2017q4", "djnw", "Revenue", "positive",
                 "Revenue growth accelerated. The roundup described Apple's results as its best quarterly growth in two years, and shares rose 2.6%.")
        set_cell("AAPL_2017q4", "wsj", "Others: eg. Covid, or macro events", "negative",
                 "The launch schedule complicated forecasting. Management said launching three iPhone models on staggered dates made demand unusually difficult to predict.")
        set_cell("AAPL_2018q3", "wsj", "Litigation", "negative",
                 "Regulatory risk was an overhang. The article flagged trade-war and Chinese regulatory risks, though it did not tie them directly to the immediate stock reaction.")
        set_cell("AAPL_2018q3", "contextual_analysis", "Product / Users", "positive",
                 "Product mix was favorable. Services set a record and higher iPhone pricing supported growth despite limited unit gains.")
        set_cell("AAPL_2018q3", "wsj", "Revenue", "positive",
                 "Revenue beat expectations. Apple delivered record fiscal Q3 revenue of $53.3 billion, near the high end of its guidance.")
        set_cell("AAPL_2018q3", "wsj", "Litigation")
        set_cell("AAPL_2018q3", "wsj", "Others: eg. Covid, or macro events", "negative",
                 "Trade tensions created risk. The article flagged possible tariffs on Apple's China exposure and criticism from Chinese state media.")

    if ticker == "ADBE":
        set_cell("ADBE_2016q2", "contextual_analysis", "Guidance", "negative",
                 "Guidance lacked upside. Adobe projected $1.42–$1.47 billion of fiscal Q3 revenue, with the high end only matching Wall Street's expectation.")
        set_cell("ADBE_2016q2", "contextual_analysis", "Product / Users", "positive",
                 "Subscription momentum remained strong. Creative Cloud ARR and adoption continued to grow; the weakness centered on forward expectations, not operations.")
        set_cell("ADBE_2016q2", "wsj", "Management", "positive",
                 "Management retained an optimistic bias. Adobe reiterated its full-year targets and indicated results could ultimately exceed that forecast.")
        set_cell("ADBE_2016q3", "contextual_analysis", "Product / Users", "positive",
                 "Subscription momentum remained strong. Creative revenue grew 39%, while Digital Media ARR increased $285 million to $3.70 billion.")
        set_cell("ADBE_2016q3", "contextual_analysis", "Profits and profitability", "positive",
                 "Profitability beat expectations. Non-GAAP EPS reached $0.75, above consensus, and Adobe raised its Q4 EPS outlook.")
        set_cell("ADBE_2016q3", "wsj", "Guidance", "positive",
                 "Guidance came in above expectations. Adobe projected $1.55–$1.60 billion of revenue and $0.83–$0.89 of adjusted EPS for the current quarter.")
        set_cell("ADBE_2016q4", "contextual_analysis", "Product / Users", "positive",
                 "Subscription and cloud fundamentals remained strong despite the softer fiscal-2017 outlook.")
        set_cell("ADBE_2016q4", "wsj", "Guidance")
        set_cell("ADBE_2017q2", "wsj", "Guidance")
        set_cell("ADBE_2017q2", "wsj", "Profits and profitability", "positive",
                 "Profitability improved strongly. Diluted EPS rose 56% year over year to $0.75, extending Adobe's multiyear earnings-growth streak.")
        set_cell("ADBE_2017q2", "djnw", "Guidance")
        set_cell("ADBE_2017q2", "djnw", "Profits and profitability")
        set_cell("ADBE_2018q2", "contextual_analysis", "Guidance", "negative",
                 "Guidance offered little upside. Adobe projected about $2.24 billion of fiscal Q3 revenue and $1.68 of adjusted EPS after a large stock run-up.")
        set_cell("ADBE_2018q1", "djnw", "Guidance")

    if ticker == "AMZN":
        set_cell("AMZN_2017q3", "contextual_analysis", "Costs", "negative",
                 "Heavy investment was a headwind. Spending on fulfillment, video, Alexa, India and AWS infrastructure drove the sharp profit shortfall.")
        set_cell("AMZN_2016q4", "contextual_analysis", "Revenue", "positive",
                 "Revenue growth remained strong. Third-quarter sales rose 29% to $32.7 billion, broadly matching expectations, while AWS revenue grew 55%.")
        set_cell("AMZN_2016q4", "wsj", "Revenue", "positive",
                 "Revenue continued growing. Sales rose to $32.7 billion even though heavy investment caused earnings to miss expectations.")
        set_cell("AMZN_2017q2", "wsj", "Guidance", "negative",
                 "Guidance was slightly below expectations. Amazon's $35.25–$37.75 billion revenue range had a $36.5 billion midpoint versus $36.87 billion consensus.")
        set_cell("AMZN_2017q3", "wsj", "Litigation")
        set_cell("AMZN_2018q1", "wsj", "Costs", "positive",
                 "Cost efficiency improved. Shipping costs rose 31%, slower than 38% revenue growth, while warehouse productivity helped profit exceed $1 billion.")
        set_cell("AMZN_2018q2", "wsj", "Litigation")
        set_cell("AMZN_2018q3", "wsj", "Litigation")

    if ticker == "AVGO":
        set_cell("AVGO_2017q1", "contextual_analysis", "Product / Users", "positive",
                 "End-market demand was supportive. Strength in data-center networking and enterprise storage offset normal wireless seasonality.")
        set_cell("AVGO_2018q1", "contextual_analysis", "Product / Users", "negative",
                 "Wireless demand was expected to weaken. Management forecast a sharp seasonal reversal after iPhone-driven strength in the reported quarter.")
        set_cell("AVGO_2018q3", "contextual_analysis", "Product / Users", "positive",
                 "Product demand was encouraging. Data-center networking and enterprise storage strength reduced Broadcom's reliance on smartphones.")
        set_cell("AVGO_2016q2", "contextual_analysis", "Management", "positive",
                 "Management emphasized diversification. Hock Tan said stronger wired demand and Asian handset shipments offset softer demand from Broadcom's largest North American customer.")
        set_cell("AVGO_2016q2", "contextual_analysis", "Others: eg. Covid, or macro events", "negative",
                 "Smartphone demand was a headwind. Apple's first iPhone sales decline and slower China demand pressured Broadcom's wireless-chip outlook.")
        set_cell("AVGO_2017q1", "contextual_analysis", "Costs", "negative",
                 "Acquisition costs remained a headwind. Merger-related accounting and integration charges continued weighing on GAAP profitability.")

    if ticker == "FB":
        set_cell("FB_2016q3", "djnw", "Product / Users", "positive",
                 "User reach remained strong. Nearly two-thirds of internet-using adults outside China accessed Facebook monthly.")
        set_cell("FB_2016q4", "wsj", "Product / Users", "positive",
                 "User growth remained strong. Monthly active users reached 1.79 billion, with 93% accessing Facebook on mobile.")
        set_cell("FB_2017q3", "wsj", "Product / Users", "negative",
                 "Product monetization faced limits. News Feed ad load was nearing a ceiling because adding more ads risked alienating users.")
        set_cell("FB_2017q3", "djnw", "Product / Users", "negative",
                 "Product monetization faced limits. Core News Feed ad growth was approaching saturation, forcing expansion into newer formats.")
        set_cell("FB_2018q1", "contextual_analysis", "Product / Users", "negative",
                 "User engagement weakened. Time spent fell by about 50 million hours daily, while U.S. and Canadian daily users declined for the first time.")
        set_cell("FB_2018q1", "wsj", "Product / Users", "negative",
                 "User growth disappointed. Facebook added 33 million daily users versus the 46 million analysts expected, its slowest sequential DAU growth on record.")
        set_cell("FB_2018q2", "wsj", "Product / Users", "positive",
                 "User growth remained resilient. Monthly active users increased by about 70 million to 2.2 billion despite the privacy backlash.")
        set_cell("FB_2018q3", "contextual_analysis", "Product / Users", "negative",
                 "User growth slowed. Daily and monthly users grew 11% year over year, while European daily users declined after GDPR took effect.")
        set_cell("FB_2018q3", "wsj", "Product / Users", "negative",
                 "User momentum weakened. U.S. and Canadian daily users were flat, while European daily users fell to 279 million from 282 million.")

    if ticker == "NFLX":
        set_cell("NFLX_2016q2", "wsj", "Product / Users", "negative",
                 "Subscriber growth was slowing. Netflix expected 1.75 million U.S. additions, down from 2.28 million a year earlier, as higher prices threatened churn.")
        set_cell("NFLX_2016q3", "contextual_analysis", "Product / Users", "negative",
                 "Subscriber growth disappointed. Netflix added 1.7 million members versus its 2.5 million forecast as price increases drove higher churn.")
        set_cell("NFLX_2016q4", "wsj", "Product / Users", "positive",
                 "Subscriber growth beat guidance. Netflix added 3.2 million international members versus 2 million expected and 370,000 U.S. members versus 300,000.")
        set_cell("NFLX_2017q2", "contextual_analysis", "Product / Users", "negative",
                 "Subscriber growth missed expectations. Netflix added about 4.95 million members versus its 5.2 million forecast and roughly 5.3 million expected.")
        set_cell("NFLX_2017q3", "djnw", "Product / Users", "positive",
                 "Subscriber growth beat expectations. Netflix added more users than projected, sending the stock up more than 10% after hours.")
        set_cell("NFLX_2018q3", "contextual_analysis", "Product / Users", "negative",
                 "Subscriber growth disappointed. Netflix added about 5.15 million members versus its 6.2 million forecast, with both U.S. and international additions short.")

    if ticker == "NVDA":
        set_cell("NVDA_2016q3", "contextual_analysis", "Debt, leverage and capital raise")
        set_cell("NVDA_2016q3", "contextual_analysis", "Management", "positive",
                 "Management emphasized accelerating demand. Jensen Huang highlighted Pascal adoption and surging interest in deep learning.")
        set_cell("NVDA_2016q3", "contextual_analysis", "Litigation")
        set_cell("NVDA_2017q3", "contextual_analysis", "Costs", "positive",
                 "Costs grew more slowly than revenue. Non-GAAP operating expenses rose 19% while revenue increased 56% year over year.")
        set_cell("NVDA_2017q3", "wsj", "Product / Users", "positive",
                 "Data-center momentum remained strong. Revenue nearly tripled year over year to $416 million as the new Volta platform began ramping.")
        set_cell("NVDA_2018q1", "contextual_analysis", "Others: eg. Covid, or macro events", "positive",
                 "Cryptocurrency demand provided upside. Management said mining-related GPU demand exceeded expectations, although it remained secondary to core markets.")

    if ticker == "NVDA":
        output["NVDA_2018q2"]["wsj"] = {
            category: {"rating": None, "reason": None} for category in CATEGORIES
        }
        wsj = output["NVDA_2018q2"]["wsj"]
        wsj["Guidance"] = {
            "rating": "negative",
            "reason": "The forward signal was negative. NVIDIA said cryptocurrency-mining demand was expected to decline in the current quarter.",
        }
        wsj["Revenue"] = {
            "rating": "positive",
            "reason": "Data-center revenue substantially beat expectations. Sales rose 71% year over year to $701 million, ahead of the 60% growth analysts projected.",
        }
        wsj["Product / Users"] = {
            "rating": "negative",
            "reason": "Cryptocurrency-related GPU demand looked less durable. The coverage flagged purpose-built mining hardware as a competitive risk and expected mining demand to decline.",
        }
        wsj["Others: eg. Covid, or macro events"] = {
            "rating": "negative",
            "reason": "Valuation and positioning created a difficult backdrop. About 15% of the stock's recent gains came in the week before earnings, leaving strong results largely priced in.",
        }
    return output


def concise_reason(reason, category, rating):
    """Reduce a reason to one verdict sentence plus one evidence sentence."""
    if not reason:
        return None
    parts = sentences(reason)
    verdict = qualitative_prefix(category, rating)
    # Generated/manual entries already lead with a verdict; discard it and
    # retain the evidence. Older hand-written entries may be a single factual
    # sentence, in which case that full sentence is the evidence.
    evidence_sentences = parts[1:] if len(parts) >= 2 else parts
    keywords = CATEGORIES[category]

    def evidence_score(value):
        lower = value.lower()
        score = 4 * sum(keyword in lower for keyword in keywords)
        score += 3 * bool(re.search(r"[$€£]?\d", value))
        score += 3 * bool(re.search(r"\b(vs\.?|versus|consensus|expected|expectations|forecast|year.over.year)\b", lower))
        score += 1 if len(value) <= 175 else 0
        return score

    evidence = max(evidence_sentences, key=evidence_score).strip()
    budget = max(100, 198 - len(verdict))
    if len(evidence) > budget:
        broad_clauses = re.split(
            r";\s+|\s+—\s+|,\s+(?=(?:while|with|but|though|although|even as|alongside|amid|and)\b)",
            evidence,
            flags=re.IGNORECASE,
        )
        atomic_clauses = re.split(r"(?<=[.!?])\s+|;\s+|,\s+", evidence)
        clauses = broad_clauses + atomic_clauses
        clauses = [clause.strip(" ,-") for clause in clauses if len(clause.strip()) >= 25]
        fitting = [clause for clause in clauses if len(clause) <= budget]
        if fitting:
            evidence = max(fitting, key=evidence_score)
        else:
            # Keep the comparison intact where possible; otherwise stop at
            # the final complete comma-delimited fact inside the budget.
            excerpt = evidence[:budget]
            cut = max(excerpt.rfind(","), excerpt.rfind(";"))
            evidence = excerpt[:cut] if cut >= 65 else excerpt.rsplit(" ", 1)[0]
    evidence = re.sub(r"^(?:while|with|but|though|although|even as|alongside|amid|and)\s+", "", evidence, flags=re.I)
    evidence = evidence.strip(" ,-")
    if evidence.count("(") > evidence.count(")"):
        evidence = evidence[: evidence.rfind("(")].rstrip(" ,-")
    # Remove an opening quotation mark whose closing mark was outside a
    # discarded clause, while leaving ordinary apostrophes untouched.
    evidence = re.sub(r"(?<!\w)'(?=[A-Za-z])", "", evidence)
    evidence = re.sub(r"(?<=\w)'(?=[,.;])", "", evidence)
    if ". " in evidence and len(evidence.rsplit(". ", 1)[1]) < 45:
        evidence = evidence.rsplit(". ", 1)[0] + "."
    evidence_parts = sentences(evidence)
    if len(evidence_parts) > 1:
        evidence = max(evidence_parts, key=evidence_score)
    evidence = re.sub(r"^Which\s+", "", evidence)
    evidence = re.sub(r"\.{2,}$", ".", evidence)
    evidence = re.sub(r"([.!?])([\"'])\.$", r"\1\2", evidence)
    if evidence:
        evidence = evidence[0].upper() + evidence[1:]
        if evidence[-1] not in ".!?":
            evidence += "."
    return f"{verdict} {evidence}".strip()


def make_output_concise(output):
    for entry in output.values():
        for source in ("contextual_analysis", "wsj", "djnw"):
            source_data = entry.get(source)
            if source_data is None:
                continue
            for category, cell in source_data.items():
                cell["reason"] = concise_reason(cell.get("reason"), category, cell.get("rating"))
    return output


def migrate_product_users_key(output):
    """Preserve reviewed legacy output while applying the renamed schema key."""
    for entry in output.values():
        for source in ("contextual_analysis", "wsj", "djnw"):
            source_data = entry.get(source)
            if source_data is None or "Product" not in source_data:
                continue
            entry[source] = {
                ("Product / Users" if category == "Product" else category): cell
                for category, cell in source_data.items()
            }
    return output


def move_explanation(entry, source):
    data = entry.get(source)
    if not data:
        return ""
    if source == "contextual_analysis":
        sections = data.get("sections", [])
        drivers = []
        earnings = []
        for section in sections:
            texts = [
                paragraph.get("text", "")
                for paragraph in section.get("paragraphs", [])
                if not paragraph.get("sources")
            ]
            if section.get("heading") == "Possible Drivers":
                drivers.extend(texts)
            elif section.get("heading") == "Current Earnings Release":
                earnings.extend(texts)
        if not drivers:
            return ""
        # The reaction coverage supplies the causal claim, while the current
        # earnings release supplies the underlying metric evidence. Weight the
        # explicitly labelled first-order driver most heavily, but rank against
        # both source-grounded sections rather than the Possible Drivers prose
        # alone. Prior-quarter context is intentionally excluded because it
        # cannot itself explain the current reaction.
        return " ".join([drivers[0]] * 6 + drivers[1:2] * 2 + earnings)
    return data.get("why_moved", "")


def first_order_for_source(pd_source, explanation, move_positive):
    if pd_source is None or not explanation:
        return None
    lower = explanation.lower()
    explanation_tokens = set(re.findall(r"[a-z]{4,}", lower))
    scored = []
    for position, (category, cell) in enumerate(pd_source.items()):
        rating = cell.get("rating")
        reason = cell.get("reason")
        if not rating or not reason:
            continue
        keyword_hits = sum(lower.count(keyword) for keyword in FIRST_ORDER_KEYWORDS[category])
        reason_tokens = set(re.findall(r"[a-z]{4,}", reason.lower()))
        overlap = len(explanation_tokens & reason_tokens)
        direction_match = (rating == "positive") == move_positive
        score = keyword_hits * 8 + min(overlap, 8) + (4 if direction_match else 0)
        scored.append((score, keyword_hits, overlap, -position, category, cell))
    if not scored:
        return None
    negative_move = len(re.findall(r"\b(?:fell|fall|dropped|declined|slid|plunged|sold off|lower)\b", lower))
    positive_move = len(re.findall(r"\b(?:rose|rise|jumped|gained|surged|rallied|higher)\b", lower))
    flat_move = bool(re.search(r"\b(?:flat|muted|little changed|barely moved|mixed)\b", lower))
    implied_positive = move_positive
    if not flat_move and negative_move != positive_move:
        implied_positive = positive_move > negative_move
    directional = [item for item in scored if (item[5]["rating"] == "positive") == implied_positive]
    if directional and not flat_move:
        scored = directional
    scored.sort(reverse=True)
    chosen = [scored[0]]
    if len(scored) > 1:
        second = scored[1]
        # A second category must have direct causal wording or substantial
        # evidence overlap; otherwise one category is the more honest result.
        if second[1] > 0 or second[2] >= 4:
            chosen.append(second)
    return [
        {"category": item[4], "rating": item[5]["rating"], "reason": item[5]["reason"]}
        for item in chosen
    ]


def build_first_order(selected, source_records):
    abnormal = json.load((ROOT / "data" / "group_abnormal_returns.json").open())
    result = {}
    for key, pd_entry in selected.items():
        source_entry = source_records[key]
        z_score = ((abnormal.get(key) or {}).get("market_adjusted") or {}).get("z_score", 0)
        move_positive = z_score >= 0
        result[key] = {
            source: first_order_for_source(
                pd_entry.get(source), move_explanation(source_entry, source), move_positive
            )
            for source in ("contextual_analysis", "wsj", "djnw")
        }
        reviewed_categories = CONTEXT_FIRST_ORDER_REVIEW.get(key)
        if reviewed_categories is not None:
            contextual_pd = pd_entry.get("contextual_analysis") or {}
            result[key]["contextual_analysis"] = [
                {
                    "category": category,
                    "rating": contextual_pd[category]["rating"],
                    "reason": contextual_pd[category]["reason"],
                }
                for category in reviewed_categories
                if contextual_pd.get(category, {}).get("reason")
            ] or None
        ticker_review_path = REVIEW_DIR / f"{key.split('_', 1)[0]}.json"
        if ticker_review_path.exists():
            ticker_review = json.load(ticker_review_path.open())
            reviewed_sources = ticker_review.get("first_order", {}).get(key)
            if reviewed_sources is not None:
                for source in ("contextual_analysis", "wsj", "djnw"):
                    categories = reviewed_sources.get(source)
                    source_pd = pd_entry.get(source) or {}
                    result[key][source] = [
                        {
                            "category": category,
                            "rating": source_pd[category]["rating"],
                            "reason": source_pd[category]["reason"],
                        }
                        for category in (categories or [])
                    ] or None
    return result


def load_reviewed_ticker(ticker, generated):
    """Expand a source-audited sparse ticker file into the fixed 11-category schema."""
    review_path = REVIEW_DIR / f"{ticker}.json"
    if not review_path.exists():
        return None
    review_document = json.load(review_path.open())
    reviewed = review_document.get("pd")
    if reviewed is None:
        # Once every existing cell has been checked, a compact review file can
        # retain the checked output and record only the cells that needed a
        # correction. This avoids duplicating tens of thousands of null cells.
        expanded = generated
        for key, source_overrides in review_document.get("pd_overrides", {}).items():
            for source, category_overrides in source_overrides.items():
                if category_overrides is None:
                    expanded[key][source] = None
                    continue
                for category, cell in category_overrides.items():
                    expanded[key][source][category] = cell
        return expanded
    expanded = {}
    for key, observation in reviewed.items():
        expanded[key] = {}
        for source in ("contextual_analysis", "wsj", "djnw"):
            source_review = observation.get(source)
            if source_review is None:
                expanded[key][source] = None
                continue
            expanded[key][source] = {
                category: source_review.get(category, {"rating": None, "reason": None})
                for category in CATEGORIES
            }
    return expanded


def main():
    with DEST.open() as handle:
        merged = migrate_product_users_key(json.load(handle))

    for ticker in TICKERS:
        output_path = BATCH_DIR / f"{ticker}_output.json"
        existing = {}
        if output_path.exists():
            with output_path.open() as handle:
                existing = migrate_product_users_key(json.load(handle))
        generated = generated_ticker(ticker)
        # Human/Claude-produced entries win; generation only fills gaps.
        if ticker in {"AMZN", "AVGO"}:
            generated.update(existing)
        elif ticker == "NVDA":
            # Preserve Claude's eight finished observations; fill its one gap.
            existing.pop("NVDA_2018q2", None)
            generated.update(existing)
        # Some legacy batch inputs omit an observation that is already present
        # in the consolidated dashboard data (notably NVDA_2016q2). Preserve
        # that base record so a compact audited review can override its cells.
        for key, observation in merged.items():
            if key.split("_", 1)[0] == ticker:
                generated.setdefault(key, observation)
        generated = apply_manual_reviews(ticker, generated)
        generated = make_output_concise(generated)
        reviewed_ticker = load_reviewed_ticker(ticker, generated)
        if reviewed_ticker is not None:
            # A completed source audit replaces every generated cell for this
            # ticker; no keyword-derived classification may leak back in.
            generated = reviewed_ticker
        if ticker == "AVGO":
            generated["AVGO_2018q3"]["wsj"]["Others: eg. Covid, or macro events"] = {
                "rating": "negative",
                "reason": "The broader backdrop was challenging. The proposed $19 billion CA Technologies acquisition had already pressured Broadcom's stock.",
            }
        with output_path.open("w") as handle:
            json.dump(generated, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        merged.update(generated)

    selected = {key: value for key, value in merged.items() if key.split("_", 1)[0] in TICKERS}
    selected = make_output_concise(selected)
    with DEST.open("w") as handle:
        json.dump(selected, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    with (ROOT / "wsj_extracted" / "pd_categories_consolidated.json").open() as handle:
        source_records = json.load(handle)
    first_order = build_first_order(selected, source_records)
    with FIRST_ORDER_DEST.open("w") as handle:
        json.dump(first_order, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
