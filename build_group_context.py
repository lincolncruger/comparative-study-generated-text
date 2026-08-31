"""
build_group_context.py
-----------------------
Converts a "Context Data Visualization 2/*.xlsx" workbook (one sheet per
ticker, plus meta sheets like Methodology / Source Dossier / Groups Index /
Source Date Audit that this script skips) into the same JSON shape app.py's
format_websearch_context() already renders for the original 241-observation
dataset (data/websearch_long_241.json):

    {"<ticker>_<fiscal_yearquarter>": [
        {"heading": "...", "paragraphs": [{"text": "...", "sources": [{"label", "url"}]}]},
        ...
    ]}

The markdown column name and the exact citation mechanism have both changed
across every workbook revision so far (four different citation syntaxes:
"[🔎 VERIFY — Label](url)" links, "- Publisher — Title — URL" bullets,
"- DATE | Publisher — Title — URL", "- ROLE | DATE | Δ +N days | Publisher
— Title — URL", and now bare "DATE | Publisher | Title | URL" lines with no
leading "-" and no em-dashes at all), so this parser doesn't hardcode any of
that -- it's content-based, not syntax-based:

  - Section headings are any "## Heading" line -- not assumed to be a fixed
    set.
  - A citation is any line that ends in a URL, with or without a leading
    "- ", using either "|" or " — " (or a mix) between whatever metadata
    fields precede the URL (date, role, day-delta, publisher, title -- the
    field count and order both vary by revision). A block of consecutive
    such lines, optionally preceded by a non-URL label/sub-heading line, is
    parsed as one grouped citation. A line with no trailing URL (e.g. "-
    PRIOR CONTEXT: NO DATE-MATCHED SOURCE FOUND", one revision's explicit
    way of saying no eligible source exists for that slot) correctly isn't
    treated as a citation, so that case falls through to plain text instead
    of being force-fit into a fake source.

Only sheets that actually have the required columns are treated as
per-ticker data -- meta sheets have a different shape and are skipped
automatically rather than by name, so a future meta-sheet with an
unanticipated name doesn't need a code change.

Run:
    python3 build_group_context.py "Context Data Visualization 2/Groups_1_2_3_contextual_analysis_DATE_AUDITED_REBUILT.xlsx"
"""
import json
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "data", "group_context.json")

_VERIFY_RE = re.compile(r"^\[🔎 VERIFY — (.+?)\]\((.+?)\)$")
_HEADING_RE = re.compile(r"^## (.+)$")
_TRAILING_URL_RE = re.compile(r"(https?://\S+)\s*$")
_DATE_FIELD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Metadata fields to drop from a citation's field list before building its
# label -- an all-caps role tag ("PRIOR CONTEXT", "EARNINGS/REACTION") or a
# day-delta ("Δ +0 days", "Δ -91 days"). Whatever's left (publisher, title)
# becomes the label; a bare date field is dropped by _DATE_FIELD_RE instead.
_METADATA_FIELD_RE = re.compile(r"^[A-Z][A-Z /]*$|^Δ\s*[+-]?\d+\s*days?$")


def parse_source_line(line):
    """A citation is any line ending in a URL, however its fields before
    that URL are delimited or however many of them there are -- optionally
    a leading "- ", then some mix of date/role/delta/publisher/title
    fields separated by "|" and/or " — " (both appear, sometimes in the
    same line). Returns a {label, url} dict, or None if the line has no
    trailing URL at all (not a citation -- e.g. a "no source found" note)."""
    line = line.strip()
    if line.startswith("- "):
        line = line[2:]
    url_match = _TRAILING_URL_RE.search(line)
    if not url_match:
        return None
    url = url_match.group(1)
    prefix = line[:url_match.start()]
    prefix = re.sub(r"[|—\-\s]+$", "", prefix)  # trailing separator before the URL

    fields = [f.strip() for f in re.split(r"\s*\|\s*|\s+—\s+", prefix) if f.strip()]
    content_fields = [f for f in fields if not _DATE_FIELD_RE.match(f) and not _METADATA_FIELD_RE.match(f)]
    if not content_fields:
        content_fields = fields  # everything looked like metadata -- keep it rather than lose the label

    label = ": ".join(content_fields[:2]) if len(content_fields) >= 2 else (content_fields[0] if content_fields else url)
    return {"label": label, "url": url}


def parse_source_block(block):
    """If `block` is a (possibly labeled) list of citation lines, return
    (lead_text, [sources]); otherwise return None so the caller falls back
    to treating the whole block as a plain paragraph."""
    lines = block.split("\n")
    parsed_lines = [parse_source_line(l) for l in lines]
    if not any(parsed_lines):
        return None

    # Non-citation lines (e.g. a "### some label" line, or the block's own
    # intro sentence) are only allowed before the first citation -- once
    # citations start, every remaining line must be one, or this isn't a
    # clean citation block.
    first_source_idx = next(i for i, p in enumerate(parsed_lines) if p)
    lead_lines = lines[:first_source_idx]
    sources = parsed_lines[first_source_idx:]
    if not all(sources):
        return None  # a non-citation line interleaved among the citations

    lead_text = " ".join(l.strip() for l in lead_lines).lstrip("#").strip() or "Sources:"
    return lead_text, sources


def parse_markdown(text):
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    sections = []
    current = None
    pending_paragraph = None

    def flush_paragraph():
        nonlocal pending_paragraph
        if pending_paragraph is not None:
            current["paragraphs"].append(pending_paragraph)
            pending_paragraph = None

    for block in blocks:
        heading_match = _HEADING_RE.match(block)
        verify_match = _VERIFY_RE.match(block)
        source_block = None if (heading_match or verify_match) else parse_source_block(block)

        if heading_match:
            flush_paragraph()
            current = {"heading": heading_match.group(1), "paragraphs": []}
            sections.append(current)
        elif verify_match:
            label, url = verify_match.groups()
            pending_paragraph["sources"].append({"label": label, "url": url})
        elif source_block is not None:
            flush_paragraph()
            lead_text, sources = source_block
            current["paragraphs"].append({"text": lead_text, "sources": sources})
        else:
            flush_paragraph()
            # Strip a leading "### sub-heading" line's hashes, and turn any
            # remaining "\n- " bullet markers into ": " -- an unparsed block
            # (e.g. one mixing a label line with a "no source found"
            # bullet) would otherwise show raw "###"/"-" characters when
            # rendered as one run-on paragraph.
            cleaned = re.sub(r"^#{2,3} ", "", block)
            cleaned = re.sub(r"\n- ", ": ", cleaned).replace("\n", " ")
            pending_paragraph = {"text": cleaned, "sources": []}
    flush_paragraph()
    return sections


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 build_group_context.py <path to xlsx>")
        sys.exit(1)

    xlsx_path = sys.argv[1]
    xls = pd.ExcelFile(xlsx_path)

    result = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH) as f:
            result = json.load(f)

    required_cols = {"ticker", "fiscal_yearquarter"}
    markdown_col_candidates = [
        "contextual_analysis_DATE_AUDITED",
        "contextual_analysis_full",
        "long_format_markdown",
    ]

    for sheet in xls.sheet_names:
        df = xls.parse(sheet)
        if not required_cols.issubset(df.columns):
            print(f"{sheet}: skipped (not a per-observation sheet)")
            continue
        markdown_col = next((c for c in markdown_col_candidates if c in df.columns), None)
        if markdown_col is None:
            print(f"{sheet}: skipped (no recognized markdown column)")
            continue
        for _, row in df.iterrows():
            note_key = f"{row['ticker']}_{row['fiscal_yearquarter']}"
            result[note_key] = parse_markdown(row[markdown_col])
        print(f"{sheet}: {len(df)} observations")

    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n{len(result)} total observations in {OUT_PATH}")


if __name__ == "__main__":
    main()
