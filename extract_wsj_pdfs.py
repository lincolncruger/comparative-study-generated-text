"""
extract_wsj_pdfs.py
--------------------
Extracts text + metadata from every WSJ article PDF in a
"Context Data Visualization 2/WSJ context - Group N" folder, as a first
mechanical pass before matching each article to a specific ticker/quarter
observation and writing WSJ-grounded analysis for it.

Per PDF: title, byline, the real publication date (parsed from the
"Updated <Month Day, Year> ..." line WSJ prints on every article -- NOT the
PDF's own file-modified date, which is just whenever it was saved/printed),
any GROUP_TICKERS symbol found followed by "%" (WSJ prints stock moves
inline like "AMZN 3.77%", a strong signal of which company the article is
about), and the full extracted text of every page.

Run:
    python3 extract_wsj_pdfs.py "Context Data Visualization 2/WSJ context - Group 1" wsj_group1_extracted.json
"""
import json
import re
import sys
from pathlib import Path

import pdfplumber

_BYLINE_RE = re.compile(r"^By .+$")
_DATE_LINE_RE = re.compile(r"([A-Za-z]+)\.?\s+(\d{1,2}),\s*(\d{4})")
_TICKER_PCT_RE = re.compile(r"\b([A-Z]{1,5})\s+[+-]?\d+\.\d+%")

MONTHS = {
    "January": "01", "Jan": "01", "February": "02", "Feb": "02", "March": "03", "Mar": "03",
    "April": "04", "Apr": "04", "May": "05", "June": "06", "Jun": "06", "July": "07", "Jul": "07",
    "August": "08", "Aug": "08", "September": "09", "Sept": "09", "Sep": "09", "October": "10",
    "Oct": "10", "November": "11", "Nov": "11", "December": "12", "Dec": "12",
}


def parse_wsj_date(line):
    """The date line reliably comes immediately after the "By <author>"
    byline in every WSJ PDF checked -- sometimes prefixed "Updated "/
    "Published ", sometimes not; month sometimes abbreviated with a
    trailing period ("Aug.", "Feb.") and sometimes spelled out, and a
    trailing " at H:MM am/pm ET" is sometimes present, sometimes not. This
    matches all of those, and returns None (not a guess) if the line
    doesn't parse as a date at all."""
    m = _DATE_LINE_RE.search(line.strip())
    if not m:
        return None
    month, day, year = m.groups()
    month = month.rstrip(".")
    if month not in MONTHS:
        return None
    return f"{year}-{MONTHS[month]}-{int(day):02d}"


# WSJ's bold-headline font (DJ5EscrowComp-Bold) renders the "ft" ligature
# as a single glyph mapped to a Private-Use-Area codepoint with no real
# ToUnicode entry, so pdfplumber extracts it as this literal character
# instead of "ft" (e.g. "Microsoft" -> "Microso"). Confirmed to be
# the ONLY PUA codepoint anywhere in the corpus (scanned every page of
# every PDF) before trusting this as a safe global substitution.
_LIGATURE_FIX = {
    "": "ft",
    # "#" -> "ff": a second broken ligature mapping, found in body text
    # ("o#set"->"offset", "e#ort"->"effort", "su#ered"->"suffered", etc).
    # Only 7 occurrences total across the whole corpus, all confirmed by
    # context to be this ligature -- not a real "#" character anywhere.
    "#": "ff",
}


def extract_pdf(path):
    with pdfplumber.open(path) as pdf:
        pages_text = [p.extract_text() or "" for p in pdf.pages]
    full_text = "\n".join(pages_text)
    for bad, good in _LIGATURE_FIX.items():
        full_text = full_text.replace(bad, good)
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    tickers_found = sorted(set(_TICKER_PCT_RE.findall(full_text)))

    # Title: the first non-boilerplate line after the "For non-personal use"
    # copyright block and the article URL -- WSJ PDFs consistently follow
    # [print-header] / [copyright x2] / [url] / [SECTION TAG] / [headline...].
    title_lines = []
    seen_url = False
    byline_idx = None
    for i, line in enumerate(lines):
        if line.startswith("http"):
            seen_url = True
            continue
        if not seen_url:
            continue
        if line.isupper() and len(line) < 20:  # section tag like "TECH", "BUSINESS"
            continue
        if _BYLINE_RE.match(line):
            byline_idx = i
            break
        title_lines.append(line)
    title = " ".join(title_lines).strip()

    # The date line reliably comes right after the byline -- more reliable
    # than searching the whole text, which can false-match a date-shaped
    # string elsewhere in the article body.
    published_date = None
    if byline_idx is not None and byline_idx + 1 < len(lines):
        published_date = parse_wsj_date(lines[byline_idx + 1])

    return {
        "filename": path.name,
        "title": title,
        "published_date": published_date,
        "tickers_mentioned": tickers_found,
        "n_pages": len(pages_text),
        "text": full_text,
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 extract_wsj_pdfs.py <folder> <out.json>")
        sys.exit(1)
    folder = Path(sys.argv[1])
    out_path = sys.argv[2]

    results = []
    pdfs = sorted(folder.glob("*.pdf"))
    for i, path in enumerate(pdfs, 1):
        try:
            res = extract_pdf(path)
        except Exception as e:
            res = {"filename": path.name, "error": str(e)}
        results.append(res)
        status = res.get("published_date", "ERROR")
        print(f"[{i}/{len(pdfs)}] {path.name} -> {status} | tickers: {res.get('tickers_mentioned')}")

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n{len(results)} PDFs extracted -> {out_path}")


if __name__ == "__main__":
    main()
