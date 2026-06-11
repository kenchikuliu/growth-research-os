#!/usr/bin/env python3
"""Higher-level verdict builders over workflow, keyword verdict, and page artifacts."""

from __future__ import annotations

from typing import Any


def get_path(data: Any, *path: Any, default: Any = None) -> Any:
    current: Any = data
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


def compact_titles(values: list[Any], limit: int = 5) -> list[str]:
    rows: list[str] = []
    for value in values:
        if isinstance(value, dict):
            title = value.get("working_title") or value.get("primary_keyword") or value.get("title")
            if title:
                rows.append(str(title).strip())
        elif isinstance(value, str) and value.strip():
            rows.append(value.strip())
        if len(rows) >= limit:
            break
    return rows


def build_page_artifact_input(workflow: dict[str, Any], page_artifacts: dict[str, Any]) -> dict[str, Any]:
    verdict = workflow.get("keyword_verdict") or {}
    pages = page_artifacts.get("publishable_pages") or []
    first_publishable = pages[0] if pages and isinstance(pages[0], dict) else {}
    return {
        "query": get_path(workflow, "input", "query", default=""),
        "primary_recommendation": verdict.get("primary_recommendation") or "",
        "summary": verdict.get("summary") or "",
        "page_type": verdict.get("page_type") or "",
        "first_batch_titles": verdict.get("first_batch_titles") or compact_titles(get_path(workflow, "report", "first_batch_of_pages", default=[])),
        "hero_angle": get_path(first_publishable, "hero", "headline", default="") or get_path(first_publishable, "hero", "subheadline", default=""),
        "cta_label": get_path(first_publishable, "hero", "primary_cta", "label", default=""),
        "proof_points": get_path(first_publishable, "hero", "supporting_proof", default=[]),
        "template": first_publishable.get("template") or "",
        "target_path": first_publishable.get("path") or "",
        "section_types": [section.get("type") for section in (first_publishable.get("sections") or []) if isinstance(section, dict) and section.get("type")],
    }


def build_high_level_scale_verdict(workflow: dict[str, Any], scale_output: dict[str, Any], page_artifacts: dict[str, Any]) -> dict[str, Any]:
    verdict = workflow.get("keyword_verdict") or {}
    decision = scale_output.get("decision") or {}
    normalized = scale_output.get("normalized_snapshot") or {}
    return {
        "query": scale_output.get("query") or "",
        "domain": scale_output.get("domain") or "",
        "mode": scale_output.get("mode") or workflow.get("mode"),
        "verdict_type": verdict.get("type") or "",
        "summary": verdict.get("summary") or "",
        "action": verdict.get("primary_recommendation") or decision.get("recommended_action") or "",
        "band": verdict.get("band") or decision.get("band") or "",
        "confidence": {
            "total_score": verdict.get("total_score") or decision.get("total_score"),
            "all_hard_gates_passed": verdict.get("all_hard_gates_passed"),
            "tools_ready": verdict.get("tools_ready") or normalized.get("tools_ready") or [],
        },
        "entry_strategy": {
            "page_type": verdict.get("page_type") or "",
            "first_moves": verdict.get("first_moves") or [],
            "kd_bucket": get_path(verdict, "kd", "bucket", default=""),
            "kd_guidance": get_path(verdict, "kd", "guidance", default=""),
        },
        "execution_payload": build_page_artifact_input(workflow, page_artifacts),
        "main_uncertainty": verdict.get("main_uncertainty") or "",
    }

