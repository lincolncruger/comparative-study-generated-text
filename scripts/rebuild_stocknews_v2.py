#!/usr/bin/env python3
"""Regenerate Data Visualization 4 StockNews coverage with Why Moved 2.

Each observation is sent as one self-contained request. Results are checkpointed
after every successful response and are not merged into the dashboard until the
entire requested batch has passed deterministic validation.
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "wsj_extracted" / "stocknews_consolidated.json"
STAGE = ROOT / "wsj_extracted" / "stocknews_v2_rebuild.json"
AUDIT = ROOT / "wsj_extracted" / "stocknews_v2_audit.json"
PROMPT = ROOT / "Why Moved 2.md"
API = "https://api.openai.com/v1/responses"
MODEL = "gpt-5.4"
CATEGORIES = [
    "Guidance", "Order book / backlog", "Revenue",
    "New Product Release / Users", "Profits, costs and margin",
    "Debt, leverage and capital raise", "Capex", "Management",
    "Litigation", "Macro and micro development", "Immediate reaction divergence",
]


def env_key(name):
    for line in (ROOT / ".env").read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == name:
            return value.strip().strip('"').strip("'")
    raise RuntimeError(f"{name} is not configured")


def prompt_core():
    text = PROMPT.read_text()
    start = text.index("```\n") + 4
    end = text.index("\n```", start)
    core = text[start:end]
    core = core.replace("[SOURCE]", "StockNews API and validated linked sources")
    core = core.replace("Read: [input file path]", "The single observation follows below.")
    core = core.replace("Output: write to [output file path]", "Return the JSON object described below")
    return core


def schema():
    category = {
        "anyOf": [
            {"type": "null"},
            {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["positive", "negative"]},
                    "attribution": {"type": "string", "enum": ["explicit", "implicit"]},
                    "text": {"type": "string"},
                },
                "required": ["direction", "attribution", "text"],
                "additionalProperties": False,
            },
        ]
    }
    return {
        "type": "object",
        "properties": {
            "summary_analysis": {"type": "string"},
            "explicit_reasons": {"type": "string"},
            "implicit_reasons": {"type": "string"},
            "categories": {
                "type": "object",
                "properties": {name: category for name in CATEGORIES},
                "required": CATEGORIES,
                "additionalProperties": False,
            },
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "published_date": {"type": "string"},
                        "url": {"type": "string"},
                    },
                    "required": ["title", "published_date", "url"],
                    "additionalProperties": False,
                },
            },
            "rejected_sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["title", "reason"],
                    "additionalProperties": False,
                },
            },
            "reaction_reported": {"type": "boolean"},
        },
        "required": ["summary_analysis", "explicit_reasons", "implicit_reasons",
                     "categories", "sources", "rejected_sources", "reaction_reported"],
        "additionalProperties": False,
    }


def output_text(payload):
    for item in payload.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    return part.get("text")
    raise RuntimeError("response contained no output_text")


def validate(note_key, result, observation):
    if list(result["categories"]) != CATEGORIES:
        raise ValueError(f"{note_key}: category schema/order mismatch")
    if not result["sources"]:
        raise ValueError(f"{note_key}: no retained sources")
    explanatory = [result["categories"][name] for name in CATEGORIES[:-1]]
    if not result["reaction_reported"] and any(explanatory):
        raise ValueError(f"{note_key}: categories assigned without a reported reaction")
    divergence = result["categories"]["Immediate reaction divergence"]
    if divergence and divergence.get("attribution") != "implicit":
        raise ValueError(f"{note_key}: immediate-reaction divergence must be implicit")
    input_urls = {a.get("url") for a in observation["articles"] if a.get("url")}
    for source in result["sources"]:
        if source["url"] not in input_urls:
            raise ValueError(f"{note_key}: model returned a URL absent from the evidence packet")
    forbidden = ("ret_1day", "ret_2day", "ret_3day", "ret_5day", "day return")
    prose = " ".join(result.get(k, "") for k in
                     ("summary_analysis", "explicit_reasons", "implicit_reasons")).lower()
    if any(term in prose for term in forbidden):
        raise ValueError(f"{note_key}: output leaked internal return data")


def request(key, instructions, note_key, observation):
    packet = {note_key: observation}
    body = {
        "model": MODEL,
        "reasoning": {"effort": "high"},
        "instructions": instructions,
        "input": json.dumps(packet, ensure_ascii=False),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "why_moved_2_observation",
                "strict": True,
                "schema": schema(),
            }
        },
        "max_output_tokens": 6000,
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.loads(output_text(json.load(response)))


def save(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ticker")
    parser.add_argument("--data-viz-5", action="store_true")
    parser.add_argument("--include-aaon", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    key = env_key("OPENAI_API_KEY")
    observations = json.loads(INPUT.read_text())
    staged = json.loads(STAGE.read_text()) if STAGE.exists() else {}
    audit = json.loads(AUDIT.read_text()) if AUDIT.exists() else {}
    targets = []
    for note_key, observation in observations.items():
        if args.data_viz_5 and observation["ticker"] not in {
            "MTW", "SFIX", "PCTY", "MGNI", "ASO", "NGL", "REZI", "CENTA", "BSM", "METC",
            "BA", "JNJ", "PH", "MRVL", "FTNT", "TMUS", "UBER", "VZ", "MO", "MCD",
        }:
            continue
        if not args.include_aaon and note_key.startswith("AAON_"):
            continue
        if args.ticker and observation["ticker"] != args.ticker:
            continue
        if not args.force and note_key in staged:
            continue
        targets.append((note_key, observation))
    if args.limit:
        targets = targets[:args.limit]

    instructions = prompt_core()
    for index, (note_key, observation) in enumerate(targets, 1):
        started = time.time()
        error = None
        for attempt in range(3):
            try:
                result = request(key, instructions, note_key, observation)
                validate(note_key, result, observation)
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                    RuntimeError, ValueError, json.JSONDecodeError) as exc:
                error = str(exc)
                if attempt == 2:
                    result = None
                    break
                time.sleep(5 * (attempt + 1))
        if result is not None:
            rejected = result.pop("rejected_sources")
            reaction = result.pop("reaction_reported")
            staged[note_key] = result
            audit[note_key] = {
                "status": "validated",
                "model": MODEL,
                "input_articles": len(observation["articles"]),
                "retained_sources": len(result["sources"]),
                "rejected_sources": rejected,
                "reaction_reported": reaction,
                "elapsed_seconds": round(time.time() - started, 2),
            }
            print(f"[{index}/{len(targets)}] {note_key}: validated", flush=True)
        else:
            audit[note_key] = {
                "status": "quarantined", "model": MODEL,
                "input_articles": len(observation["articles"]), "error": error,
            }
            print(f"[{index}/{len(targets)}] {note_key}: QUARANTINED: {error}", flush=True)
        save(STAGE, staged)
        save(AUDIT, audit)

    print(f"staged={len(staged)} audited={len(audit)}")


if __name__ == "__main__":
    main()
