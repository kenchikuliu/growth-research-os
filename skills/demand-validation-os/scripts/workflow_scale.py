#!/usr/bin/env python3
"""Shared thin scale-output helpers for workflow consumers."""

from __future__ import annotations

from typing import Any


def build_scale_output(workflow: dict[str, Any]) -> dict[str, Any]:
    report = workflow.get("report") or {}
    decision = workflow.get("decision") or {}
    artifacts = (workflow.get("artifacts") or {}).get("page_artifacts") or {}
    normalized = ((workflow.get("evidence") or {}).get("tool_capture") or {}).get("normalized") or {}
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

