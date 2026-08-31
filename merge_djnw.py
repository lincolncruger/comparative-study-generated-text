"""
merge_djnw.py
--------------
Merges Dow Jones Newswires-analysis batch outputs into
data/group_djnw_coverage.json (additive, same pattern as merge_wsj_v2.py).

Normalizes every entry to a "sources" list -- Group 1/2 batches wrote a
single "source" dict (one DJNW link per observation), while Group 3
observations can have 2-3 DJNW articles synthesized together, so batches
write "sources" (a list) instead. Both are accepted and normalized to
"sources" here so app.py only has to handle one shape.

Run:
    python3 merge_djnw.py wsj_extracted/djnw_batches/batchA_..._output.json ...
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "data", "group_djnw_coverage.json")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 merge_djnw.py <batch_output.json> [more...]")
        sys.exit(1)

    result = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH) as f:
            result = json.load(f)
        # Normalize any pre-existing legacy singular "source" entries too.
        for v in result.values():
            if "source" in v and "sources" not in v:
                v["sources"] = [v.pop("source")]

    for path in sys.argv[1:]:
        batch = json.load(open(path))
        n = 0
        for k, v in batch.items():
            if "source" in v and "sources" not in v:
                v["sources"] = [v.pop("source")]
            if not all(f in v for f in ("summary_analysis", "why_moved", "sources")):
                continue
            result[k] = v
            n += 1
        print(f"{path}: {n} entries merged")

    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n{len(result)} total observations in {OUT_PATH}")


if __name__ == "__main__":
    main()
