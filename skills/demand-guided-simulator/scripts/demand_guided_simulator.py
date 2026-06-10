#!/usr/bin/env python3
"""One-click simulator wrapper for staged demand and attribution workflows."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


SIMULATOR_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
DVOS_SCRIPTS = REPO_ROOT / "skills" / "demand-validation-os" / "scripts"
if str(DVOS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DVOS_SCRIPTS))

import run_demand_workflow


def get_path(data: Any, *path: Any, default: Any = None) -> Any:
    current = data
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and isinstance(key, int):
            if key < 0 or key >= len(current):
                return default
            current = current[key]
        else:
            return default
        if current is None:
            return default
    return current


def build_evidence_status(workflow: dict[str, Any]) -> dict[str, Any]:
    tool_capture = get_path(workflow, "evidence", "tool_capture", default={}) or {}
    trends = get_path(workflow, "evidence", "trends", default={}) or {}
    knowledge = workflow.get("knowledge", {}) or {}
    core_ready_tools = get_path(tool_capture, "summary", "core_ready_tools", default=[]) or []
    similarweb = (((tool_capture.get("results") or {}).get("similarweb") or {}).get("data") or {}).get("website_evidence") or {}
    semrush = (((tool_capture.get("results") or {}).get("semrush") or {}).get("data") or {}) or {}
    return {
        "trends_available": bool(trends.get("available")),
        "core_ready_tools": core_ready_tools,
        "semrush_top_pages": len(semrush.get("top_pages") or []),
        "semrush_top_keywords": len(semrush.get("top_organic_keywords") or []),
        "similarweb_website_performance": bool(get_path(similarweb, "website_performance", "available")),
        "similarweb_website_content_rows": len(get_path(similarweb, "website_content", "summary", "rows", default=[]) or []),
        "similarweb_paid_landing_rows": len(get_path(similarweb, "search_overview", "paid_landing_pages", "rows", default=[]) or []),
        "similarweb_non_brand_keyword_rows": len(get_path(similarweb, "search_overview", "top_non_brand_keywords", "rows", default=[]) or []),
        "gefei_summary_available": bool(get_path(knowledge, "gefei", "summary", default="")),
        "chuhai_method_available": bool(get_path(knowledge, "chuhai", "focus_methods", 0, default="")),
    }


def build_stage_index(guided_flow: dict[str, Any]) -> list[dict[str, Any]]:
    stages = guided_flow.get("stages") or []
    return [
        {
            "step": stage.get("step"),
            "title": stage.get("title"),
            "question": stage.get("question"),
        }
        for stage in stages
    ]


def build_simulator_surface(workflow: dict[str, Any], view: str, step: int | None = None) -> dict[str, Any]:
    guided = workflow.get("guided_flow") or {}
    stages = guided.get("stages") or []
    entry = guided.get("entry") or {}
    direct_result = guided.get("direct_result") or workflow.get("decision") or {}
    evidence_status = build_evidence_status(workflow)

    if view == "guided":
        return {
            "mode": workflow.get("mode"),
            "entry": entry,
            "step_count": guided.get("step_count", len(stages)),
            "stage_index": build_stage_index(guided),
            "stages": stages,
            "direct_result": direct_result,
            "evidence_status": evidence_status,
        }

    if view == "direct":
        return {
            "mode": workflow.get("mode"),
            "entry": entry,
            "direct_result": direct_result,
            "report": workflow.get("report"),
            "evidence_status": evidence_status,
            "method_alignment": workflow.get("method_alignment"),
        }

    if view == "step":
        if step is None:
            raise ValueError("--step is required when --view step is used")
        selected = next((stage for stage in stages if int(stage.get("step", 0)) == step), None)
        if selected is None:
            raise ValueError(f"Step {step} is out of range for this workflow")
        return {
            "mode": workflow.get("mode"),
            "entry": entry,
            "step_count": guided.get("step_count", len(stages)),
            "current_step": selected,
            "stage_index": build_stage_index(guided),
            "direct_result": direct_result,
            "evidence_status": evidence_status,
        }

    return {
        "mode": workflow.get("mode"),
        "entry": entry,
        "guided_path": {
            "step_count": guided.get("step_count", len(stages)),
            "stage_index": build_stage_index(guided),
        },
        "direct_result": direct_result,
        "report": workflow.get("report"),
        "evidence_status": evidence_status,
        "method_alignment": workflow.get("method_alignment"),
        "notes": [
            "Use view=guided for the full staged path.",
            "Use view=step with --step N for one unlocked panel at a time.",
            "Use view=direct for the fast result surface.",
        ],
    }


def load_or_build_workflow(args: argparse.Namespace) -> dict[str, Any]:
    if args.workflow_input:
        return json.loads(Path(args.workflow_input).read_text())

    domain = args.domain or (args.query if run_demand_workflow.looks_like_domain(args.query) else None)
    needs_live_capture = domain and not args.bundle_input
    if needs_live_capture and (not args.username or not args.password):
        raise SystemExit("Missing 3ue credentials. Set THREEUE_USERNAME / THREEUE_PASSWORD or pass --username / --password.")

    return run_demand_workflow.build_workflow(
        mode=args.mode,
        query=args.query,
        domain=domain,
        geo=args.geo,
        username=args.username,
        password=args.password,
        max_node_rotations=args.max_node_rotations,
        bundle_input=args.bundle_input,
        trends_input=args.trends_input,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or render the demand guided simulator surface.")
    parser.add_argument("--mode", choices=["demand", "attribution"], help="Workflow mode when building live")
    parser.add_argument("--query", help="Keyword or domain to inspect when building live")
    parser.add_argument("--domain", help="Competitor or target domain for Semrush/Similarweb capture")
    parser.add_argument("--geo", default="US")
    parser.add_argument("--username", default=os.environ.get("THREEUE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("THREEUE_PASSWORD", ""))
    parser.add_argument("--max-node-rotations", type=int, default=2)
    parser.add_argument("--bundle-input", help="Reuse an existing capture_bundle JSON file")
    parser.add_argument("--trends-input", help="Reuse an existing Google Trends JSON file")
    parser.add_argument("--workflow-input", help="Reuse an existing workflow JSON file")
    parser.add_argument("--view", choices=["simulator", "guided", "direct", "step"], default="simulator")
    parser.add_argument("--step", type=int, help="Specific step number for view=step")
    parser.add_argument("--output", help="Write simulator JSON to a file")
    args = parser.parse_args()

    if not args.workflow_input and (not args.mode or not args.query):
        raise SystemExit("Provide --workflow-input or both --mode and --query.")

    workflow = load_or_build_workflow(args)
    data = build_simulator_surface(workflow, view=args.view, step=args.step)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
