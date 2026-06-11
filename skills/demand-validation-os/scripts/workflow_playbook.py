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


def demand_template(workflow: dict[str, Any]) -> dict[str, Any]:
    report = workflow.get("report") or {}
    derived = workflow.get("derived") or {}
    first_pages = report.get("first_batch_of_pages") or []
    return {
        "template_type": "new_demand_launch_play",
        "goal": "把一个新词 / 新需求从验证推进到首批页面执行",
        "stages": [
            {
                "id": "reality_check",
                "title": "需求真实性",
                "question": "它到底是真需求，还是讨论热度？",
                "signals": [
                    report.get("demand_reality") or "",
                    report.get("search_proof") or "",
                ],
                "done_when": "至少能讲清真实痛点、搜索承接和页面证据三者之间的关系。",
            },
            {
                "id": "page_shape",
                "title": "页面形态",
                "question": "用户到底要什么页面？",
                "signals": [
                    report.get("page_type_recommendation") or "",
                    derived.get("page_signal_summary") or "",
                ],
                "done_when": "已经确定首批主页面类型，而不是只停留在关键词列表。",
            },
            {
                "id": "cluster_scope",
                "title": "扩张边界",
                "question": "它是一页机会，还是 cluster / site 机会？",
                "signals": [
                    report.get("recommended_action") or "",
                    derived.get("cluster_summary") or "",
                ],
                "done_when": "已经把 stop / watch / one-page / cluster / site 的动作边界写清楚。",
            },
            {
                "id": "launch_batch",
                "title": "首批执行",
                "question": "第一批先交付哪些页面？",
                "signals": compact_text_list(first_pages, limit=5),
                "done_when": "至少有一页能直接进页面制作，而不是继续停留在分析。",
            },
        ],
        "required_inputs": [
            "核心 query / demand statement",
            "Similarweb landing pages or page-level evidence",
            "Semrush top pages / top keywords",
            "Google Trends shape",
            "gefei + chuhai judgment rules",
        ],
        "handoff_outputs": [
            "recommended_action",
            "first_batch_of_pages",
            "page_artifacts",
            "publishable_pages",
        ],
    }


def attribution_template(workflow: dict[str, Any]) -> dict[str, Any]:
    report = workflow.get("report") or {}
    derived = workflow.get("derived") or {}
    return {
        "template_type": "leaderboard_attribution_play",
        "goal": "把榜单站点增长拆成可归因、可复用、可复制的打法",
        "stages": [
            {
                "id": "window_lock",
                "title": "时间窗口",
                "question": "增长发生在什么窗口？",
                "signals": [
                    derived.get("time_window_summary") or "",
                    report.get("confidence_and_gaps") or "",
                ],
                "done_when": "已经避免把旧流量盘和新增长混在一起。",
            },
            {
                "id": "page_change",
                "title": "页面变化",
                "question": "到底是哪些页面在动？",
                "signals": compact_text_list(report.get("main_growth_pages") or [], limit=5),
                "done_when": "能明确说出增长不是平均抬升，而是集中在某些页面型。",
            },
            {
                "id": "term_to_page",
                "title": "词页闭环",
                "question": "哪些 term / page type 在驱动变化？",
                "signals": [
                    report.get("main_growth_terms") or "",
                    derived.get("keyword_signal_summary") or "",
                ],
                "done_when": "已经建立 term -> page -> action 的闭环，而不是只看总流量。",
            },
            {
                "id": "replication_cut",
                "title": "复制边界",
                "question": "哪些部分可复用，哪些绝对不要抄？",
                "signals": [
                    report.get("reusable_part") or "",
                    report.get("do_not_copy") or "",
                ],
                "done_when": "下一轮可以直接拿一个更窄的页面切入执行。",
            },
        ],
        "required_inputs": [
            "目标域名或榜单站点",
            "Semrush top pages / top keywords",
            "Similarweb page-level signals",
            "Google Trends window alignment",
        ],
        "handoff_outputs": [
            "likely_growth_action",
            "reusable_part",
            "do_not_copy",
            "replication_next_actions",
        ],
    }


def demand_template_actions(workflow: dict[str, Any]) -> list[dict[str, str]]:
    report = workflow.get("report") or {}
    derived = workflow.get("derived") or {}
    return [
        {
            "step": "先定主承接页",
            "why": report.get("page_type_recommendation") or "",
            "deliverable": "确定一页最先上线的主页面类型。",
        },
        {
            "step": "先做一页可验证页面",
            "why": report.get("recommended_action") or "",
            "deliverable": "拿首批页面里的第一优先级页出首版。",
        },
        {
            "step": "再看要不要扩 cluster",
            "why": derived.get("cluster_summary") or "",
            "deliverable": "确认是只做一页，还是扩到对比页 / 模板页 / FAQ。",
        },
    ]


def attribution_template_actions(workflow: dict[str, Any]) -> list[dict[str, str]]:
    report = workflow.get("report") or {}
    derived = workflow.get("derived") or {}
    return [
        {
            "step": "先挑一个页面型复用",
            "why": report.get("reusable_part") or "",
            "deliverable": "不要泛化整站策略，先缩成一个页面型。",
        },
        {
            "step": "把词页关系缩窄",
            "why": derived.get("keyword_signal_summary") or "",
            "deliverable": "把 term cluster 缩成一个更窄的执行切口。",
        },
        {
            "step": "下一轮补更深 capture",
            "why": report.get("confidence_and_gaps") or "",
            "deliverable": "补深层 page-level rows，判断复制是否足够稳。",
        },
    ]


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
        "playbook_template": demand_template(workflow),
        "template_actions": demand_template_actions(workflow),
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
        "playbook_template": attribution_template(workflow),
        "template_actions": attribution_template_actions(workflow),
    }


def build_playbook(workflow: dict[str, Any]) -> dict[str, Any]:
    mode = workflow.get("mode")
    if mode == "attribution":
        return build_attribution_playbook(workflow)
    return build_demand_playbook(workflow)

