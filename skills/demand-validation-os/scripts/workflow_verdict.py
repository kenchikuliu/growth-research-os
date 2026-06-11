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


def compact_non_empty(values: list[Any], limit: int = 5) -> list[str]:
    rows: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        rows.append(text)
        if len(rows) >= limit:
            break
    return rows


def build_business_snapshot(workflow: dict[str, Any], scale_output: dict[str, Any]) -> dict[str, Any]:
    mode = scale_output.get("mode") or workflow.get("mode") or "demand"
    report = workflow.get("report") or {}
    derived = workflow.get("derived") or {}
    page_artifact_input = get_path(workflow, "verdict_outputs", "page_artifact_input", default={}) or {}
    keyword_verdict = workflow.get("keyword_verdict") or {}
    if mode == "attribution":
        return {
            "use_case": "leaderboard_attribution",
            "operator_question": "这个站到底为什么涨，哪些部分值得复用？",
            "one_line_answer": report.get("core_conclusion") or keyword_verdict.get("summary") or "",
            "decision_ready_for": [
                "榜单归因周报",
                "竞品拆解会",
                "下一轮页面复制判断",
            ],
            "must_watch": compact_non_empty(
                [
                    report.get("main_growth_pages_text"),
                    report.get("main_growth_terms_text"),
                    derived.get("time_window_summary"),
                ],
                limit=3,
            ),
            "do_next": compact_non_empty(
                [
                    report.get("reusable_part"),
                    report.get("do_not_copy"),
                    report.get("likely_growth_action"),
                ],
                limit=3,
            ),
        }
    return {
        "use_case": "new_keyword_validation",
        "operator_question": "这个词/需求值不值得做，先做什么页面？",
        "one_line_answer": report.get("core_conclusion") or keyword_verdict.get("summary") or "",
        "decision_ready_for": [
            "新词评审",
            "建站/扩页优先级判断",
            "替代页与工具页规划",
        ],
        "must_watch": compact_non_empty(
            [
                report.get("search_proof"),
                report.get("trend_pattern"),
                report.get("page_type_recommendation"),
            ],
            limit=3,
        ),
        "do_next": compact_non_empty(
            [
                report.get("recommended_action"),
                derived.get("cluster_summary"),
                page_artifact_input.get("target_path"),
            ],
            limit=3,
        ),
    }


def build_business_template(workflow: dict[str, Any], scale_output: dict[str, Any], page_artifacts: dict[str, Any]) -> dict[str, Any]:
    mode = scale_output.get("mode") or workflow.get("mode") or "demand"
    report = workflow.get("report") or {}
    verdict = workflow.get("keyword_verdict") or {}
    page_input = build_page_artifact_input(workflow, page_artifacts)
    if mode == "attribution":
        return {
            "template_type": "attribution_business_result",
            "headline": report.get("core_conclusion") or verdict.get("summary") or "",
            "sections": [
                {"id": "core_conclusion", "label": "Core conclusion", "value": report.get("core_conclusion") or ""},
                {"id": "main_growth_pages", "label": "Main growth pages", "value": report.get("main_growth_pages") or []},
                {"id": "main_growth_terms", "label": "Main growth terms", "value": report.get("main_growth_terms") or ""},
                {"id": "likely_growth_action", "label": "Likely growth action", "value": report.get("likely_growth_action") or ""},
                {"id": "reusable_part", "label": "Reusable part", "value": report.get("reusable_part") or ""},
                {"id": "do_not_copy", "label": "Do not copy", "value": report.get("do_not_copy") or ""},
                {"id": "confidence_and_gaps", "label": "Confidence and gaps", "value": report.get("confidence_and_gaps") or ""},
            ],
            "render_hints": {
                "preferred_surface": "weekly_attribution_board",
                "table_ready": True,
                "artifact_dependency": False,
            },
        }
    return {
        "template_type": "demand_validation_business_result",
        "headline": report.get("core_conclusion") or verdict.get("summary") or "",
        "sections": [
            {"id": "core_conclusion", "label": "Core conclusion", "value": report.get("core_conclusion") or ""},
            {"id": "demand_reality", "label": "Demand reality", "value": report.get("demand_reality") or ""},
            {"id": "search_proof", "label": "Search proof", "value": report.get("search_proof") or ""},
            {"id": "trend_pattern", "label": "Trend pattern", "value": report.get("trend_pattern") or ""},
            {"id": "page_type_recommendation", "label": "Page-type recommendation", "value": report.get("page_type_recommendation") or ""},
            {"id": "recommended_action", "label": "Recommended action", "value": report.get("recommended_action") or ""},
            {"id": "first_batch_of_pages", "label": "First batch of pages", "value": report.get("first_batch_of_pages") or []},
            {"id": "main_uncertainty", "label": "Main uncertainty", "value": report.get("main_uncertainty") or ""},
        ],
        "render_hints": {
            "preferred_surface": "new-demand-review_board",
            "table_ready": True,
            "artifact_dependency": bool(page_input.get("template")),
        },
    }


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
    business_snapshot = build_business_snapshot(workflow, scale_output)
    business_template = build_business_template(workflow, scale_output, page_artifacts)
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
        "business_snapshot": business_snapshot,
        "business_template": business_template,
        "execution_payload": build_page_artifact_input(workflow, page_artifacts),
        "main_uncertainty": verdict.get("main_uncertainty") or "",
    }
