"""
merge_wsj_coverage.py
-----------------------
Merges the per-batch WSJ-summary outputs (written by parallel agents, one
per batch of tickers) into data/group_wsj_coverage.json, the file app.py
actually reads.

Run:
    python3 merge_wsj_coverage.py wsj_extracted/batches/batch1_nvda_aapl_output.json wsj_extracted/batches/batch2_googl_msft_output.json ...
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "data", "group_wsj_coverage.json")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 merge_wsj_coverage.py <batch_output.json> [more...]")
        sys.exit(1)

    result = {}
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH) as f:
            result = json.load(f)

    for path in sys.argv[1:]:
        batch = json.load(open(path))
        for k, v in batch.items():
            if "summary" not in v or "sources" not in v:
                print(f"WARNING: {path} entry {k} missing required fields, skipping")
                continue
            result[k] = v
        print(f"{path}: {len(batch)} entries merged")

    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n{len(result)} total observations in {OUT_PATH}")


if __name__ == "__main__":
    main()
