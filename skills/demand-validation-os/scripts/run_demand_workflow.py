#!/usr/bin/env python3
"""One-click orchestrator for demand-validation-os."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import capture_api
import capture_bundle
import google_trends
import guided_flow
import page_artifacts
import scorecard as scorecard_module
import web_cafe_kd
import workflow_playbook
from browser_capture import iso_utc_now


GEFEI_SCRIPT = "/Users/Yuki/.codex/skills/gefei/scripts/gefei.py"
CHUHAI_SCRIPT = "/Users/Yuki/.codex/skills/chuhai/scripts/chuhai.py"


def looks_like_domain(value: str) -> bool:
    return bool(re.fullmatch(r"(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}", value.strip().lower()))


def run_text_command(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return (proc.stdout + "\n" + proc.stderr).strip()
    return proc.stdout.strip()


def summarize_text(text: str, limit: int = 6) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines[:limit])


def query_page_type(query: str) -> str:
    lowered = query.lower()
    if any(token in lowered for token in [" vs ", "versus", "alternative", "compare", "comparison"]):
        return "comparison"
    if any(token in lowered for token in ["template", "examples", "sample"]):
        return "template"
    if any(token in lowered for token in ["generator", "converter", "calculator", "checker", "tool", "editor"]):
        return "tool"
    if any(token in lowered for token in ["how ", "what ", "why ", "guide", "tutorial"]):
        return "content"
    return "content"


def page_type_label(page_type: str) -> str:
    return {
        "tool": "工具页",
        "comparison": "对比页",
        "template": "模板页",
        "content": "内容页",
    }.get(page_type, "内容页")


def unwrap_capture_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict) and payload["data"].get("results"):
        data = payload["data"]
    return data if isinstance(data, dict) else {}


def read_normalized_capture(bundle: dict[str, Any]) -> dict[str, Any]:
    return (unwrap_capture_bundle(bundle).get("normalized") or {}) if isinstance(bundle, dict) else {}


def normalized_rows(
    bundle: dict[str, Any],
    key: str,
    *,
    source_tool: str | None = None,
    cluster_type: str | None = None,
    landing_type: str | None = None,
) -> list[dict[str, Any]]:
    rows = read_normalized_capture(bundle).get(key) or []
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if source_tool and row.get("source_tool") != source_tool:
            continue
        if cluster_type and row.get("cluster_type") != cluster_type:
            continue
        if landing_type and row.get("landing_type") != landing_type:
            continue
        normalized.append(row)
    return normalized


def read_top_pages(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = normalized_rows(bundle, "top_pages", source_tool="semrush")
    if rows:
        return [
            {
                "title": row.get("title"),
                "url": row.get("url"),
                "top_keyword": row.get("top_keyword"),
                "traffic": row.get("traffic_estimate"),
                "traffic_percent": row.get("traffic_share_percent"),
                "position": row.get("position"),
                "volume": row.get("keyword_volume"),
            }
            for row in rows
        ]
    return (((unwrap_capture_bundle(bundle).get("results") or {}).get("semrush") or {}).get("data") or {}).get("top_pages") or []


def read_top_keywords(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = normalized_rows(bundle, "top_keywords", source_tool="semrush")
    if rows:
        return [
            {
                "keyword": row.get("keyword"),
                "position": row.get("position"),
                "position_difference": row.get("position_change"),
                "volume": row.get("volume"),
                "traffic": row.get("traffic_estimate"),
                "traffic_percent": row.get("traffic_share_percent"),
                "keyword_difficulty": row.get("keyword_difficulty"),
                "url": row.get("url"),
            }
            for row in rows
        ]
    return (((unwrap_capture_bundle(bundle).get("results") or {}).get("semrush") or {}).get("data") or {}).get("top_organic_keywords") or []


def read_similarweb_website(bundle: dict[str, Any]) -> dict[str, Any]:
    raw = (((unwrap_capture_bundle(bundle).get("results") or {}).get("similarweb") or {}).get("data") or {}).get("website_evidence") or {}
    if raw:
        return raw
    normalized = read_normalized_capture(bundle)
    similarweb_signals = (normalized.get("tool_signals") or {}).get("similarweb") or {}
    return {
        "website_performance": {
            "available": bool(similarweb_signals.get("website_performance_ready")),
        },
        "home_signals": {
            "priority_alerts": [{} for _ in range(int(similarweb_signals.get("priority_alert_count") or 0))]
        },
    }


def similarweb_folder_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = normalized_rows(bundle, "page_clusters", source_tool="similarweb", cluster_type="folder")
    if rows:
        return [
            {
                "folder": row.get("label"),
                "share": row.get("traffic_share_percent"),
                "month_over_month_change": row.get("traffic_change_pp"),
            }
            for row in rows
        ]
    return (((read_similarweb_website(bundle).get("website_content") or {}).get("summary") or {}).get("rows") or [])


def similarweb_non_brand_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = normalized_rows(bundle, "top_keywords", source_tool="similarweb")
    if rows:
        return [
            {
                "keyword": row.get("keyword"),
                "clicks": row.get("traffic_estimate"),
                "share": row.get("traffic_share_percent"),
                "organic_share": row.get("organic_share_percent"),
                "paid_share": row.get("paid_share_percent"),
            }
            for row in rows
        ]
    return (((read_similarweb_website(bundle).get("search_overview") or {}).get("top_non_brand_keywords") or {}).get("rows") or [])


def similarweb_paid_landing_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = normalized_rows(bundle, "landing_pages", source_tool="similarweb", landing_type="paid_landing_page")
    if rows:
        return [
            {
                "url": row.get("url"),
                "clicks": row.get("clicks_estimate"),
                "share": row.get("traffic_share_percent"),
                "top_keyword": row.get("top_keyword"),
                "new_keyword_count": row.get("new_keyword_count"),
            }
            for row in rows
        ]
    return (((read_similarweb_website(bundle).get("search_overview") or {}).get("paid_landing_pages") or {}).get("rows") or [])


def semrush_core_ready(bundle: dict[str, Any]) -> bool:
    core_ready = get_path(bundle, "summary", "core_ready_tools", default=[])
    return "semrush" in core_ready


def similarweb_core_ready(bundle: dict[str, Any]) -> bool:
    core_ready = get_path(bundle, "summary", "core_ready_tools", default=[])
    return "similarweb" in core_ready


def get_path(data: dict[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def knowledge_payload(mode: str, query: str) -> dict[str, Any]:
    gefei_prompt = (
        f"哥飞怎么判断 {query} 值不值得做，以及应该先做什么页面？"
        if mode == "demand"
        else f"哥飞会怎么归因 {query} 这种站点的增长，并判断哪些部分可复用？"
    )
    gefei_query = run_text_command(["python3", GEFEI_SCRIPT, "query", gefei_prompt])
    gefei_search = run_text_command(["python3", GEFEI_SCRIPT, "search", query])

    method_terms = ["Similarweb", "Semrush", "Google Trends", "主要页面", "着落页"]
    chuhai_focus = {}
    for term in method_terms:
        chuhai_focus[term] = run_text_command(["python3", CHUHAI_SCRIPT, "search", term])

    return {
        "gefei": {
            "prompt": gefei_prompt,
            "query_output": gefei_query,
            "search_output": gefei_search,
            "summary": summarize_text(gefei_query),
        },
        "chuhai": {
            "focus_methods": [summarize_text(chuhai_focus[term], limit=2) for term in ["Similarweb", "Semrush", "Google Trends"]],
            "method_highlights": [
                summarize_text(chuhai_focus["着落页"], limit=2),
                summarize_text(chuhai_focus["主要页面"], limit=2),
            ],
            "raw_outputs": chuhai_focus,
        },
    }


def build_method_alignment(
    *,
    mode: str,
    query: str,
    page_type: str,
    knowledge: dict[str, Any],
    trends: dict[str, Any],
    bundle: dict[str, Any],
    guided: dict[str, Any],
) -> dict[str, Any]:
    core_ready_tools = get_path(bundle, "summary", "core_ready_tools", default=[])
    return {
        "gefei": {
            "used": True,
            "entrypoint": GEFEI_SCRIPT,
            "role": "judgment_rules",
            "workflow_match": [
                "Use gefei query for broad judgment before expanding into execution.",
                "Keep page-list thinking ahead of raw keyword dumping.",
                "Treat knowledge output as rules, not as market evidence.",
            ],
            "signals_used": {
                "summary": get_path(knowledge, "gefei", "summary", default=""),
                "has_search_output": bool(get_path(knowledge, "gefei", "search_output", default="")),
            },
        },
        "chuhai": {
            "used": True,
            "entrypoint": CHUHAI_SCRIPT,
            "role": "operator_path",
            "workflow_match": [
                "Similarweb focuses on landing pages / validated click paths.",
                "Semrush focuses on top pages / top terms / cluster decomposition.",
                "Google Trends is used for shape, durability, geo, and wording shifts.",
            ],
            "signals_used": {
                "focus_methods": get_path(knowledge, "chuhai", "focus_methods", default=[]),
                "method_highlights": get_path(knowledge, "chuhai", "method_highlights", default=[]),
            },
        },
        "web_cafe_simulator": {
            "used": True,
            "reference_pages": [
                "https://new.web.cafe/seosimulator/gsc/",
                "https://new.web.cafe/seosimulator/",
                "https://new.web.cafe/search-simulator/",
            ],
            "role": "guided_product_shape",
            "pattern_coverage": {
                "gsc_simulator": {
                    "url": "https://new.web.cafe/seosimulator/gsc/",
                    "moves_reused": [
                        "contradiction-first landing copy",
                        "guided path vs direct simulator dual CTA",
                        "bounded step count instead of a flat article",
                        "event evidence before aggregated diagnosis",
                    ],
                },
                "seo_growth_simulator": {
                    "url": "https://new.web.cafe/seosimulator/",
                    "moves_reused": [
                        "phase-based workflow progression",
                        "action -> state change -> next decision chain",
                        "new site / new page execution framing instead of abstract SEO talk",
                    ],
                },
                "search_engine_simulator": {
                    "url": "https://new.web.cafe/search-simulator/",
                    "moves_reused": [
                        "one hidden mechanism per step",
                        "one concept per panel",
                        "input -> extraction -> scoring style causal decomposition",
                    ],
                },
            },
            "workflow_match": {
                "contradiction_first": bool(get_path(guided, "entry", "contradiction", default="")),
                "hidden_variable_named": bool(get_path(guided, "entry", "hidden_variable", default="")),
                "dual_entry_paths": bool(get_path(guided, "entry", "primary_cta", default=""))
                and bool(get_path(guided, "entry", "secondary_cta", default="")),
                "bounded_step_count": get_path(guided, "step_count", default=0),
                "expected_step_count": 8 if mode == "demand" else 6,
                "direct_result_surface": bool(guided.get("direct_result")),
            },
            "simulator_mapping": {
                "mode": mode,
                "query": query,
                "page_type": page_type,
                "trends_available": bool(trends.get("available")),
                "core_ready_tools": core_ready_tools,
            },
        },
    }


def capture_bundle_payload(
    *,
    domain: str | None,
    username: str,
    password: str,
    max_node_rotations: int,
    bundle_input: str | None = None,
    bundle_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if bundle_payload:
        return unwrap_capture_bundle(bundle_payload)
    if bundle_input:
        return unwrap_capture_bundle(json.loads(Path(bundle_input).read_text()))
    if not domain:
        return {
            "skipped": True,
            "reason": "no-domain-provided",
        }
    return capture_api.run_capture_plan(
        query=domain,
        username=username,
        password=password,
        tools=["semrush", "similarweb"],
        session_prefix="dvos-workflow",
        keep_session=False,
        max_node_rotations=max_node_rotations,
        continue_on_error=True,
        request_id="workflow-capture",
    )


def build_page_artifacts_payload(
    workflow: dict[str, Any],
    *,
    brand_name: str = "",
    brand_url: str = "",
    primary_cta_url: str = "",
    primary_cta_label: str = "",
) -> dict[str, Any]:
    context = page_artifacts.brand_context_payload(
        brand_name=brand_name,
        brand_url=brand_url,
        primary_cta_url=primary_cta_url,
        primary_cta_label=primary_cta_label,
    )
    return page_artifacts.build_page_artifacts(workflow, brand_context=context)


def trend_primary_shape(trends: dict[str, Any]) -> str:
    return get_path(trends, "summary", "primary_shape", default="unknown")


def top_rising_terms(trends: dict[str, Any], limit: int = 5) -> list[str]:
    rows = get_path(trends, "summary", "top_rising_queries", default=[])
    return [item.get("query") for item in rows[:limit] if item.get("query")]


def count_non_home_pages(top_pages: list[dict[str, Any]]) -> int:
    count = 0
    for row in top_pages:
        url = str(row.get("url") or "")
        path = url.split("://", 1)[-1].split("/", 1)
        if len(path) == 2 and path[1].strip("/"):
            count += 1
    return count


def classify_page_examples(top_pages: list[dict[str, Any]], limit: int = 5) -> list[str]:
    result = []
    for row in top_pages[:limit]:
        keyword = row.get("top_keyword")
        title = row.get("title")
        url = row.get("url")
        result.append(f"{keyword} -> {title} -> {url}")
    return result


def page_examples_text(top_pages: list[dict[str, Any]], limit: int = 5) -> str:
    return " | ".join(classify_page_examples(top_pages, limit=limit))


def cluster_summary(query: str, top_pages: list[dict[str, Any]], top_keywords: list[dict[str, Any]], rising_terms: list[str]) -> str:
    unique_urls = len({row.get("url") for row in top_pages if row.get("url")})
    unique_terms = len({row.get("keyword") for row in top_keywords if row.get("keyword")})
    return (
        f"{query} 当前可见 {unique_urls} 个高价值页面样本、{unique_terms} 个关键词样本，"
        f"Trends 上升词包括 {', '.join(rising_terms[:3]) or '暂无稳定上升词'}。"
    )


def monetization_summary(page_type: str) -> str:
    if page_type == "tool":
        return "工具页更容易走免费试用、批量、高级导出或订阅升级。"
    if page_type == "comparison":
        return "对比页更容易承接替代、迁移和 affiliate / 引流型转化。"
    if page_type == "template":
        return "模板页适合收集注册和低摩擦导流，但要防止薄内容。"
    return "内容页更适合先验证需求，再用工具页或对比页承接更高价值动作。"


def hero_primary_cta(page_type: str) -> str:
    return {
        "tool": "免费试用",
        "comparison": "马上注册",
        "template": "查看模板",
        "content": "立即开始",
    }.get(page_type, "立即开始")


def comparison_subject(query: str) -> str:
    normalized = re.sub(r"(?i)\b(vs|versus|alternative|alternatives|compare|comparison)\b", " ", query)
    normalized = re.sub(r"(替代方案|替代|对比)", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" -:：")
    return normalized or query.strip()


def comparison_page_blueprint(query: str) -> dict[str, Any]:
    subject = comparison_subject(query)
    return {
        "title_formula": f"{subject} Alternative：为什么很多用户选择你的品牌",
        "hero_requirement": "首屏直接回答为什么你是替代方案，并放一个明确主按钮，不要让用户自己猜下一步。",
        "hero_questions_answered": [
            "为什么你是这个竞品的替代方案",
            "你比它更适合哪类用户",
            "用户现在可以马上怎么开始用你",
        ],
        "hero_cta_examples": [
            "预约 Demo",
            "免费试用",
            "马上注册",
            "打电话咨询",
        ],
        "recommended_h2": f"{subject} vs 你的品牌：Comparison",
        "fit_section_rule": "只写具体适合谁，不要写所有人都适合。优先写团队类型、业务类型、当前卡点。",
        "comparison_table_dimensions": [
            "价格",
            "功能",
            "上手难度",
            "支持方式",
            "适用场景",
            "迁移成本",
        ],
        "suggested_sections": [
            "标题",
            "首屏一句话替代理由 + CTA",
            "适合谁",
            "对比表",
        ],
        "seo_notes": [
            "优先使用 alternative / comparison / versus 结构。",
            "对比表和明确 H2 更适合 Google、AI Overview、ChatGPT、Perplexity 抓取。",
            "如果竞品信息稀少，这类页面有机会承接竞品品牌词流量。",
        ],
    }


def demand_raw_scores(
    *,
    query: str,
    page_type: str,
    trends: dict[str, Any],
    bundle: dict[str, Any],
    kd_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, int], dict[str, list[str]], dict[str, Any]]:
    reasons: dict[str, list[str]] = {}
    top_pages = read_top_pages(bundle)
    top_keywords = read_top_keywords(bundle)
    similarweb = read_similarweb_website(bundle)
    sw_folder_rows = similarweb_folder_rows(bundle)
    sw_non_brand_rows = similarweb_non_brand_rows(bundle)
    sw_paid_landing_rows = similarweb_paid_landing_rows(bundle)
    trend_shape = trend_primary_shape(trends)
    rising_terms = top_rising_terms(trends)
    non_home_pages = count_non_home_pages(top_pages)
    trends_available = bool(trends.get("available"))
    kd_score = get_path(kd_payload or {}, "kd_score", default=None)
    kd_guidance = get_path(kd_payload or {}, "guidance", default="")
    kd_bucket = get_path(kd_payload or {}, "kd_bucket", default="unknown")

    demand_reality = 2
    if trends_available and rising_terms:
        demand_reality += 1
    if semrush_core_ready(bundle):
        demand_reality += 1
    if similarweb_core_ready(bundle):
        demand_reality += 1
    demand_reality = min(5, demand_reality)
    reasons["demand_reality"] = [
        "Trends rising queries available" if rising_terms else "No clear rising queries yet",
        "Google Trends unavailable in this environment" if not trends_available else "Google Trends collected",
        "Semrush core capture ready" if semrush_core_ready(bundle) else "Semrush capture missing or partial",
        "Similarweb core capture ready" if similarweb_core_ready(bundle) else "Similarweb capture missing or partial",
    ]

    search_carry = 2
    if top_keywords:
        search_carry += 1
    if top_pages:
        search_carry += 1
    if get_path(similarweb, "website_performance", "available"):
        search_carry += 1
    if sw_paid_landing_rows or sw_non_brand_rows:
        search_carry += 1
    search_carry = min(5, search_carry)
    reasons["search_carry"] = [
        f"Top keyword rows: {len(top_keywords)}",
        f"Top page rows: {len(top_pages)}",
        f"Similarweb paid landing rows: {len(sw_paid_landing_rows)}",
        f"Similarweb non-brand keyword rows: {len(sw_non_brand_rows)}",
        "Similarweb website-performance ready" if get_path(similarweb, "website_performance", "available") else "No stable Similarweb website-performance layer",
    ]

    trend_stability = {
        "rising": 4,
        "stable": 4,
        "mixed": 3,
        "declining": 2,
        "spike": 1,
        "unknown": 2,
        "missing": 2,
    }.get(trend_shape, 2)
    if not trends_available:
        trend_stability = 2
    reasons["trend_stability"] = [f"Primary trend shape: {trend_shape}"]

    serp_entry = 2
    if non_home_pages >= 3:
        serp_entry += 1
    if top_pages and top_keywords:
        serp_entry += 1
    if page_type in {"tool", "comparison"}:
        serp_entry += 1
    if kd_bucket in {"easy", "possible"}:
        serp_entry += 1
    if kd_bucket in {"hard", "very_hard"}:
        serp_entry -= 1
    serp_entry = min(5, serp_entry)
    reasons["serp_entry"] = [
        f"Non-home top pages: {non_home_pages}",
        f"Inferred page type: {page_type}",
        f"KD bucket: {kd_bucket}",
    ]

    page_intent_fit = 4 if page_type in {"tool", "comparison", "template", "content"} else 2
    if not top_pages and not top_keywords:
        page_intent_fit = max(2, page_intent_fit - 1)
    reasons["page_intent_fit"] = [f"Query intent maps to {page_type_label(page_type)}"]

    clusterability = 2
    unique_terms = len({row.get("keyword") for row in top_keywords if row.get("keyword")})
    if unique_terms >= 5:
        clusterability += 1
    if non_home_pages >= 3:
        clusterability += 1
    if len(sw_folder_rows) >= 5:
        clusterability += 1
    if trends_available and rising_terms:
        clusterability += 1
    if kd_bucket in {"hard", "very_hard"}:
        clusterability = max(2, clusterability - 1)
    clusterability = min(5, clusterability)
    reasons["clusterability"] = [
        f"Unique keyword samples: {unique_terms}",
        f"Rising queries: {len(rising_terms)}",
        f"Similarweb folder rows: {len(sw_folder_rows)}",
        f"KD guidance: {kd_guidance}" if kd_guidance else "",
    ]

    monetization = {
        "tool": 4,
        "comparison": 4,
        "template": 3,
        "content": 3,
    }.get(page_type, 2)
    reasons["monetization"] = [monetization_summary(page_type)]

    execution_fit = 3
    if page_type in {"tool", "content"}:
        execution_fit += 1
    if trend_shape == "spike":
        execution_fit -= 1
    execution_fit = max(1, min(5, execution_fit))
    reasons["execution_fit"] = [
        f"Page type execution fit starts at {execution_fit}",
        "Execution fit is still partly operator-dependent.",
    ]

    scores = {
        "demand_reality": demand_reality,
        "search_carry": search_carry,
        "trend_stability": trend_stability,
        "serp_entry": serp_entry,
        "page_intent_fit": page_intent_fit,
        "clusterability": clusterability,
        "monetization": monetization,
        "execution_fit": execution_fit,
    }
    derived = {
        "top_page_examples": classify_page_examples(top_pages),
        "top_page_examples_text": page_examples_text(top_pages),
        "page_signal_summary": (
            f"Semrush top pages {len(top_pages)} 条，可见非首页高价值页面 {non_home_pages} 条；"
            f"Similarweb website content 文件夹样本 {len(sw_folder_rows)} 条。"
        ),
        "keyword_signal_summary": (
            f"Semrush top keywords {len(top_keywords)} 条，"
            f"Similarweb 非品牌关键词 {len(sw_non_brand_rows)} 条，"
            f"付费落地页 {len(sw_paid_landing_rows)} 条，"
            f"Trends rising queries {len(rising_terms)} 条。"
        ),
        "cluster_summary": cluster_summary(query, top_pages, top_keywords, rising_terms),
        "monetization_summary": monetization_summary(page_type),
        "trends_summary": "Google Trends 可用" if trends_available else "Google Trends 当前不可用，已明确降级",
        "kd_summary": (
            f"web.cafe KD={kd_score}，{kd_guidance}"
            if kd_score is not None and kd_guidance
            else kd_guidance or "当前没有 web.cafe KD 难度证据。"
        ),
    }
    return scores, reasons, derived


def attribution_raw_scores(
    *,
    query: str,
    trends: dict[str, Any],
    bundle: dict[str, Any],
) -> tuple[dict[str, int], dict[str, list[str]], dict[str, Any]]:
    top_pages = read_top_pages(bundle)
    top_keywords = read_top_keywords(bundle)
    sw_folder_rows = similarweb_folder_rows(bundle)
    sw_non_brand_rows = similarweb_non_brand_rows(bundle)
    sw_paid_landing_rows = similarweb_paid_landing_rows(bundle)
    trend_shape = trend_primary_shape(trends)
    non_home_pages = count_non_home_pages(top_pages)
    trends_available = bool(trends.get("available"))
    reasons: dict[str, list[str]] = {}

    scores = {
        "page_change_clarity": min(
            5,
            2
            + (1 if top_pages else 0)
            + (1 if non_home_pages >= 3 else 0)
            + (1 if similarweb_core_ready(bundle) else 0)
            + (1 if sw_folder_rows else 0),
        ),
        "keyword_change_confidence": min(
            5,
            2
            + (1 if top_keywords else 0)
            + (1 if semrush_core_ready(bundle) else 0)
            + (1 if sw_non_brand_rows or sw_paid_landing_rows else 0),
        ),
        "page_type_pattern": min(5, 2 + (1 if non_home_pages >= 3 else 0) + (1 if len(top_pages) >= 5 else 0)),
        "time_window_alignment": {"rising": 4, "stable": 3, "mixed": 3, "declining": 2, "spike": 2}.get(trend_shape, 2)
        if trends_available
        else 2,
        "structural_expansion": min(
            5,
            2
            + (1 if len({row.get('url') for row in top_pages if row.get('url')}) >= 3 else 0)
            + (1 if len(top_pages) >= 5 else 0)
            + (1 if len(sw_folder_rows) >= 5 else 0),
        ),
        "offsite_amplification": 3,
        "chain_closure": min(
            5,
            2
            + (1 if top_pages and top_keywords else 0)
            + (1 if semrush_core_ready(bundle) and similarweb_core_ready(bundle) else 0)
            + (1 if sw_paid_landing_rows else 0),
        ),
    }
    reasons["page_change_clarity"] = [
        f"Top pages: {len(top_pages)}",
        f"Non-home pages: {non_home_pages}",
        f"Similarweb folder rows: {len(sw_folder_rows)}",
    ]
    reasons["keyword_change_confidence"] = [
        f"Top keywords: {len(top_keywords)}",
        f"Similarweb non-brand rows: {len(sw_non_brand_rows)}",
        f"Similarweb paid landing rows: {len(sw_paid_landing_rows)}",
    ]
    reasons["page_type_pattern"] = [f"Unique top-page URLs: {len({row.get('url') for row in top_pages if row.get('url')})}"]
    reasons["time_window_alignment"] = [f"Trend shape: {trend_shape}"]
    reasons["structural_expansion"] = [f"Top pages: {len(top_pages)}", f"Similarweb folder rows: {len(sw_folder_rows)}"]
    reasons["offsite_amplification"] = ["Backlink and amplification are only directionally inferred in this runner."]
    reasons["chain_closure"] = [
        "Chain closure is stronger when both page rows and keyword rows are present.",
        f"Similarweb paid landing rows: {len(sw_paid_landing_rows)}",
    ]

    derived = {
        "time_window_summary": (
            f"Trend shape {trend_shape}; semrush snapshot rows {len(top_pages)} / {len(top_keywords)}; "
            f"similarweb folder rows {len(sw_folder_rows)} / paid landing rows {len(sw_paid_landing_rows)}."
        ),
        "top_page_examples": classify_page_examples(top_pages),
        "top_page_examples_text": page_examples_text(top_pages),
        "page_signal_summary": (
            f"可识别主要页面 {len(top_pages)} 条，非首页样本 {non_home_pages} 条，"
            f"Similarweb 文件夹样本 {len(sw_folder_rows)} 条。"
        ),
        "keyword_signal_summary": (
            f"可识别主要关键词 {len(top_keywords)} 条，"
            f"Similarweb 非品牌关键词 {len(sw_non_brand_rows)} 条，"
            f"付费落地页 {len(sw_paid_landing_rows)} 条。"
        ),
        "cluster_summary": (
            f"页面重复结构样本 {len({row.get('url') for row in top_pages if row.get('url')})} 个；"
            f"Similarweb 文件夹分布样本 {len(sw_folder_rows)} 个。"
        ),
        "trends_summary": "Google Trends 可用" if trends_available else "Google Trends 当前不可用，归因时间对齐只能方向性判断",
    }
    return scores, reasons, derived


def score_payload(mode: str, raw_scores: dict[str, int]) -> dict[str, Any]:
    result = scorecard_module.compute(mode, raw_scores)
    return result


def band_action(band: str, gates_passed: bool) -> str:
    if not gates_passed:
        return "watch"
    return {
        "stop": "stop",
        "watch": "watch",
        "ship_one_page": "ship_one_page",
        "ship_cluster": "ship_cluster",
        "build_site": "build_site",
        "weak_hypothesis": "record_only",
        "partial_explanation": "monitor_hypothesis",
        "solid_attribution": "replicate_narrower_variant",
        "strong_attribution": "translate_into_execution_play",
    }.get(band, band)


def build_first_batch_pages(query: str, page_type: str, rising_terms: list[str]) -> list[dict[str, Any]]:
    base_term = query.strip()
    pages = [
        {
            "working_title": base_term,
            "page_type": page_type_label(page_type),
            "primary_intent": "直接完成主要任务",
            "primary_keyword": base_term,
            "evidence_basis": "主词 + 页面类型推断 + Trends/竞品页级证据",
            "content_or_tool_structure": "首屏交付结果 + 常见失败原因 + 可验证示例 + 下一步入口",
            "hero_primary_cta": hero_primary_cta(page_type),
            "internal_links_to": "支柱页 / 定价页 / 相关场景页",
            "monetization_path": monetization_summary(page_type),
        }
    ]
    if page_type == "comparison":
        pages[0]["page_blueprint"] = comparison_page_blueprint(base_term)
    if page_type != "comparison":
        pages.append(
            {
                "working_title": f"{base_term} vs alternatives",
                "page_type": "对比页",
                "primary_intent": "替代方案比较和迁移决策",
                "primary_keyword": f"{base_term} alternative",
                "evidence_basis": "哥飞/出海方法里对比页通常是高转化承接面",
                "content_or_tool_structure": "核心差异表 + 适用场景 + 迁移成本 + CTA",
                "hero_primary_cta": hero_primary_cta("comparison"),
                "internal_links_to": "主工具页 / 定价页 / FAQ",
                "monetization_path": "affiliate / 引流 / 自家产品升级",
                "page_blueprint": comparison_page_blueprint(base_term),
            }
        )
    pages.append(
        {
            "working_title": f"How to use {base_term}",
            "page_type": "内容页",
            "primary_intent": "解决失败场景和操作路径疑问",
            "primary_keyword": f"how to {base_term}",
            "evidence_basis": "Reddit/问题型需求适合转成失败修复内容页",
            "content_or_tool_structure": "步骤 + 常见失败原因 + 示例 + 工具入口",
            "hero_primary_cta": hero_primary_cta("content"),
            "internal_links_to": "主工具页 / 模板页 / 对比页",
            "monetization_path": "内容引导到工具页或注册页",
        }
    )
    if page_type != "template":
        pages.append(
            {
                "working_title": f"{base_term} examples and templates",
                "page_type": "模板页",
                "primary_intent": "让用户快速看到可验证输出",
                "primary_keyword": f"{base_term} template",
                "evidence_basis": "模板/示例页有助于长尾承接和转化前验证",
                "content_or_tool_structure": "示例库 + 一键复制/试用 + FAQ",
                "hero_primary_cta": hero_primary_cta("template"),
                "internal_links_to": "主工具页 / 场景页 / 对比页",
                "monetization_path": "免费试用导注册或高级模板付费",
            }
        )
    if rising_terms:
        pages.append(
            {
                "working_title": f"{base_term} for {rising_terms[0]}",
                "page_type": page_type_label(page_type),
                "primary_intent": "承接最新场景化长尾需求",
                "primary_keyword": rising_terms[0],
                "evidence_basis": "Google Trends rising queries",
                "content_or_tool_structure": "场景化首屏 + 示例 + 限制条件说明",
                "hero_primary_cta": hero_primary_cta(page_type),
                "internal_links_to": "主工具页 / 模板页",
                "monetization_path": monetization_summary(page_type),
            }
        )
    return pages[:5]


def demand_report(
    *,
    query: str,
    page_type: str,
    score_result: dict[str, Any],
    trends: dict[str, Any],
    derived: dict[str, Any],
    kd_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    band = score_result["band"]
    gates_passed = score_result["all_hard_gates_passed"]
    action = band_action(band, gates_passed)
    rising_terms = top_rising_terms(trends)
    pages = build_first_batch_pages(query, page_type, rising_terms)
    return {
        "mode": "新词 / 新需求验证",
        "core_conclusion": (
            f"{query} 当前的建议动作是 {action}。"
            f"判断依据不是单独的搜索量，而是搜索承接、页面形态、趋势形状和可扩展性。"
        ),
        "demand_reality": (
            f"Demand Reality={get_path(score_result, 'breakdown', default=[])[0]['raw_score'] if get_path(score_result, 'breakdown', default=[]) else 'n/a'}；"
            "结合 community/knowledge 规则和页级证据判断。"
        ),
        "search_proof": derived["keyword_signal_summary"],
        "trend_pattern": (
            f"Google Trends primary shape: {trend_primary_shape(trends)}"
            if trends.get("available")
            else "Google Trends 当前不可用，趋势判断已降级处理。"
        ),
        "page_type_recommendation": (
            f"优先按 {page_type_label(page_type)} 承接，而不是先堆泛内容。"
            + (f" KD 提示：{get_path(kd_payload or {}, 'guidance', default='')}" if kd_payload else "")
        ),
        "recommended_action": action,
        "first_batch_of_pages": pages,
        "main_uncertainty": "如果没有补充社区 / Reddit 痛点证据，这一版仍然偏向搜索侧验证而不是完整 PMF 结论。",
    }


def attribution_report(
    *,
    query: str,
    score_result: dict[str, Any],
    derived: dict[str, Any],
) -> dict[str, Any]:
    action = band_action(score_result["band"], score_result["all_hard_gates_passed"])
    return {
        "mode": "榜单归因",
        "core_conclusion": (
            f"{query} 当前归因结论为 {score_result['band']}。"
            "重点不是看它站强不强，而是看哪些页面和页面型在支撑增长。"
        ),
        "main_growth_pages": derived["top_page_examples"][:5],
        "main_growth_pages_text": derived["top_page_examples_text"],
        "main_growth_terms": derived["keyword_signal_summary"],
        "main_growth_terms_text": derived["keyword_signal_summary"],
        "likely_growth_action": action,
        "reusable_part": "优先复用页面结构和需求承接方式，不要把整体站强当成可复制策略。",
        "do_not_copy": "不要直接复制品牌词、不可控外部资源和首页权重。",
        "confidence_and_gaps": (
            "如果 Similarweb 只有 website-performance 没有 deeper page-level rows，这一版仍然偏方向性；"
            "当前会优先使用 website content、non-brand keywords 和 paid landing pages 补足归因链。"
        ),
    }


def degraded_trends_payload(query: str, geo: str, error: str) -> dict[str, Any]:
    windows = []
    for timeframe in google_trends.DEFAULT_TIMEFRAMES:
        windows.append(
            {
                "timeframe": timeframe,
                "label": google_trends.timeframe_label(timeframe),
                "interest_over_time": {
                    "rows": [],
                    "summary": {
                        "points": 0,
                        "average_interest": None,
                        "latest_interest": None,
                        "peak_interest": None,
                        "shape": "missing",
                    },
                },
                "interest_by_region": [],
                "related_queries": {"top": [], "rising": []},
                "fetch_modes": {},
                "available": False,
                "notes": [error],
            }
        )
    return {
        "query": {"type": "keyword", "value": query},
        "source": {"provider": "google-trends", "captured_at": iso_utc_now()},
        "available": False,
        "geo": geo,
        "language": "en-US",
        "property": "web",
        "windows": windows,
        "summary": {
            "available_windows": 0,
            "all_windows_available": False,
            "shape_by_window": {window["label"]: "missing" for window in windows},
            "primary_shape": "missing",
            "top_rising_queries": [],
            "top_regions": [],
        },
        "notes": [
            "Google Trends could not be collected in the current environment.",
            error,
        ],
    }


def build_workflow(
    *,
    mode: str,
    query: str,
    domain: str | None,
    geo: str,
    username: str,
    password: str,
    max_node_rotations: int,
    brand_name: str = "",
    brand_url: str = "",
    primary_cta_url: str = "",
    primary_cta_label: str = "",
    bundle_input: str | None = None,
    bundle_payload: dict[str, Any] | None = None,
    trends_input: str | None = None,
    kd_input: str | None = None,
    kd_score: int | None = None,
    kd_live: bool = True,
    kd_gl: str = "us",
    kd_hl: str = "en",
    kd_force: bool = False,
    kd_token: str | None = None,
) -> dict[str, Any]:
    page_type = query_page_type(query)
    knowledge = knowledge_payload(mode, query)
    if trends_input:
        trends = json.loads(Path(trends_input).read_text())
    else:
        try:
            trends = google_trends.collect(query, geo=geo)
        except Exception as exc:
            trends = degraded_trends_payload(query, geo, f"{type(exc).__name__}: {exc}")
    kd_payload = web_cafe_kd.collect(
        query=query,
        kd_score=kd_score,
        kd_input=kd_input,
        live=kd_live,
        gl=kd_gl,
        hl=kd_hl,
        force=kd_force,
        token=kd_token,
    )
    bundle = capture_bundle_payload(
        domain=domain,
        username=username,
        password=password,
        max_node_rotations=max_node_rotations,
        bundle_input=bundle_input,
        bundle_payload=bundle_payload,
    )

    if mode == "demand":
        raw_scores, reasoning, derived = demand_raw_scores(query=query, page_type=page_type, trends=trends, bundle=bundle, kd_payload=kd_payload)
        score_result = score_payload("demand", raw_scores)
        report = demand_report(query=query, page_type=page_type, score_result=score_result, trends=trends, derived=derived, kd_payload=kd_payload)
    else:
        raw_scores, reasoning, derived = attribution_raw_scores(query=query, trends=trends, bundle=bundle)
        score_result = score_payload("attribution", raw_scores)
        report = attribution_report(query=query, score_result=score_result, derived=derived)

    workflow = {
        "mode": mode,
        "captured_at": iso_utc_now(),
        "input": {
            "query": query,
            "domain": domain,
            "geo": geo,
            "brand_context": {
                "brand_name": brand_name,
                "brand_url": brand_url,
                "primary_cta_url": primary_cta_url,
                "primary_cta_label": primary_cta_label,
            },
        },
        "knowledge": knowledge,
        "evidence": {
            "trends": trends,
            "web_cafe_kd": kd_payload,
            "tool_capture": bundle,
        },
        "inferences": {
            "query_intent": page_type_label(page_type),
            "page_type": page_type_label(page_type),
        },
        "derived": derived,
        "scores": {
            "raw_scores": raw_scores,
            "reasoning": reasoning,
            "scorecard": score_result,
        },
        "decision": {
            "band": score_result["band"],
            "total_score": score_result["total_score"],
            "all_hard_gates_passed": score_result["all_hard_gates_passed"],
            "recommended_action": band_action(score_result["band"], score_result["all_hard_gates_passed"]),
            "reasoning": derived.get("cluster_summary") or derived.get("page_signal_summary"),
        },
        "report": report,
        "notes": [
            "This runner combines gefei, chuhai, Google Trends, Similarweb, and Semrush into one workflow JSON.",
            "Knowledge outputs are used as judgment rules. Trends and capture bundle are used as market evidence.",
            "Any missing source is kept explicit instead of being silently backfilled.",
            "Google Trends collection degrades explicitly when the upstream source is unavailable or rate-limited.",
        ],
    }
    workflow["guided_flow"] = guided_flow.build_guided_flow(workflow)
    workflow["method_alignment"] = build_method_alignment(
        mode=mode,
        query=query,
        page_type=page_type_label(page_type),
        knowledge=knowledge,
        trends=trends,
        bundle=bundle,
        guided=workflow["guided_flow"],
    )
    workflow["artifacts"] = {
        "page_artifacts": build_page_artifacts_payload(
            workflow,
            brand_name=brand_name,
            brand_url=brand_url,
            primary_cta_url=primary_cta_url,
            primary_cta_label=primary_cta_label,
        )
    }
    workflow["playbook"] = workflow_playbook.build_playbook(workflow)
    return workflow


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full demand-validation-os workflow.")
    parser.add_argument("--mode", choices=["demand", "attribution"], required=True)
    parser.add_argument("--query", required=True, help="Keyword or domain to inspect")
    parser.add_argument("--domain", help="Competitor or target domain for Semrush/Similarweb capture")
    parser.add_argument("--geo", default="US")
    parser.add_argument("--username", default=os.environ.get("THREEUE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("THREEUE_PASSWORD", ""))
    parser.add_argument("--max-node-rotations", type=int, default=2)
    parser.add_argument("--brand-name", default="", help="Our brand name for page-artifact generation")
    parser.add_argument("--brand-url", default="", help="Our canonical product URL for page-artifact generation")
    parser.add_argument("--primary-cta-url", default="", help="Primary CTA target URL for generated page artifacts")
    parser.add_argument("--primary-cta-label", default="", help="Primary CTA label override for generated page artifacts")
    parser.add_argument("--bundle-input", help="Reuse an existing capture_bundle JSON file instead of recapturing")
    parser.add_argument("--trends-input", help="Reuse an existing Google Trends JSON file instead of refetching")
    parser.add_argument("--kd-input", help="Reuse an existing web.cafe KD JSON file")
    parser.add_argument("--kd-score", type=int, help="Manual KD score from seo.web.cafe/kd/")
    parser.add_argument("--disable-kd-live", action="store_true", help="Skip live web.cafe KD fetch and fall back to manual/unknown")
    parser.add_argument("--kd-gl", default="us", help="web.cafe KD Google country code")
    parser.add_argument("--kd-hl", default="en", help="web.cafe KD language code")
    parser.add_argument("--kd-force", action="store_true", help="Force live web.cafe KD recompute instead of cached result")
    parser.add_argument("--kd-token", help="Optional explicit web.cafe KD page token override")
    parser.add_argument("--output", help="Write workflow JSON to a file")
    args = parser.parse_args()

    domain = args.domain or (args.query if looks_like_domain(args.query) else None)
    needs_live_capture = domain and not args.bundle_input
    if needs_live_capture and (not args.username or not args.password):
        raise SystemExit("Missing 3ue credentials. Set THREEUE_USERNAME / THREEUE_PASSWORD or pass --username / --password.")

    workflow = build_workflow(
        mode=args.mode,
        query=args.query,
        domain=domain,
        geo=args.geo,
        username=args.username,
        password=args.password,
        max_node_rotations=args.max_node_rotations,
        brand_name=args.brand_name,
        brand_url=args.brand_url,
        primary_cta_url=args.primary_cta_url,
        primary_cta_label=args.primary_cta_label,
        bundle_input=args.bundle_input,
        trends_input=args.trends_input,
        kd_input=args.kd_input,
        kd_score=args.kd_score,
        kd_live=not args.disable_kd_live,
        kd_gl=args.kd_gl,
        kd_hl=args.kd_hl,
        kd_force=args.kd_force,
        kd_token=args.kd_token,
    )
    text = json.dumps(workflow, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
