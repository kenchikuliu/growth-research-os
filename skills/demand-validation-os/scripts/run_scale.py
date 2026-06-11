#!/usr/bin/env python3
"""Thin CLI for serial demand-validation workflow runs and batch jobs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import run_demand_workflow
import tabular_io
from workflow_scale import build_scale_output, parse_csv_set, rank_filtered_pairs


def read_jobs(path: str) -> list[dict[str, Any]]:
    rows = tabular_io.read_rows(path)
    jobs = [tabular_io.compact_row(row) for row in rows]
    return [job for job in jobs if isinstance(job, dict)]


def run_one(job: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    mode = (job.get("mode") or args.mode or "").strip()
    if mode not in {"demand", "attribution"}:
        raise ValueError("Each job must provide mode='demand' or mode='attribution'.")

    query = (job.get("query") or args.query or "").strip()
    if not query:
        raise ValueError("Each job must provide query.")

    domain = (job.get("domain") or args.domain or "").strip() or None
    bundle_input = job.get("bundle_input") or args.bundle_input
    trends_input = job.get("trends_input") or args.trends_input
    bundle_payload = job.get("bundle_payload")

    username = (job.get("username") or args.username or os.environ.get("THREEUE_USERNAME") or "").strip()
    password = job.get("password") or args.password or os.environ.get("THREEUE_PASSWORD") or ""

    workflow = run_demand_workflow.build_workflow(
        mode=mode,
        query=query,
        domain=domain or (query if run_demand_workflow.looks_like_domain(query) else None),
        geo=(job.get("geo") or args.geo or "US").strip() or "US",
        username=username,
        password=password,
        max_node_rotations=int(job.get("max_node_rotations") or args.max_node_rotations or 2),
        brand_name=job.get("brand_name") or args.brand_name or "",
        brand_url=job.get("brand_url") or args.brand_url or "",
        primary_cta_url=job.get("primary_cta_url") or args.primary_cta_url or "",
        primary_cta_label=job.get("primary_cta_label") or args.primary_cta_label or "",
        bundle_input=bundle_input,
        bundle_payload=bundle_payload,
        trends_input=trends_input,
    )
    scale_output = build_scale_output(workflow)
    return {
        "workflow": workflow if args.include_workflow else None,
        "scale_output": scale_output,
        "page_artifacts": scale_output.get("artifacts") or {},
        "playbook": workflow.get("playbook") or {},
    }


def compact_result(result: dict[str, Any], include_workflow: bool) -> dict[str, Any]:
    if include_workflow:
        return result
    return {
        "scale_output": result.get("scale_output") or {},
        "page_artifacts": result.get("page_artifacts") or {},
        "playbook": result.get("playbook") or {},
    }


def flatten_scale_result(*, index: int | None, mode: str | None, query: str | None, result: dict[str, Any]) -> dict[str, Any]:
    scale_output = result.get("scale_output") or {}
    decision = scale_output.get("decision") or {}
    direct_answer = scale_output.get("direct_answer") or {}
    page_plan = scale_output.get("page_plan") or {}
    normalized_snapshot = scale_output.get("normalized_snapshot") or {}
    page_artifacts = result.get("page_artifacts") or {}
    first_pages = page_plan.get("first_batch_of_pages") or []
    slugs = [page.get("slug") for page in (page_artifacts.get("pages") or []) if isinstance(page, dict) and page.get("slug")]
    return {
        "index": index if index is not None else "",
        "mode": mode or scale_output.get("mode") or "",
        "query": query or scale_output.get("query") or "",
        "domain": scale_output.get("domain") or "",
        "band": decision.get("band") or "",
        "recommended_action": decision.get("recommended_action") or "",
        "total_score": decision.get("total_score") or "",
        "all_hard_gates_passed": decision.get("all_hard_gates_passed"),
        "core_conclusion": direct_answer.get("core_conclusion") or "",
        "page_type_recommendation": direct_answer.get("page_type_recommendation") or "",
        "tools_ready": ",".join(normalized_snapshot.get("tools_ready") or []),
        "top_page_count": normalized_snapshot.get("top_page_count") or 0,
        "top_keyword_count": normalized_snapshot.get("top_keyword_count") or 0,
        "landing_page_count": normalized_snapshot.get("landing_page_count") or 0,
        "page_cluster_count": normalized_snapshot.get("page_cluster_count") or 0,
        "page_artifact_count": page_plan.get("page_artifact_count") or 0,
        "artifacts_available": page_plan.get("artifacts_available"),
        "first_page_titles": " | ".join(
            page.get("working_title") or page.get("primary_keyword") or ""
            for page in first_pages
            if isinstance(page, dict)
        ),
        "artifact_slugs": " | ".join(slugs),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Thin CLI over demand-validation workflow and page-artifact outputs.")
    parser.add_argument("--mode", choices=["demand", "attribution"])
    parser.add_argument("--query", help="Single query to evaluate")
    parser.add_argument("--domain", help="Optional domain for live capture")
    parser.add_argument("--geo", default="US")
    parser.add_argument("--username", default=os.environ.get("THREEUE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("THREEUE_PASSWORD", ""))
    parser.add_argument("--max-node-rotations", type=int, default=2)
    parser.add_argument("--brand-name", default="")
    parser.add_argument("--brand-url", default="")
    parser.add_argument("--primary-cta-url", default="")
    parser.add_argument("--primary-cta-label", default="")
    parser.add_argument("--bundle-input", help="Reuse an existing capture bundle JSON file")
    parser.add_argument("--trends-input", help="Reuse an existing Google Trends JSON file")
    parser.add_argument("--jobs-input", help="Run a batch JSON array of workflow jobs")
    parser.add_argument("--include-workflow", action="store_true", help="Include full workflow JSON alongside scale output")
    parser.add_argument("--table-output", help="Write flattened scale rows to csv/tsv/xlsx/json")
    parser.add_argument("--min-score", type=int, help="Keep only rows with total_score >= this value")
    parser.add_argument("--allowed-actions", help="Comma-separated allowed recommended_action values")
    parser.add_argument("--require-tools-ready", help="Comma-separated required ready tools, e.g. semrush,similarweb")
    parser.add_argument("--sort-by", default="total_score", help="Flat leaderboard column to sort by")
    parser.add_argument("--ascending", action="store_true", help="Sort ascending instead of descending")
    parser.add_argument("--top", type=int, help="Keep only the top N rows after filtering and sorting")
    parser.add_argument("--output", help="Write JSON to a file")
    args = parser.parse_args()

    allowed_actions = parse_csv_set(args.allowed_actions)
    required_tools = parse_csv_set(args.require_tools_ready)

    if args.jobs_input:
        jobs = read_jobs(args.jobs_input)
        results = []
        flat_rows = []
        for idx, job in enumerate(jobs, start=1):
            result = run_one(job, args)
            mode = (job.get("mode") or args.mode)
            query = (job.get("query") or args.query)
            results.append(
                {
                    "index": idx,
                    "mode": mode,
                    "query": query,
                    **compact_result(result, args.include_workflow),
                }
            )
            flat_rows.append(flatten_scale_result(index=idx, mode=mode, query=query, result=result))
        results, flat_rows = rank_filtered_pairs(
            results,
            flat_rows,
            min_score=args.min_score,
            allowed_actions=allowed_actions or None,
            require_tools_ready=required_tools or None,
            sort_by=args.sort_by,
            ascending=args.ascending,
            top=args.top,
        )
        payload: dict[str, Any] = {
            "job_count": len(results),
            "filters": {
                "min_score": args.min_score,
                "allowed_actions": sorted(allowed_actions),
                "require_tools_ready": sorted(required_tools),
                "sort_by": args.sort_by,
                "ascending": args.ascending,
                "top": args.top,
            },
            "results": results,
        }
    else:
        result = run_one({}, args)
        payload = compact_result(result, args.include_workflow)
        flat_rows = [flatten_scale_result(index=None, mode=args.mode, query=args.query, result=result)]

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    if args.table_output:
        tabular_io.write_rows(args.table_output, flat_rows, sheet_name="scale_results")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
