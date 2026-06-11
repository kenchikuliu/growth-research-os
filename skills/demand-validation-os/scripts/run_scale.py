#!/usr/bin/env python3
"""Thin CLI for serial demand-validation workflow runs and batch jobs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import run_demand_workflow
from workflow_scale import build_scale_output


def read_jobs(path: str) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text())
    if isinstance(payload, list):
        return [job for job in payload if isinstance(job, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
        return [job for job in payload["jobs"] if isinstance(job, dict)]
    raise ValueError("Jobs input must be a JSON array or an object with a 'jobs' array.")


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
    }


def compact_result(result: dict[str, Any], include_workflow: bool) -> dict[str, Any]:
    if include_workflow:
        return result
    return {
        "scale_output": result.get("scale_output") or {},
        "page_artifacts": result.get("page_artifacts") or {},
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
    parser.add_argument("--output", help="Write JSON to a file")
    args = parser.parse_args()

    if args.jobs_input:
        jobs = read_jobs(args.jobs_input)
        results = []
        for idx, job in enumerate(jobs, start=1):
            result = run_one(job, args)
            results.append(
                {
                    "index": idx,
                    "mode": (job.get("mode") or args.mode),
                    "query": (job.get("query") or args.query),
                    **compact_result(result, args.include_workflow),
                }
            )
        payload: dict[str, Any] = {
            "job_count": len(results),
            "results": results,
        }
    else:
        result = run_one({}, args)
        payload = compact_result(result, args.include_workflow)

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
