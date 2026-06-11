#!/usr/bin/env python3
"""Shared playbook builders over demand-validation workflow outputs."""

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


def compact_text_list(values: list[Any], limit: int = 5) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                result.append(text)
        elif isinstance(value, dict):
            parts = [str(item).strip() for item in value.values() if str(item).strip()]
            if parts:
                result.append(" | ".join(parts[:3]))
        if len(result) >= limit:
            break
    return result


def build_demand_playbook(workflow: dict[str, Any]) -> dict[str, Any]:
    report = workflow.get("report") or {}
    decision = workflow.get("decision") or {}
    derived = workflow.get("derived") or {}
    page_artifacts = get_path(workflow, "artifacts", "page_artifacts", default={}) or {}
    first_pages = report.get("first_batch_of_pages") or []
    page_titles = [
        page.get("working_title") or page.get("primary_keyword") or ""
        for page in first_pages
        if isinstance(page, dict) and (page.get("working_title") or page.get("primary_keyword"))
    ]
    artifact_slugs = [
        page.get("slug")
        for page in (page_artifacts.get("pages") or [])
        if isinstance(page, dict) and page.get("slug")
    ]
    return {
        "mode": "demand",
        "goal": "新词 / 新需求验证",
        "decision": {
            "recommended_action": decision.get("recommended_action"),
            "band": decision.get("band"),
            "total_score": decision.get("total_score"),
            "all_hard_gates_passed": decision.get("all_hard_gates_passed"),
        },
        "why_now": report.get("core_conclusion") or "",
        "evidence_chain": [
            report.get("demand_reality") or "",
            report.get("search_proof") or "",
            report.get("trend_pattern") or "",
            report.get("page_type_recommendation") or "",
        ],
        "launch_plan": {
            "primary_page_type": report.get("page_type_recommendation") or "",
            "first_batch_titles": page_titles,
            "page_artifact_count": page_artifacts.get("page_count") or 0,
            "artifact_slugs": artifact_slugs,
        },
        "execution_checks": [
            derived.get("page_signal_summary") or "",
            derived.get("keyword_signal_summary") or "",
            derived.get("cluster_summary") or "",
            derived.get("monetization_summary") or "",
        ],
        "next_actions": [
            "先做首批页面里意图最清晰的一页。",
            "用 page artifacts / frontend payload 直接生成首版页面 JSON。",
            "回看 Similarweb landing pages 与 Semrush top pages，验证是否需要扩成 cluster。",
        ],
        "main_uncertainty": report.get("main_uncertainty") or "",
    }


def build_attribution_playbook(workflow: dict[str, Any]) -> dict[str, Any]:
    report = workflow.get("report") or {}
    decision = workflow.get("decision") or {}
    derived = workflow.get("derived") or {}
    return {
        "mode": "attribution",
        "goal": "榜单归因",
        "decision": {
            "recommended_action": decision.get("recommended_action"),
            "band": decision.get("band"),
            "total_score": decision.get("total_score"),
            "all_hard_gates_passed": decision.get("all_hard_gates_passed"),
        },
        "core_judgment": report.get("core_conclusion") or "",
        "growth_map": {
            "main_growth_pages": compact_text_list(report.get("main_growth_pages") or []),
            "main_growth_terms": compact_text_list([report.get("main_growth_terms") or ""]),
            "page_signal_summary": derived.get("page_signal_summary") or "",
            "keyword_signal_summary": derived.get("keyword_signal_summary") or "",
        },
        "replication_play": {
            "likely_growth_action": report.get("likely_growth_action") or "",
            "reusable_part": report.get("reusable_part") or "",
            "do_not_copy": report.get("do_not_copy") or "",
        },
        "execution_checks": [
            derived.get("time_window_summary") or "",
            derived.get("cluster_summary") or "",
            report.get("confidence_and_gaps") or "",
        ],
        "next_actions": [
            "先挑一个可复用页面型，而不是笼统复制整站。",
            "把可复用 term cluster 收束成更窄的页面切入。",
            "下一轮用 Similarweb / Semrush 对目标页面型做更深一层 capture。",
        ],
    }


def build_playbook(workflow: dict[str, Any]) -> dict[str, Any]:
    mode = workflow.get("mode")
    if mode == "attribution":
        return build_attribution_playbook(workflow)
    return build_demand_playbook(workflow)

