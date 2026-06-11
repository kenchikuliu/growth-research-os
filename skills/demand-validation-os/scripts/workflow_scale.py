#!/usr/bin/env python3
"""Shared thin scale-output helpers for workflow consumers."""

from __future__ import annotations

from typing import Any


def parse_csv_set(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in str(value).split(",") if item.strip()}


def normalize_sort_value(value: Any) -> tuple[int, Any]:
    if value is None or value == "":
        return (1, "")
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, (int, float)):
        return (0, value)
    return (0, str(value).lower())


def build_scale_output(workflow: dict[str, Any]) -> dict[str, Any]:
    report = workflow.get("report") or {}
    decision = workflow.get("decision") or {}
    artifacts = (workflow.get("artifacts") or {}).get("page_artifacts") or {}
    normalized = ((workflow.get("evidence") or {}).get("tool_capture") or {}).get("normalized") or {}
    verdict = workflow.get("keyword_verdict") or {}
    return {
        "mode": workflow.get("mode"),
        "query": (workflow.get("input") or {}).get("query"),
        "domain": (workflow.get("input") or {}).get("domain"),
        "decision": {
            "band": decision.get("band"),
            "recommended_action": decision.get("recommended_action"),
            "total_score": decision.get("total_score"),
            "all_hard_gates_passed": decision.get("all_hard_gates_passed"),
        },
        "direct_answer": {
            "core_conclusion": report.get("core_conclusion"),
            "recommended_action": report.get("recommended_action") or decision.get("recommended_action"),
            "page_type_recommendation": report.get("page_type_recommendation"),
            "main_growth_terms": report.get("main_growth_terms"),
            "main_growth_pages": report.get("main_growth_pages"),
        },
        "page_plan": {
            "first_batch_of_pages": report.get("first_batch_of_pages") or [],
            "page_artifact_count": artifacts.get("page_count", 0),
            "artifacts_available": bool(artifacts.get("available")),
        },
        "keyword_verdict": {
            "summary": verdict.get("summary"),
            "primary_recommendation": verdict.get("primary_recommendation"),
            "page_type": verdict.get("page_type"),
            "kd_bucket": get_path(verdict, "kd", "bucket", default=""),
            "tools_ready": verdict.get("tools_ready") or [],
            "first_moves": verdict.get("first_moves") or [],
            "main_uncertainty": verdict.get("main_uncertainty") or "",
        },
        "normalized_snapshot": {
            "tools_ready": normalized.get("tools_ready") or [],
            "coverage": normalized.get("coverage") or {},
            "traffic_summary": normalized.get("traffic_summary") or {},
            "top_page_count": len(normalized.get("top_pages") or []),
            "top_keyword_count": len(normalized.get("top_keywords") or []),
            "landing_page_count": len(normalized.get("landing_pages") or []),
            "page_cluster_count": len(normalized.get("page_clusters") or []),
        },
        "artifacts": artifacts,
    }


def get_path(data: Any, *path: Any, default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
        if current is None:
            return default
    return current


def passes_filters(
    scale_output: dict[str, Any],
    *,
    min_score: int | None = None,
    allowed_actions: set[str] | None = None,
    require_tools_ready: set[str] | None = None,
) -> bool:
    decision = scale_output.get("decision") or {}
    snapshot = scale_output.get("normalized_snapshot") or {}
    score = decision.get("total_score")
    if min_score is not None and isinstance(score, (int, float)) and score < min_score:
        return False
    if min_score is not None and not isinstance(score, (int, float)):
        return False
    if allowed_actions and (decision.get("recommended_action") not in allowed_actions):
        return False
    if require_tools_ready:
        tools_ready = set(snapshot.get("tools_ready") or [])
        if not require_tools_ready.issubset(tools_ready):
            return False
    return True


def sort_scale_rows(rows: list[dict[str, Any]], *, sort_by: str = "total_score", descending: bool = True) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: normalize_sort_value(row.get(sort_by)),
        reverse=descending,
    )


def rank_filtered_pairs(
    result_rows: list[dict[str, Any]],
    flat_rows: list[dict[str, Any]],
    *,
    min_score: int | None = None,
    allowed_actions: set[str] | None = None,
    require_tools_ready: set[str] | None = None,
    sort_by: str = "total_score",
    ascending: bool = False,
    top: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    filtered_pairs = [
        (result_row, flat_row)
        for result_row, flat_row in zip(result_rows, flat_rows)
        if passes_filters(
            (result_row.get("scale_output") or {}),
            min_score=min_score,
            allowed_actions=allowed_actions or None,
            require_tools_ready=require_tools_ready or None,
        )
    ]
    filtered_flat_rows = [pair[1] for pair in filtered_pairs]
    sorted_flat_rows = sort_scale_rows(filtered_flat_rows, sort_by=sort_by, descending=not ascending)
    order = {id(row): idx for idx, row in enumerate(sorted_flat_rows)}
    filtered_pairs = sorted(filtered_pairs, key=lambda pair: order[id(pair[1])])
    if top:
        filtered_pairs = filtered_pairs[:top]
    return [pair[0] for pair in filtered_pairs], [pair[1] for pair in filtered_pairs]
