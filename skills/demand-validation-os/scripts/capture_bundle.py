#!/usr/bin/env python3
"""Run Semrush and Similarweb captures serially and emit a combined JSON bundle."""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from pathlib import Path
from typing import Any

import capture_semrush
import capture_similarweb
from browser_capture import iso_utc_now


def assess_capture_quality(tool: str, data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "status": "error",
            "core_ready": False,
            "score": 0,
            "reasons": ["missing-result"],
        }
    if tool == "semrush":
        rpc_count = int(data.get("raw_artifacts", {}).get("rpc_result_count") or 0)
        organic_traffic = data.get("domain_overview", {}).get("organic_traffic")
        organic_keywords = data.get("domain_overview", {}).get("organic_keywords")
        reasons = []
        if rpc_count <= 0:
            reasons.append("rpc-results-missing")
        if organic_traffic is None:
            reasons.append("organic-traffic-missing")
        if organic_keywords is None:
            reasons.append("organic-keywords-missing")
        core_ready = not reasons
        return {
            "status": "ok" if core_ready else "partial",
            "core_ready": core_ready,
            "score": 3 if core_ready else 1,
            "reasons": reasons or ["core-report-ready"],
        }
    if tool == "similarweb":
        website_perf = data.get("website_evidence", {}).get("website_performance", {})
        website_content = data.get("website_evidence", {}).get("website_content", {})
        search_overview = data.get("website_evidence", {}).get("search_overview", {})
        home_signals = data.get("website_evidence", {}).get("home_signals", {})
        quick_search = data.get("website_evidence", {}).get("quick_search", {})
        folder_rows = len((((website_content or {}).get("summary") or {}).get("rows") or []))
        paid_landing_rows = len((((search_overview or {}).get("paid_landing_pages") or {}).get("rows") or []))
        non_brand_keyword_rows = len((((search_overview or {}).get("top_non_brand_keywords") or {}).get("rows") or []))
        if website_perf.get("available") and (folder_rows > 0 or paid_landing_rows > 0 or non_brand_keyword_rows > 0):
            reasons = ["website-performance-ready"]
            if folder_rows > 0:
                reasons.append("website-content-ready")
            if paid_landing_rows > 0:
                reasons.append("paid-landing-pages-ready")
            if non_brand_keyword_rows > 0:
                reasons.append("non-brand-keywords-ready")
            return {
                "status": "ok",
                "core_ready": True,
                "score": 4,
                "reasons": reasons,
            }
        if website_perf.get("available"):
            return {
                "status": "ok",
                "core_ready": True,
                "score": 3,
                "reasons": ["website-performance-ready"],
            }
        if home_signals.get("priority_alerts") or quick_search.get("ok"):
            reasons = []
            if quick_search.get("ok"):
                reasons.append("quick-search-ready")
            if home_signals.get("priority_alerts"):
                reasons.append("priority-alerts-ready")
            return {
                "status": "partial",
                "core_ready": False,
                "score": 2,
                "reasons": reasons,
            }
        return {
            "status": "partial",
            "core_ready": False,
            "score": 1,
            "reasons": ["core-report-missing"],
        }
    return {
        "status": "partial",
        "core_ready": False,
        "score": 0,
        "reasons": [f"unknown-tool:{tool}"],
    }


def run_capture_once(
    *,
    tool: str,
    query: str,
    username: str,
    password: str,
    session: str,
    keep_session: bool,
    attempt: int,
    max_node_rotations: int,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    started_at = iso_utc_now()
    start_monotonic = time.monotonic()
    try:
        if tool == "semrush":
            data = capture_semrush.collect(
                query,
                username,
                password,
                session,
                keep_session=keep_session,
                max_node_rotations=max_node_rotations,
            )
        elif tool == "similarweb":
            data = capture_similarweb.collect(
                query,
                username,
                password,
                session,
                keep_session=keep_session,
                max_node_rotations=max_node_rotations,
            )
        else:
            raise ValueError(f"Unsupported tool: {tool}")
        quality = assess_capture_quality(tool, data)
        meta = {
            "tool": tool,
            "session": session,
            "attempt": attempt,
            "status": quality["status"],
            "started_at": started_at,
            "duration_seconds": round(time.monotonic() - start_monotonic, 2),
            "quality": quality,
        }
        return data, meta
    except Exception as exc:
        meta = {
            "tool": tool,
            "session": session,
            "attempt": attempt,
            "status": "error",
            "started_at": started_at,
            "duration_seconds": round(time.monotonic() - start_monotonic, 2),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "quality": {
                "status": "error",
                "core_ready": False,
                "score": 0,
                "reasons": [type(exc).__name__],
            },
        }
        return None, meta


def preferred_attempts(tool: str) -> int:
    if tool == "similarweb":
        return 2
    return 1


def pick_better_result(
    current: tuple[dict[str, Any] | None, dict[str, Any]] | None,
    candidate: tuple[dict[str, Any] | None, dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if current is None:
        return candidate
    _, current_meta = current
    _, candidate_meta = candidate
    current_score = int(current_meta.get("quality", {}).get("score") or 0)
    candidate_score = int(candidate_meta.get("quality", {}).get("score") or 0)
    if candidate_score > current_score:
        return candidate
    return current


def run_capture_with_retries(
    *,
    tool: str,
    query: str,
    username: str,
    password: str,
    session_prefix: str,
    keep_session: bool,
    max_attempts: int,
    max_node_rotations: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any]]:
    best: tuple[dict[str, Any] | None, dict[str, Any]] | None = None
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        session = f"{session_prefix}-{tool}-a{attempt}"
        result = run_capture_once(
            tool=tool,
            query=query,
            username=username,
            password=password,
            session=session,
            keep_session=keep_session,
            attempt=attempt,
            max_node_rotations=max_node_rotations,
        )
        data, meta = result
        attempts.append(meta)
        best = pick_better_result(best, result)
        if meta.get("quality", {}).get("core_ready"):
            break
    assert best is not None
    best_data, best_meta = best
    best_meta = {
        **best_meta,
        "attempts_ran": len(attempts),
        "attempt_sessions": [meta["session"] for meta in attempts],
    }
    return best_data, attempts, best_meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture Semrush and Similarweb serially into one JSON bundle.")
    parser.add_argument("--query", required=True, help="Domain to inspect")
    parser.add_argument("--username", default=os.environ.get("THREEUE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("THREEUE_PASSWORD", ""))
    parser.add_argument("--session-prefix", default="dvos-bundle", help="Base session prefix for serial tool runs")
    parser.add_argument("--output", help="Write combined JSON bundle to a file")
    parser.add_argument(
        "--tools",
        nargs="+",
        choices=["semrush", "similarweb"],
        default=["semrush", "similarweb"],
        help="Tools to run, in order. Default: semrush similarweb",
    )
    parser.add_argument("--keep-session", action="store_true", help="Keep the final tool session(s) open after capture")
    parser.add_argument(
        "--max-node-rotations",
        type=int,
        default=2,
        help="Rotate to a different 3ue node when daily usage limit is detected",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue to the next tool if one capture fails. Default behavior is fail fast.",
    )
    args = parser.parse_args()

    if not args.username or not args.password:
        raise SystemExit("Missing 3ue credentials. Set THREEUE_USERNAME and THREEUE_PASSWORD or pass --username/--password.")

    bundle: dict[str, Any] = {
        "query": {"type": "domain", "value": args.query},
        "captured_at": iso_utc_now(),
        "capture_mode": "serial",
        "notes": [
            "Semrush and Similarweb captures were executed serially to avoid cross-session interference.",
            "Use this bundle executor instead of launching both browser-backed capture scripts in parallel.",
            "Bundle success is now quality-aware: a tool is only fully successful when its core structured report is ready.",
        ],
        "runs": [],
        "results": {},
    }

    failures = 0
    for tool in args.tools:
        max_attempts = preferred_attempts(tool)
        data, attempts, best_meta = run_capture_with_retries(
            tool=tool,
            query=args.query,
            username=args.username,
            password=args.password,
            session_prefix=args.session_prefix,
            keep_session=args.keep_session,
            max_attempts=max_attempts,
            max_node_rotations=args.max_node_rotations,
        )
        bundle["runs"].extend(attempts)
        bundle["results"][tool] = {
            "best_attempt": best_meta,
            "data": data,
        }
        if data is not None:
            if best_meta.get("quality", {}).get("core_ready"):
                continue
            if not args.continue_on_error:
                failures += 1
                break
            failures += 1
            continue
        failures += 1
        if not args.continue_on_error:
            break

    bundle["summary"] = {
        "requested_tools": args.tools,
        "completed_tools": [
            tool
            for tool in args.tools
            if bundle["results"].get(tool, {}).get("best_attempt", {}).get("status") in {"ok", "partial"}
        ],
        "core_ready_tools": [
            tool
            for tool in args.tools
            if bundle["results"].get(tool, {}).get("best_attempt", {}).get("quality", {}).get("core_ready")
        ],
        "partial_tools": [
            tool
            for tool in args.tools
            if bundle["results"].get(tool, {}).get("best_attempt", {}).get("status") == "partial"
        ],
        "failed_tools": [
            tool
            for tool in args.tools
            if bundle["results"].get(tool, {}).get("best_attempt", {}).get("status") == "error"
            or tool not in bundle["results"]
        ],
        "all_succeeded": failures == 0 and all(
            bundle["results"].get(tool, {}).get("best_attempt", {}).get("quality", {}).get("core_ready")
            for tool in args.tools
        ),
    }

    text = json.dumps(bundle, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
