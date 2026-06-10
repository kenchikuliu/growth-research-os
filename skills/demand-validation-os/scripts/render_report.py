#!/usr/bin/env python3
"""Emit starter report JSON skeletons for demand-validation-os."""

from __future__ import annotations

import argparse
import json


TEMPLATES = {
    "attribution": {
        "mode": "榜单归因",
        "core_conclusion": "",
        "main_growth_pages": [],
        "main_growth_terms": [],
        "likely_growth_action": "",
        "reusable_part": "",
        "do_not_copy": "",
        "confidence_and_gaps": "",
    },
    "demand": {
        "mode": "新词 / 新需求验证",
        "core_conclusion": "",
        "demand_reality": "",
        "search_proof": "",
        "trend_pattern": "",
        "page_type_recommendation": "",
        "recommended_action": "",
        "first_batch_of_pages": [
            {
                "working_title": "",
                "page_type": "",
                "primary_intent": "",
                "primary_keyword": "",
                "evidence_basis": "",
                "content_or_tool_structure": "",
                "internal_links_to": "",
                "monetization_path": "",
            }
        ],
        "main_uncertainty": "",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit report skeleton JSON for demand-validation-os.")
    parser.add_argument("--mode", choices=sorted(TEMPLATES), required=True)
    args = parser.parse_args()
    print(json.dumps(TEMPLATES[args.mode], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
