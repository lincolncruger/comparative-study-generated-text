#!/usr/bin/env python3
"""Split unfinished Data Viz 5 StockNews observations into disjoint halves."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "wsj_extracted" / "stocknews_consolidated.json"
STAGED = ROOT / "wsj_extracted" / "stocknews_v2_rebuild.json"
OPENAI_KEYS = ROOT / "data" / "dataviz5_openai_batch_keys.json"
CLAUDE_KEYS = ROOT / "data" / "dataviz5_claude_batch_keys.json"
CLAUDE_PACKET = ROOT / "data" / "dataviz5_claude_evidence.json"

TICKERS = {
    "MTW", "SFIX", "PCTY", "MGNI", "ASO", "NGL", "REZI", "CENTA", "BSM", "METC",
    "BA", "JNJ", "PH", "MRVL", "FTNT", "TMUS", "UBER", "VZ", "MO", "MCD",
}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


evidence = json.loads(EVIDENCE.read_text())
staged = json.loads(STAGED.read_text()) if STAGED.exists() else {}
unfinished = sorted(
    key for key, observation in evidence.items()
    if observation.get("ticker") in TICKERS
    and key not in staged
    and any(article.get("full_text") for article in observation.get("articles", []))
)
openai_keys = unfinished[::2]
claude_keys = unfinished[1::2]
save(OPENAI_KEYS, openai_keys)
save(CLAUDE_KEYS, claude_keys)
save(CLAUDE_PACKET, {key: evidence[key] for key in claude_keys})
print(f"unfinished={len(unfinished)} openai={len(openai_keys)} claude={len(claude_keys)}")

