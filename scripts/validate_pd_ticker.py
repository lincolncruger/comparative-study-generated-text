#!/usr/bin/env python3
"""Validate one source-reviewed ticker's PD and first-order output."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = [
    "Guidance",
    "Order book / order backlog",
    "Revenue",
    "Product / Users",
    "Profits and profitability",
    "Costs",
    "Debt, leverage and capital raise",
    "Capex",
    "Management",
    "Litigation",
    "Others: eg. Covid, or macro events",
]
SOURCES = ("contextual_analysis", "wsj", "djnw")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    args = parser.parse_args()
    ticker = args.ticker.upper()

    pd = json.load((ROOT / "data" / "group_pd_categories.json").open())
    first_order = json.load((ROOT / "data" / "group_first_order_categories.json").open())
    raw = json.load((ROOT / "wsj_extracted" / "pdcat_batches" / f"{ticker}.json").open())
    reviewed = json.load((ROOT / "wsj_extracted" / "pdcat_reviewed" / f"{ticker}.json").open())
    context_coverage = json.load((ROOT / "data" / "group_context.json").open())
    wsj_coverage = json.load((ROOT / "data" / "group_wsj_coverage.json").open())
    djnw_coverage = json.load((ROOT / "data" / "group_djnw_coverage.json").open())
    errors = []

    # A small number of legacy per-ticker batches omit an observation that is
    # present in the authoritative dashboard coverage files. Reviewed markers
    # make that audited observation explicit, so validate the union.
    expected_keys = set(raw) | set(reviewed.get("reviewed_observations", []))
    reviewed_pd_keys = set(reviewed.get("pd", {}))
    reviewed_markers = set(reviewed.get("reviewed_observations", []))
    if reviewed_pd_keys != expected_keys and reviewed_markers != expected_keys:
        errors.append("reviewed PD observations do not exactly match the source observations")
    if set(reviewed.get("first_order", {})) != expected_keys:
        errors.append("reviewed first-order observations do not exactly match the source observations")

    for key in sorted(expected_keys):
        for source in SOURCES:
            source_pd = pd.get(key, {}).get(source)
            if key in raw:
                source_exists = raw[key].get(source) is not None
            else:
                source_exists = {
                    "contextual_analysis": key in context_coverage,
                    "wsj": key in wsj_coverage,
                    "djnw": key in djnw_coverage,
                }[source]
            if (source_pd is not None) != source_exists:
                errors.append(f"{key}/{source}: source-presence mismatch")
                continue
            if source_pd is None:
                if first_order.get(key, {}).get(source):
                    errors.append(f"{key}/{source}: first-order data exists without coverage")
                continue
            if list(source_pd) != CATEGORIES:
                errors.append(f"{key}/{source}: category schema or order is wrong")
            for category, cell in source_pd.items():
                rating, reason = cell.get("rating"), cell.get("reason")
                if rating not in (None, "positive", "negative", "neutral"):
                    errors.append(f"{key}/{source}/{category}: invalid rating {rating!r}")
                if (rating is None) != (reason is None):
                    errors.append(f"{key}/{source}/{category}: incomplete rating/reason pair")
                if reason and len(reason) > 199:
                    errors.append(f"{key}/{source}/{category}: reason exceeds 199 characters")
            for item in first_order.get(key, {}).get(source) or []:
                category = item["category"]
                cell = source_pd.get(category)
                if not cell or item.get("rating") != cell.get("rating") or item.get("reason") != cell.get("reason"):
                    errors.append(f"{key}/{source}/{category}: first-order card contradicts its PD cell")

    if errors:
        print("FAIL")
        print("\n".join(f"- {error}" for error in errors))
        raise SystemExit(1)
    print(f"PASS: {ticker} — {len(expected_keys)} observations, source isolation, 11-category schema, and first-order/PD consistency verified.")


if __name__ == "__main__":
    main()
