#!/usr/bin/env python3
"""Render a web.cafe-style staged guided flow from workflow JSON."""

from __future__ import annotations

import argparse
import json
from typing import Any


def step_fact_list(values: list[str]) -> list[str]:
    return [item for item in values if item]


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


def build_landing(workflow: dict[str, Any]) -> dict[str, Any]:
    mode = workflow.get("mode")
    query = get_path(workflow, "input", "query", default="")
    decision = get_path(workflow, "decision", "band", default="watch")
    if mode == "demand":
        contradiction = f"这个词看起来能做，但它到底是社区噪音，还是能被搜索稳定承接的真实需求？"
        headline = f"把 {query} 从“想法”拆成“证据、阶段、动作”"
        hidden_variable = "真正决定结果的不是搜索量，而是需求是否被搜索承接、页面形态是否清晰、能否扩成页面系统。"
    else:
        contradiction = f"{query} 看起来在涨，但它到底是首页强、品牌强，还是某一批页面正在系统性吃到流量？"
        headline = f"把 {query} 的增长拆成页面、关键词和可复用动作"
        hidden_variable = "真正决定归因质量的不是总流量，而是 page -> term -> action 这条链能不能闭合。"
    return {
        "headline": headline,
        "contradiction": contradiction,
        "hidden_variable": hidden_variable,
        "primary_cta": "跟我走完分阶段诊断",
        "secondary_cta": "直接看最终建议",
        "bounded_scope": "8 步数据化诊断" if mode == "demand" else "6 步数据化归因",
        "decision_preview": decision,
    }


def build_demand_stages(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    query = get_path(workflow, "input", "query", default="")
    knowledge = workflow.get("knowledge", {})
    trends = workflow.get("evidence", {}).get("trends", {})
    tool_capture = workflow.get("evidence", {}).get("tool_capture", {})
    scores = workflow.get("scores", {})
    report = workflow.get("report", {})
    first_pages = report.get("first_batch_of_pages", [])
    trend_shape = get_path(trends, "summary", "primary_shape", default="unknown")
    core_ready_tools = get_path(tool_capture, "summary", "core_ready_tools", default=[])
    semrush_ready = "semrush" in core_ready_tools
    similarweb_ready = "similarweb" in core_ready_tools
    trends_available = bool(trends.get("available"))
    top_rising = get_path(trends, "summary", "top_rising_queries", default=[])
    rising_terms = ", ".join(item.get("query", "") for item in top_rising[:3] if item.get("query"))

    return [
        {
            "step": 1,
            "title": "先把问题框准",
            "question": f"{query} 到底是不是一个值得进入的搜索需求，而不是只是听起来像机会？",
            "facts": step_fact_list(
                [
                    workflow.get("input", {}).get("query"),
                    get_path(workflow, "inferences", "query_intent"),
                    get_path(workflow, "inferences", "page_type"),
                ]
            ),
            "inference": "第一步不是找更多词，而是先判断用户实际上想要什么页面。",
            "diagnosis": get_path(report, "page_type_recommendation", default="页面类型还不够清晰。"),
            "next_action": "先确认首屏要交付的是工具、内容、对比还是模板。",
        },
        {
            "step": 2,
            "title": "需求到底真不真",
            "question": "这个需求背后有没有稳定痛点、代价和结果诉求？",
            "facts": step_fact_list(
                [
                    get_path(knowledge, "gefei", "summary"),
                    get_path(knowledge, "chuhai", "focus_methods", 0, default=""),
                ]
            ),
            "inference": "这里只把知识库当判断规则，不把它当作真实市场数据替代品。",
            "diagnosis": report.get("demand_reality", ""),
            "next_action": "如果社区证据没补齐，这一步最多只能给出保守通过。",
        },
        {
            "step": 3,
            "title": "搜索有没有真的在承接",
            "question": "用户会不会真的通过搜索来找这个结果？",
            "facts": step_fact_list(
                [
                    f"Trends primary shape: {trend_shape}",
                    f"Semrush ready: {semrush_ready}",
                    f"Similarweb ready: {similarweb_ready}",
                    f"Trends available: {trends_available}",
                    get_path(report, "search_proof"),
                ]
            ),
            "inference": "搜索承接要看趋势是否持续，还要看 Semrush / Similarweb 能不能找到页级或词级证据。",
            "diagnosis": report.get("search_proof", ""),
            "next_action": "没有页级证据时，不要直接把它判成可规模化 SEO 需求。",
        },
        {
            "step": 4,
            "title": "先看页，不先看总量",
            "question": "什么页面正在拿量，用户要的页面形态到底是什么？",
            "facts": step_fact_list(
                [
                    get_path(knowledge, "chuhai", "method_highlights", 1, default=""),
                    get_path(workflow, "derived", "page_signal_summary"),
                    get_path(workflow, "derived", "top_page_examples_text", default=""),
                ]
            ),
            "inference": "这是 `主要页面 / Landing Pages` 方法的核心：先找已经赢的页面，再反推词和结构。",
            "diagnosis": report.get("page_type_recommendation", ""),
            "next_action": "把首页强和内页强分开看，优先复用可拆成页面系统的结构。",
        },
        {
            "step": 5,
            "title": "能不能扩成集群",
            "question": "这是一个单页机会，还是可以扩成一组页面？",
            "facts": step_fact_list(
                [
                    get_path(workflow, "derived", "cluster_summary"),
                    rising_terms,
                    f"Clusterability score: {get_path(scores, 'raw_scores', 'clusterability')}",
                ]
            ),
            "inference": "真正能放大的，不是一个词，而是一组意图相近但页面角色不同的页面。",
            "diagnosis": report.get("recommended_action", ""),
            "next_action": "如果只能落成一页，就不要硬讲成建站机会。",
        },
        {
            "step": 6,
            "title": "趋势是短爆还是耐久",
            "question": "这个词的热度是在起，还是只是被事件推了一下？",
            "facts": step_fact_list(
                [
                    f"Trend shape: {trend_shape}",
                    get_path(report, "trend_pattern"),
                    f"Rising queries: {rising_terms}" if rising_terms else "",
                ]
            ),
            "inference": "Trends 用来判断形状，不用来伪造绝对量级。",
            "diagnosis": report.get("trend_pattern", ""),
            "next_action": "短爆词只适合低成本试页，不适合直接上站。",
        },
        {
            "step": 7,
            "title": "怎么承接、怎么赚钱",
            "question": "就算能拿到流量，这种页面能不能把结果交付出去？",
            "facts": step_fact_list(
                [
                    f"Monetization score: {get_path(scores, 'raw_scores', 'monetization')}",
                    f"Execution score: {get_path(scores, 'raw_scores', 'execution_fit')}",
                    get_path(workflow, "derived", "monetization_summary"),
                ]
            ),
            "inference": "能搜索不代表能赚钱，能赚钱也不代表应该先做大站。",
            "diagnosis": get_path(workflow, "decision", "reasoning", default=""),
            "next_action": "优先交付一个用户能走通的结果闭环，而不是先堆内容规模。",
        },
        {
            "step": 8,
            "title": "最后决策和首批页面",
            "question": "现在应该停、看、做一页、做集群，还是直接建站？",
            "facts": step_fact_list(
                [
                    f"Decision band: {get_path(workflow, 'decision', 'band')}",
                    f"Total score: {get_path(workflow, 'decision', 'total_score')}",
                    f"First batch pages: {len(first_pages)}",
                ]
            ),
            "inference": "最后的动作必须落到页面清单，不落到页面就还是停留在关键词层。",
            "diagnosis": report.get("recommended_action", ""),
            "next_action": "按首批页面清单开工，并把每页的可验证示例、失败修复和内链关系一起定掉。",
        },
    ]


def build_attribution_stages(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    report = workflow.get("report", {})
    scores = workflow.get("scores", {})
    query = get_path(workflow, "input", "query", default="")
    return [
        {
            "step": 1,
            "title": "先冻结观察窗口",
            "question": f"{query} 的增长到底发生在什么时间段？",
            "facts": step_fact_list(
                [
                    get_path(workflow, "derived", "time_window_summary"),
                    get_path(report, "confidence_and_gaps"),
                ]
            ),
            "inference": "不先冻结窗口，就很容易把旧盘子和新增长混在一起。",
            "diagnosis": report.get("confidence_and_gaps", ""),
            "next_action": "先按窗口归因，再讨论能不能复用。",
        },
        {
            "step": 2,
            "title": "哪些页面真的在动",
            "question": "增长是不是集中在可识别的页面，而不是整站平均抬升？",
            "facts": step_fact_list(
                [
                    get_path(workflow, "derived", "top_page_examples_text"),
                    get_path(workflow, "derived", "page_signal_summary"),
                ]
            ),
            "inference": "页级集中度越高，归因质量越高。",
            "diagnosis": report.get("main_growth_pages", ""),
            "next_action": "先把首页强、目录页强、工具页强拆开看。",
        },
        {
            "step": 3,
            "title": "哪些词和页面型在带动",
            "question": "是品牌、泛词、还是一批新页面型在带动增长？",
            "facts": step_fact_list(
                [
                    get_path(workflow, "derived", "keyword_signal_summary"),
                    get_path(report, "main_growth_terms_text"),
                ]
            ),
            "inference": "没有 term -> page 的连接，只能算半归因。",
            "diagnosis": report.get("main_growth_terms", ""),
            "next_action": "把可复用词和不可复用品牌词分开。",
        },
        {
            "step": 4,
            "title": "这个玩法是不是系统性的",
            "question": "它是靠一个爆页面，还是靠一组可复用页面结构？",
            "facts": step_fact_list(
                [
                    get_path(workflow, "derived", "cluster_summary"),
                    f"Structural expansion score: {get_path(scores, 'raw_scores', 'structural_expansion')}",
                ]
            ),
            "inference": "只有重复出现的页面形态，才值得当打法去学。",
            "diagnosis": report.get("likely_growth_action", ""),
            "next_action": "复用页面结构，不要只抄表层关键词。",
        },
        {
            "step": 5,
            "title": "哪些部分能学，哪些不能学",
            "question": "我们到底应该复用什么，而不是只看到它流量大？",
            "facts": step_fact_list(
                [
                    report.get("reusable_part", ""),
                    report.get("do_not_copy", ""),
                ]
            ),
            "inference": "可复用的是 page shape 和 demand absorption，不是对方站点整体强。",
            "diagnosis": report.get("reusable_part", ""),
            "next_action": "只复制可交付的页面结构，不复制不可控资源优势。",
        },
        {
            "step": 6,
            "title": "最后归因结论",
            "question": "这算不算一个闭合的归因案例？",
            "facts": step_fact_list(
                [
                    f"Decision band: {get_path(workflow, 'decision', 'band')}",
                    f"Total score: {get_path(workflow, 'decision', 'total_score')}",
                    f"Chain closure score: {get_path(scores, 'raw_scores', 'chain_closure')}",
                ]
            ),
            "inference": "只有当 page -> term -> traffic -> action 能闭合，才能把它当成可执行结论。",
            "diagnosis": report.get("core_conclusion", ""),
            "next_action": "把最终可复用动作写成下一轮实验清单，而不是只写成一段分析结论。",
        },
    ]


def build_guided_flow(workflow: dict[str, Any]) -> dict[str, Any]:
    mode = workflow.get("mode")
    stages = build_demand_stages(workflow) if mode == "demand" else build_attribution_stages(workflow)
    return {
        "mode": mode,
        "entry": build_landing(workflow),
        "step_count": len(stages),
        "stages": stages,
        "direct_result": workflow.get("decision", {}),
        "notes": [
            "This flow follows the web.cafe simulator pattern: contradiction first, guided path vs direct result, and one concept per step.",
            "Each step is driven by workflow JSON, not by freeform prose alone.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a staged guided flow from workflow JSON.")
    parser.add_argument("--input", required=True, help="Workflow JSON path")
    parser.add_argument("--output", help="Write guided flow JSON to a file")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as handle:
        workflow = json.load(handle)
    data = build_guided_flow(workflow)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
