#!/usr/bin/env python3
"""Validate and publish all completed Data Viz 5 StockNews shards."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "wsj_extracted" / "stocknews_consolidated.json"
DESTINATION = ROOT / "data" / "stocknews_coverage.json"
SOURCES = [
    ROOT / "wsj_extracted" / "stocknews_v2_rebuild.json",
    ROOT / "wsj_extracted" / "stocknews_v2_codex_shard_0.json",
    ROOT / "wsj_extracted" / "stocknews_v2_codex_shard_1.json",
    ROOT / "wsj_extracted" / "stocknews_v2_codex_shard_2.json",
    ROOT / "wsj_extracted" / "stocknews_v2_claude.json",
]
CATEGORIES = [
    "Guidance", "Order book / backlog", "Revenue",
    "New Product Release / Users", "Profits, costs and margin",
    "Debt, leverage and capital raise", "Capex", "Management",
    "Litigation", "Macro and micro development", "Immediate reaction divergence",
]


def load(path):
    return json.loads(path.read_text()) if path.exists() else {}


evidence = load(EVIDENCE)
merged = {}
for source_path in SOURCES:
    for note_key, output in load(source_path).items():
        if note_key in merged:
            raise RuntimeError(f"Overlapping generated output: {note_key}")
        if note_key not in evidence:
            raise RuntimeError(f"Missing evidence packet: {note_key}")
        if list((output.get("categories") or {}).keys()) != CATEGORIES:
            raise RuntimeError(f"Invalid category schema: {note_key}")
        allowed_urls = {
            article.get("url") for article in evidence[note_key].get("articles", []) if article.get("url")
        }
        for source in output.get("sources", []):
            if source.get("url") not in allowed_urls:
                raise RuntimeError(f"Source URL absent from evidence: {note_key}")
        prose = " ".join(
            str(output.get(field, ""))
            for field in ("summary_analysis", "explicit_reasons", "implicit_reasons")
        ).lower()
        if any(token in prose for token in ("ret_1day", "ret_2day", "ret_3day", "ret_5day")):
            raise RuntimeError(f"Computed return leaked into prose: {note_key}")
        divergence = output["categories"].get("Immediate reaction divergence")
        if divergence and divergence.get("attribution") != "implicit":
            raise RuntimeError(f"Invalid divergence attribution: {note_key}")
        merged[note_key] = output

destination = load(DESTINATION)
destination.update(merged)
temporary = DESTINATION.with_suffix(".json.tmp")
temporary.write_text(json.dumps(destination, indent=2, ensure_ascii=False) + "\n")
os.replace(temporary, DESTINATION)
print(f"published={len(merged)} dashboard_total={len(destination)}")

