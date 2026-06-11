#!/usr/bin/env python3
"""Unified API/CLI for 3ue-backed Semrush and Similarweb capture."""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from pathlib import Path
from typing import Any, Sequence

import capture_semrush
import capture_similarweb
from capture_normalize import build_normalized_capture
from browser_capture import iso_utc_now


API_NAME = "demand-validation-os.capture_api"
API_VERSION = "2026-06-11"
SUPPORTED_TOOLS = ("semrush", "similarweb")


def normalize_requested_tools(tools: Sequence[str] | None) -> list[str]:
    requested = list(tools or SUPPORTED_TOOLS)
    normalized: list[str] = []
    for tool in requested:
        if tool not in SUPPORTED_TOOLS:
            raise ValueError(f"Unsupported tool: {tool}")
        if tool in normalized:
            continue
        normalized.append(tool)
    return normalized or list(SUPPORTED_TOOLS)


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
        landing_pages_research = data.get("website_evidence", {}).get("landing_pages_research", {})
        keyword_research = data.get("website_evidence", {}).get("keyword_research", {})
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
            if landing_pages_research.get("available"):
                reasons.append("landing-pages-research-ready")
            if keyword_research.get("available"):
                reasons.append("keyword-research-ready")
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


def preferred_attempts(tool: str) -> int:
    if tool == "similarweb":
        return 2
    return 1


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


def build_execution_policy(
    *,
    tools: Sequence[str] | None,
    session_prefix: str,
    keep_session: bool,
    max_node_rotations: int,
    continue_on_error: bool,
) -> dict[str, Any]:
    normalized_tools = normalize_requested_tools(tools)
    return {
        "device_scope": "single_device",
        "browser_scope": "single_browser",
        "page_scope": "single_active_page",
        "run_mode": "serial",
        "tool_order": normalized_tools,
        "session_strategy": "isolated_session_per_attempt",
        "tab_strategy": "collapse_non_active_tabs_after_tool_open",
        "dashboard_strategy": "reopen_dashboard_only_when_needed",
        "keep_session": keep_session,
        "continue_on_error": continue_on_error,
        "max_node_rotations": max_node_rotations,
        "session_prefix": session_prefix,
    }


def build_capture_summary(bundle: dict[str, Any], tools: Sequence[str], failures: int) -> dict[str, Any]:
    requested_tools = list(tools)
    return {
        "requested_tools": requested_tools,
        "completed_tools": [
            tool
            for tool in requested_tools
            if bundle["results"].get(tool, {}).get("best_attempt", {}).get("status") in {"ok", "partial"}
        ],
        "core_ready_tools": [
            tool
            for tool in requested_tools
            if bundle["results"].get(tool, {}).get("best_attempt", {}).get("quality", {}).get("core_ready")
        ],
        "partial_tools": [
            tool
            for tool in requested_tools
            if bundle["results"].get(tool, {}).get("best_attempt", {}).get("status") == "partial"
        ],
        "failed_tools": [
            tool
            for tool in requested_tools
            if bundle["results"].get(tool, {}).get("best_attempt", {}).get("status") == "error"
            or tool not in bundle["results"]
        ],
        "all_succeeded": failures == 0
        and all(
            bundle["results"].get(tool, {}).get("best_attempt", {}).get("quality", {}).get("core_ready")
            for tool in requested_tools
        ),
    }


def run_capture_plan(
    *,
    query: str,
    username: str,
    password: str,
    tools: Sequence[str] | None = None,
    session_prefix: str = "dvos-capture",
    keep_session: bool = False,
    max_node_rotations: int = 2,
    continue_on_error: bool = False,
    request_id: str = "",
) -> dict[str, Any]:
    normalized_tools = normalize_requested_tools(tools)
    policy = build_execution_policy(
        tools=normalized_tools,
        session_prefix=session_prefix,
        keep_session=keep_session,
        max_node_rotations=max_node_rotations,
        continue_on_error=continue_on_error,
    )
    bundle: dict[str, Any] = {
        "api": {
            "name": API_NAME,
            "version": API_VERSION,
        },
        "request": {
            "id": request_id.strip() or None,
            "query": {"type": "domain", "value": query},
            "tools": normalized_tools,
        },
        "captured_at": iso_utc_now(),
        "capture_mode": "serial",
        "execution_policy": policy,
        "notes": [
            "This unified capture entrypoint is the preferred API/CLI for later scale or skill calls.",
            "Execution policy is intentionally strict: single device, single browser, single active page, serial tool order.",
            "After 3ue opens a tool tab, background tabs are collapsed so each live browser stays on one active page.",
        ],
        "runs": [],
        "results": {},
    }

    failures = 0
    for tool in normalized_tools:
        max_attempts = preferred_attempts(tool)
        data, attempts, best_meta = run_capture_with_retries(
            tool=tool,
            query=query,
            username=username,
            password=password,
            session_prefix=session_prefix,
            keep_session=keep_session,
            max_attempts=max_attempts,
            max_node_rotations=max_node_rotations,
        )
        bundle["runs"].extend(attempts)
        bundle["results"][tool] = {
            "best_attempt": best_meta,
            "data": data,
        }
        if data is not None and best_meta.get("quality", {}).get("core_ready"):
            continue
        failures += 1
        if not continue_on_error:
            break

    bundle["summary"] = build_capture_summary(bundle, normalized_tools, failures)
    bundle["normalized"] = build_normalized_capture(bundle)
    return bundle


def run_capture_tool(
    *,
    tool: str,
    query: str,
    username: str,
    password: str,
    session_prefix: str = "dvos-capture",
    keep_session: bool = False,
    max_node_rotations: int = 2,
    request_id: str = "",
) -> dict[str, Any]:
    return run_capture_plan(
        query=query,
        username=username,
        password=password,
        tools=[tool],
        session_prefix=session_prefix,
        keep_session=keep_session,
        max_node_rotations=max_node_rotations,
        continue_on_error=False,
        request_id=request_id,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified API/CLI for serial 3ue-backed Semrush and Similarweb capture.")
    parser.add_argument("--query", required=True, help="Domain to inspect")
    parser.add_argument("--username", default=os.environ.get("THREEUE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("THREEUE_PASSWORD", ""))
    parser.add_argument(
        "--tools",
        nargs="+",
        choices=list(SUPPORTED_TOOLS),
        default=list(SUPPORTED_TOOLS),
        help="Tools to run in serial order. Default: semrush similarweb",
    )
    parser.add_argument("--session-prefix", default="dvos-capture", help="Base session prefix for serial tool runs")
    parser.add_argument("--output", help="Write JSON to a file")
    parser.add_argument("--request-id", default="", help="Optional caller request id for downstream scale/skill tracing")
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

    data = run_capture_plan(
        query=args.query,
        username=args.username,
        password=args.password,
        tools=args.tools,
        session_prefix=args.session_prefix,
        keep_session=args.keep_session,
        max_node_rotations=args.max_node_rotations,
        continue_on_error=args.continue_on_error,
        request_id=args.request_id,
    )
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 0 if data["summary"]["all_succeeded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
