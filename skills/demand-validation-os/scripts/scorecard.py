#!/usr/bin/env python3
"""Compute weighted scorecards for demand-validation-os."""

from __future__ import annotations

import argparse
import json
import sys


MODE_CONFIG = {
    "attribution": {
        "weights": {
            "page_change_clarity": 20,
            "keyword_change_confidence": 15,
            "page_type_pattern": 15,
            "time_window_alignment": 10,
            "structural_expansion": 15,
            "offsite_amplification": 10,
            "chain_closure": 15,
        },
        "bands": [
            (39, "weak_hypothesis"),
            (59, "partial_explanation"),
            (79, "solid_attribution"),
            (100, "strong_attribution"),
        ],
        "hard_gates": [],
    },
    "demand": {
        "weights": {
            "demand_reality": 20,
            "search_carry": 15,
            "trend_stability": 10,
            "serp_entry": 15,
            "page_intent_fit": 10,
            "clusterability": 10,
            "monetization": 10,
            "execution_fit": 10,
        },
        "bands": [
            (39, "stop"),
            (54, "watch"),
            (69, "ship_one_page"),
            (84, "ship_cluster"),
            (100, "build_site"),
        ],
        "hard_gates": [
            ("demand_reality", 3, "Demand is not real enough yet."),
            ("page_intent_fit", 3, "Page type is not clear enough for scale."),
        ],
    },
}


def parse_score_items(items: list[str]) -> dict[str, int]:
    scores: dict[str, int] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid score '{item}'. Use key=value.")
        key, raw = item.split("=", 1)
        key = key.strip()
        raw = raw.strip()
        if not key:
            raise ValueError(f"Invalid score '{item}'. Empty key.")
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"Score '{item}' must be an integer.") from exc
        if value < 1 or value > 5:
            raise ValueError(f"Score '{item}' must be between 1 and 5.")
        scores[key] = value
    return scores


def compute(mode: str, scores: dict[str, int]) -> dict[str, object]:
    config = MODE_CONFIG[mode]
    weights = config["weights"]
    missing = [key for key in weights if key not in scores]
    extra = [key for key in scores if key not in weights]
    if missing:
        raise ValueError(f"Missing scores: {', '.join(missing)}")
    if extra:
        raise ValueError(f"Unknown scores for mode '{mode}': {', '.join(extra)}")

    weighted_points = 0.0
    breakdown = []
    for key, weight in weights.items():
        raw = scores[key]
        contribution = (raw / 5.0) * weight
        weighted_points += contribution
        breakdown.append(
            {
                "key": key,
                "raw_score": raw,
                "weight": weight,
                "weighted_points": round(contribution, 2),
            }
        )

    total = round(weighted_points, 2)
    band = None
    for upper, label in config["bands"]:
        if total <= upper:
            band = label
            break

    gate_results = []
    for key, threshold, message in config["hard_gates"]:
        passed = scores[key] >= threshold
        gate_results.append(
            {
                "key": key,
                "threshold": threshold,
                "actual": scores[key],
                "passed": passed,
                "message": message if not passed else "",
            }
        )

    return {
        "mode": mode,
        "total_score": total,
        "band": band,
        "breakdown": breakdown,
        "hard_gates": gate_results,
        "all_hard_gates_passed": all(item["passed"] for item in gate_results) if gate_results else True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute demand-validation-os scorecards.")
    parser.add_argument("--mode", choices=sorted(MODE_CONFIG), required=True)
    parser.add_argument("--scores", nargs="+", required=True, help="key=value pairs with 1-5 integer values")
    args = parser.parse_args()

    try:
        scores = parse_score_items(args.scores)
        result = compute(args.mode, scores)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
