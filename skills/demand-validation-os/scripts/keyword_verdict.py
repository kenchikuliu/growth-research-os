#!/usr/bin/env python3
"""Build one shared keyword-verdict layer for demand-validation workflow consumers."""

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
    items: list[str] = []
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                items.append(text)
        elif isinstance(value, dict):
            title = value.get("working_title") or value.get("primary_keyword") or value.get("title")
            if title:
                items.append(str(title).strip())
        if len(items) >= limit:
            break
    return items


def score_map(workflow: dict[str, Any]) -> dict[str, int]:
    rows = get_path(workflow, "scores", "raw_scores", default={}) or {}
    return {str(key): int(value) for key, value in rows.items() if isinstance(value, int)}


def score_reasons(workflow: dict[str, Any]) -> dict[str, list[str]]:
    rows = get_path(workflow, "scores", "reasoning", default={}) or {}
    result: dict[str, list[str]] = {}
    for key, values in rows.items():
        if isinstance(values, list):
            result[str(key)] = [str(item).strip() for item in values if str(item).strip()]
    return result


def demand_stage_verdict(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    raw_scores = score_map(workflow)
    reasons = score_reasons(workflow)
    report = workflow.get("report") or {}
    derived = workflow.get("derived") or {}
    decision = workflow.get("decision") or {}
    kd = get_path(workflow, "evidence", "web_cafe_kd", default={}) or {}
    return [
        {
            "id": "demand_reality",
            "question": "这个需求真实吗？",
            "score": raw_scores.get("demand_reality"),
            "status": "pass" if (raw_scores.get("demand_reality") or 0) >= 3 else "weak",
            "answer": report.get("demand_reality") or "",
            "evidence": reasons.get("demand_reality", []),
        },
        {
            "id": "search_carry",
            "question": "它是不是被搜索承接？",
            "score": raw_scores.get("search_carry"),
            "status": "pass" if (raw_scores.get("search_carry") or 0) >= 3 else "weak",
            "answer": report.get("search_proof") or derived.get("keyword_signal_summary") or "",
            "evidence": reasons.get("search_carry", []),
        },
        {
            "id": "entry_shape",
            "question": "应该先用什么页面切进去？",
            "score": raw_scores.get("page_intent_fit"),
            "status": "pass" if (raw_scores.get("page_intent_fit") or 0) >= 3 else "weak",
            "answer": report.get("page_type_recommendation") or "",
            "evidence": reasons.get("page_intent_fit", []) + reasons.get("serp_entry", []),
        },
        {
            "id": "expansion",
            "question": "它能不能扩成 cluster 或 site？",
            "score": raw_scores.get("clusterability"),
            "status": "pass" if (raw_scores.get("clusterability") or 0) >= 3 else "weak",
            "answer": derived.get("cluster_summary") or "",
            "evidence": reasons.get("clusterability", []),
        },
        {
            "id": "difficulty_cut",
            "question": "应该直接打主词，还是先缩窄切口？",
            "score": raw_scores.get("serp_entry"),
            "status": "pass" if (raw_scores.get("serp_entry") or 0) >= 3 else "weak",
            "answer": kd.get("guidance") or "当前没有稳定 KD 提示。",
            "evidence": [f"KD bucket: {kd.get('kd_bucket') or 'unknown'}"] + reasons.get("serp_entry", []),
        },
        {
            "id": "action",
            "question": "现在最应该做什么？",
            "score": None,
            "status": "pass" if decision.get("all_hard_gates_passed") else "weak",
            "answer": report.get("recommended_action") or decision.get("recommended_action") or "",
            "evidence": [
                report.get("core_conclusion") or "",
                derived.get("monetization_summary") or "",
                get_path(workflow, "derived", "kd_summary", default="") or "",
            ],
        },
    ]


def attribution_stage_verdict(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    raw_scores = score_map(workflow)
    reasons = score_reasons(workflow)
    report = workflow.get("report") or {}
    derived = workflow.get("derived") or {}
    decision = workflow.get("decision") or {}
    return [
        {
            "id": "page_change",
            "question": "到底是哪些页面在变？",
            "score": raw_scores.get("page_change_clarity"),
            "status": "pass" if (raw_scores.get("page_change_clarity") or 0) >= 3 else "weak",
            "answer": report.get("main_growth_pages_text") or derived.get("page_signal_summary") or "",
            "evidence": reasons.get("page_change_clarity", []),
        },
        {
            "id": "term_driver",
            "question": "哪些词和页面型在驱动增长？",
            "score": raw_scores.get("keyword_change_confidence"),
            "status": "pass" if (raw_scores.get("keyword_change_confidence") or 0) >= 3 else "weak",
            "answer": report.get("main_growth_terms_text") or derived.get("keyword_signal_summary") or "",
            "evidence": reasons.get("keyword_change_confidence", []),
        },
        {
            "id": "window_alignment",
            "question": "时间窗口对得上吗？",
            "score": raw_scores.get("time_window_alignment"),
            "status": "pass" if (raw_scores.get("time_window_alignment") or 0) >= 3 else "weak",
            "answer": derived.get("time_window_summary") or "",
            "evidence": reasons.get("time_window_alignment", []),
        },
        {
            "id": "replication",
            "question": "哪些部分值得复用？",
            "score": raw_scores.get("chain_closure"),
            "status": "pass" if (raw_scores.get("chain_closure") or 0) >= 3 else "weak",
            "answer": report.get("reusable_part") or "",
            "evidence": reasons.get("chain_closure", []),
        },
        {
            "id": "action",
            "question": "下一步该怎么复制？",
            "score": None,
            "status": "pass" if decision.get("all_hard_gates_passed") else "weak",
            "answer": report.get("likely_growth_action") or decision.get("recommended_action") or "",
            "evidence": [
                report.get("core_conclusion") or "",
                report.get("do_not_copy") or "",
                report.get("confidence_and_gaps") or "",
            ],
        },
    ]


def build_keyword_verdict(workflow: dict[str, Any]) -> dict[str, Any]:
    mode = workflow.get("mode") or "demand"
    report = workflow.get("report") or {}
    decision = workflow.get("decision") or {}
    first_pages = report.get("first_batch_of_pages") or []
    kd = get_path(workflow, "evidence", "web_cafe_kd", default={}) or {}
    normalized = get_path(workflow, "evidence", "tool_capture", "normalized", default={}) or {}
    tools_ready = normalized.get("tools_ready") or []

    if mode == "attribution":
        verdict_type = "leaderboard_attribution"
        stages = attribution_stage_verdict(workflow)
        summary = report.get("core_conclusion") or ""
        primary_recommendation = report.get("likely_growth_action") or decision.get("recommended_action") or ""
        first_moves = [
            report.get("reusable_part") or "",
            report.get("do_not_copy") or "",
            "先挑一个可复用页面型，而不是笼统复制整站。",
        ]
    else:
        verdict_type = "new_keyword_validation"
        stages = demand_stage_verdict(workflow)
        summary = report.get("core_conclusion") or ""
        primary_recommendation = report.get("recommended_action") or decision.get("recommended_action") or ""
        first_moves = [
            f"优先页面型：{report.get('page_type_recommendation') or '待补充'}",
            f"首批页面：{', '.join(compact_text_list(first_pages, limit=3)) or '待补充'}",
            get_path(workflow, "derived", "kd_summary", default="") or "",
        ]

    return {
        "type": verdict_type,
        "query": get_path(workflow, "input", "query", default=""),
        "domain": get_path(workflow, "input", "domain", default=""),
        "summary": summary,
        "primary_recommendation": primary_recommendation,
        "band": decision.get("band"),
        "total_score": decision.get("total_score"),
        "all_hard_gates_passed": decision.get("all_hard_gates_passed"),
        "page_type": report.get("page_type_recommendation") or get_path(workflow, "inferences", "page_type", default=""),
        "kd": {
            "available": kd.get("available"),
            "score": kd.get("kd_score"),
            "bucket": kd.get("kd_bucket"),
            "guidance": kd.get("guidance"),
            "source_mode": get_path(kd, "source", "mode", default=""),
        },
        "tools_ready": tools_ready,
        "first_batch_titles": compact_text_list(first_pages, limit=5),
        "stage_verdicts": stages,
        "first_moves": [item for item in first_moves if item],
        "main_uncertainty": report.get("main_uncertainty") or report.get("confidence_and_gaps") or "",
    }

