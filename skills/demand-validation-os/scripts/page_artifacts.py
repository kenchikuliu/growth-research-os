#!/usr/bin/env python3
"""Generate publishable page artifacts from demand-validation workflow JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def get_path(data: dict[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "page-artifact"


def comparison_subject(text: str) -> str:
    normalized = re.sub(r"(?i)\b(vs|versus|alternative|alternatives|compare|comparison)\b", " ", text)
    normalized = re.sub(r"(替代方案|替代|对比)", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" -:：")
    return normalized or text.strip()


def brand_context_payload(
    *,
    brand_name: str = "",
    brand_url: str = "",
    primary_cta_url: str = "",
    primary_cta_label: str = "",
) -> dict[str, str]:
    return {
        "brand_name": brand_name.strip() or "你的品牌",
        "brand_url": brand_url.strip(),
        "primary_cta_url": primary_cta_url.strip(),
        "primary_cta_label": primary_cta_label.strip(),
    }


def evidence_counts(workflow: dict[str, Any]) -> dict[str, int]:
    normalized = get_path(workflow, "evidence", "tool_capture", "normalized", default={})
    if normalized:
        top_pages = normalized.get("top_pages", [])
        top_keywords = normalized.get("top_keywords", [])
        landing_pages = normalized.get("landing_pages", [])
        page_clusters = normalized.get("page_clusters", [])
        tool_signals = normalized.get("tool_signals", {})
        return {
            "semrush_top_pages": len([row for row in top_pages if row.get("source_tool") == "semrush"]),
            "semrush_top_keywords": len([row for row in top_keywords if row.get("source_tool") == "semrush"]),
            "similarweb_folder_rows": len(
                [row for row in page_clusters if row.get("source_tool") == "similarweb" and row.get("cluster_type") == "folder"]
            ),
            "similarweb_non_brand_keywords": len([row for row in top_keywords if row.get("source_tool") == "similarweb"]),
            "similarweb_paid_landing_pages": len(
                [row for row in landing_pages if row.get("source_tool") == "similarweb" and row.get("landing_type") == "paid_landing_page"]
            ),
            "similarweb_priority_keyword_alerts": int(
                get_path(tool_signals, "similarweb", "keyword_count", default=0)
            ),
            "similarweb_priority_landing_alerts": int(
                get_path(tool_signals, "similarweb", "landing_page_count", default=0)
            ),
        }

    semrush_top_pages = len(get_path(workflow, "evidence", "tool_capture", "results", "semrush", "data", "top_pages", default=[]))
    semrush_top_keywords = len(
        get_path(workflow, "evidence", "tool_capture", "results", "semrush", "data", "top_organic_keywords", default=[])
    )
    sw_folder_rows = len(
        get_path(
            workflow,
            "evidence",
            "tool_capture",
            "results",
            "similarweb",
            "data",
            "website_evidence",
            "website_content",
            "summary",
            "rows",
            default=[],
        )
    )
    sw_non_brand = len(
        get_path(
            workflow,
            "evidence",
            "tool_capture",
            "results",
            "similarweb",
            "data",
            "website_evidence",
            "search_overview",
            "top_non_brand_keywords",
            "rows",
            default=[],
        )
    )
    sw_paid_landing = len(
        get_path(
            workflow,
            "evidence",
            "tool_capture",
            "results",
            "similarweb",
            "data",
            "website_evidence",
            "search_overview",
            "paid_landing_pages",
            "rows",
            default=[],
        )
    )
    priority_alerts = get_path(
        workflow,
        "evidence",
        "tool_capture",
        "results",
        "similarweb",
        "data",
        "website_evidence",
        "home_signals",
        "priority_alerts",
        default=[],
    )
    sw_priority_keywords = len([row for row in priority_alerts if row.get("metric") == "keywords"])
    sw_priority_landing = len([row for row in priority_alerts if row.get("metric") == "landing_pages"])
    return {
        "semrush_top_pages": semrush_top_pages,
        "semrush_top_keywords": semrush_top_keywords,
        "similarweb_folder_rows": sw_folder_rows,
        "similarweb_non_brand_keywords": sw_non_brand,
        "similarweb_paid_landing_pages": sw_paid_landing,
        "similarweb_priority_keyword_alerts": sw_priority_keywords,
        "similarweb_priority_landing_alerts": sw_priority_landing,
    }


def build_proof_points(workflow: dict[str, Any]) -> list[str]:
    counts = evidence_counts(workflow)
    points = []
    if counts["similarweb_paid_landing_pages"]:
        points.append(f"Similarweb 已抓到 {counts['similarweb_paid_landing_pages']} 条付费落地页样本。")
    if counts["similarweb_non_brand_keywords"]:
        points.append(f"Similarweb 已抓到 {counts['similarweb_non_brand_keywords']} 条非品牌关键词样本。")
    if counts["similarweb_folder_rows"]:
        points.append(f"Similarweb 已抓到 {counts['similarweb_folder_rows']} 条网站内容文件夹样本。")
    if counts["semrush_top_pages"]:
        points.append(f"Semrush 已抓到 {counts['semrush_top_pages']} 条 Top Pages 样本。")
    if counts["semrush_top_keywords"]:
        points.append(f"Semrush 已抓到 {counts['semrush_top_keywords']} 条 Top Keywords 样本。")
    trend_shape = get_path(workflow, "evidence", "trends", "summary", "primary_shape", default="missing")
    points.append(f"Google Trends 当前趋势形状为 {trend_shape}。")
    gefei_summary = get_path(workflow, "knowledge", "gefei", "summary", default="")
    if gefei_summary:
        points.append(f"gefei 规则层摘要：{gefei_summary}")
    kd_guidance = get_path(workflow, "evidence", "web_cafe_kd", "guidance", default="")
    kd_score = get_path(workflow, "evidence", "web_cafe_kd", "kd_score", default=None)
    if kd_guidance:
        if kd_score is None:
            points.append(f"web.cafe KD 提示：{kd_guidance}")
        else:
            points.append(f"web.cafe KD={kd_score}，提示：{kd_guidance}")
    return points[:6]


def build_fit_for_blocks() -> list[dict[str, str]]:
    return [
        {
            "title": "SaaS 团队",
            "problem": "你们不是只想看几个关键词，而是想知道某个 demand 到底值不值得做、该先做哪一页。",
            "why_fit": "这套输出会直接把证据收束成页面类型、首批页面和下一步动作。",
        },
        {
            "title": "跨境卖家",
            "problem": "你已经知道竞品词有流量，但不会把 Similarweb / Semrush 的页级信号转成落地页计划。",
            "why_fit": "它会把 landing pages、top pages、top keywords 和趋势拼成一条能执行的链路。",
        },
        {
            "title": "外贸工厂 / B2B 服务商",
            "problem": "你更在意哪种内容页、对比页或工具页能承接询盘，而不是泛流量。",
            "why_fit": "输出不是关键词清单，而是按意图拆好的页面清单和 CTA 建议。",
        },
        {
            "title": "SEO / 内容运营",
            "problem": "你不想再把时间花在散装工具和手工串联结论上。",
            "why_fit": "这套 workflow 把诊断顺序固定下来，适合拿来做周会、复盘和页面立项。",
        },
    ]


def build_comparison_rows(competitor: str, brand_name: str, workflow: dict[str, Any]) -> list[dict[str, Any]]:
    decision = get_path(workflow, "decision", "recommended_action", default="")
    page_signal = get_path(workflow, "derived", "page_signal_summary", default="")
    keyword_signal = get_path(workflow, "derived", "keyword_signal_summary", default="")
    return [
        {
            "dimension": "价格",
            "competitor_label": competitor,
            "competitor_value": "请补竞品公开价格、席位限制和升级门槛。",
            "our_label": brand_name,
            "our_value": "先按一个 query 或一个页面机会开始，不必先为一整套重工具工作流买单。",
            "manual_fill_required": True,
        },
        {
            "dimension": "功能",
            "competitor_label": competitor,
            "competitor_value": "请补竞品是否只给面板、还是能给诊断和页面动作。",
            "our_label": brand_name,
            "our_value": "把 Similarweb、Semrush、Google Trends、gefei、chuhai 串成一个证据优先的判断链。",
            "manual_fill_required": True,
        },
        {
            "dimension": "上手难度",
            "competitor_label": competitor,
            "competitor_value": "通常需要用户自己拼流程、自己判断先看哪张表。",
            "our_label": brand_name,
            "our_value": "先给阶段诊断，再给结论和页面建议，减少用户自己拼步骤的成本。",
            "manual_fill_required": False,
        },
        {
            "dimension": "支持方式",
            "competitor_label": competitor,
            "competitor_value": "请补竞品是偏自助、客服、顾问制，还是模板制。",
            "our_label": brand_name,
            "our_value": "支持 staged diagnosis、替代页蓝图、页面 JSON 和后续页面规划。",
            "manual_fill_required": True,
        },
        {
            "dimension": "适用场景",
            "competitor_label": competitor,
            "competitor_value": "更适合单点查数时就写清楚，不要泛写。",
            "our_label": brand_name,
            "our_value": f"更适合新词验证、榜单归因、comparison 页规划，以及 {decision or '首批页面判断'}。",
            "manual_fill_required": False,
        },
        {
            "dimension": "迁移成本",
            "competitor_label": competitor,
            "competitor_value": "请写清用户从旧工作流切到新工作流，最先要替换哪一步。",
            "our_label": brand_name,
            "our_value": f"可以先从一篇对比页或一个 query 开始替换，证据层参考：{page_signal or keyword_signal}",
            "manual_fill_required": True,
        },
    ]


def build_faq(competitor: str, brand_name: str) -> list[dict[str, str]]:
    return [
        {
            "question": f"{brand_name} 和 {competitor} 最大的区别是什么？",
            "answer": f"{brand_name} 不是只给你单张数据面板，而是把证据、诊断、页面建议和下一步动作连在一起。",
        },
        {
            "question": "如果我现在只是想验证一个新词，适合直接用吗？",
            "answer": "适合。先跑一个 query，看 recommended action、first batch of pages 和 comparison page artifact，再决定要不要继续扩页。",
        },
        {
            "question": "没有完整 Similarweb / Semrush 数据还能不能用？",
            "answer": "可以，但系统会明确标出缺口，不会拿空白证据硬凑结论。",
        },
        {
            "question": "第一页应该先做什么？",
            "answer": "先做首批页面里意图最清晰、CTA 最明确、证据最闭环的那一页，通常是工具页或对比页。",
        },
    ]


def build_comparison_page_artifact(page: dict[str, Any], workflow: dict[str, Any], brand_context: dict[str, str]) -> dict[str, Any]:
    query = get_path(workflow, "input", "query", default="")
    competitor = comparison_subject(page.get("primary_keyword") or query)
    brand_name = brand_context["brand_name"]
    cta_label = brand_context["primary_cta_label"] or page.get("hero_primary_cta") or "马上注册"
    cta_url = brand_context["primary_cta_url"] or brand_context["brand_url"] or "/signup"
    blueprint = page.get("page_blueprint") or {}
    proof_points = build_proof_points(workflow)
    page_slug = slugify(f"{competitor}-alternative")
    keyword_signal = get_path(workflow, "derived", "keyword_signal_summary", default="")
    page_signal = get_path(workflow, "derived", "page_signal_summary", default="")
    conclusion = get_path(workflow, "report", "core_conclusion", default="")

    hero_subheadline = (
        f"如果你现在缺的不是又一个散装面板，而是一条从需求验证、竞品归因到页面落地的 workflow，"
        f"{brand_name} 会更直接。{keyword_signal or page_signal}"
    ).strip()

    page_json = {
        "page_type": "comparison",
        "title": blueprint.get("title_formula") or f"{competitor} Alternative：为什么很多用户选择{brand_name}",
        "meta_title": blueprint.get("title_formula") or f"{competitor} Alternative：为什么很多用户选择{brand_name}",
        "meta_description": (
            f"直接回答为什么 {brand_name} 是 {competitor} 的替代方案、它更适合哪类用户、以及用户现在怎么马上开始用。"
        ),
        "h1": blueprint.get("title_formula") or f"{competitor} Alternative：为什么很多用户选择{brand_name}",
        "hero": {
            "eyebrow": "Alternative / Comparison",
            "headline": f"不是再多一个工具面板，而是把验证、诊断和页面动作串成一个 workflow。",
            "subheadline": hero_subheadline,
            "primary_cta": {
                "label": cta_label,
                "url": cta_url,
            },
            "supporting_proof": proof_points[:3],
        },
        "direct_answers": [
            {
                "question": "为什么你是这个竞品的替代方案",
                "answer": (
                    f"{brand_name} 更像一条决策链，而不只是一个查询入口。"
                    "它把 Similarweb 的落地页信号、Semrush 的页面和词、Google Trends 的趋势形状，再加上 gefei / chuhai 的判断规则，"
                    "直接收束成可执行的下一步。"
                ),
            },
            {
                "question": "你比它更适合哪类用户",
                "answer": (
                    f"{brand_name} 更适合不是只想查数，而是想判断一个 demand 值不值得做、"
                    "该先做工具页还是对比页、以及首批页面应该怎么排优先级的人。"
                ),
            },
            {
                "question": "用户现在可以马上怎么开始用你",
                "answer": (
                    f"直接拿一个竞品词或域名跑一遍 workflow，先看 {conclusion or 'recommended action'}，"
                    "再看 first batch of pages，最后把这页 comparison JSON 拿去落页。"
                ),
            },
        ],
        "fit_for": build_fit_for_blocks(),
        "comparison_section": {
            "heading": blueprint.get("recommended_h2") or f"{competitor} vs {brand_name}：Comparison",
            "rows": build_comparison_rows(competitor, brand_name, workflow),
            "table_dimensions": blueprint.get("comparison_table_dimensions") or [],
        },
        "evidence_section": {
            "heading": "为什么这页不是拍脑袋写的",
            "proof_points": proof_points,
            "page_signal_summary": page_signal,
            "keyword_signal_summary": keyword_signal,
        },
        "faq": build_faq(competitor, brand_name),
        "internal_links": [
            "主工具页",
            "定价页",
            "模板页",
            "相关场景页",
        ],
        "editorial_notes": {
            "fit_section_rule": blueprint.get("fit_section_rule"),
            "seo_notes": blueprint.get("seo_notes") or [],
            "manual_fill_required_rows": [
                row["dimension"] for row in build_comparison_rows(competitor, brand_name, workflow) if row["manual_fill_required"]
            ],
        },
    }
    return {
        "kind": "comparison_page",
        "slug": page_slug,
        "target_path": f"/alternatives/{page_slug}",
        "page_json": page_json,
        "frontend_payload": build_frontend_payload(
            kind="comparison_page",
            slug=page_slug,
            target_path=f"/alternatives/{page_slug}",
            page_json=page_json,
            workflow=workflow,
        ),
    }


def build_generic_page_artifact(page: dict[str, Any], workflow: dict[str, Any], brand_context: dict[str, str]) -> dict[str, Any]:
    page_slug = slugify(page.get("primary_keyword") or page.get("working_title") or "page")
    cta_label = brand_context["primary_cta_label"] or page.get("hero_primary_cta") or "立即开始"
    cta_url = brand_context["primary_cta_url"] or brand_context["brand_url"] or "/start"
    proof_points = build_proof_points(workflow)
    page_json = {
        "page_type": page.get("page_type"),
        "title": page.get("working_title"),
        "h1": page.get("working_title"),
        "hero": {
            "headline": page.get("working_title"),
            "subheadline": page.get("content_or_tool_structure"),
            "primary_cta": {
                "label": cta_label,
                "url": cta_url,
            },
        },
        "evidence_basis": page.get("evidence_basis"),
        "proof_points": proof_points[:3],
        "internal_links": page.get("internal_links_to"),
        "monetization_path": page.get("monetization_path"),
    }
    return {
        "kind": "page_brief",
        "slug": page_slug,
        "target_path": f"/pages/{page_slug}",
        "page_json": page_json,
        "frontend_payload": build_frontend_payload(
            kind="page_brief",
            slug=page_slug,
            target_path=f"/pages/{page_slug}",
            page_json=page_json,
            workflow=workflow,
        ),
    }


def build_frontend_payload(
    *,
    kind: str,
    slug: str,
    target_path: str,
    page_json: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    hero = page_json.get("hero") or {}
    direct_answers = page_json.get("direct_answers") or []
    fit_for = page_json.get("fit_for") or []
    comparison = page_json.get("comparison_section") or {}
    evidence = page_json.get("evidence_section") or {}
    faq = page_json.get("faq") or []
    editorial = page_json.get("editorial_notes") or {}
    blocks = [
        {
            "id": "direct-answers",
            "type": "direct_answers",
            "required": kind == "comparison_page",
            "data": {
                "heading": "直接回答三个问题",
                "items": direct_answers,
            },
        },
        {
            "id": "fit-for",
            "type": "fit_for",
            "required": kind == "comparison_page",
            "data": {
                "heading": "更适合谁",
                "items": fit_for,
            },
        },
        {
            "id": "comparison-table",
            "type": "comparison_table",
            "required": kind == "comparison_page",
            "data": {
                "heading": comparison.get("heading"),
                "dimensions": comparison.get("table_dimensions") or [],
                "rows": comparison.get("rows") or [],
            },
        },
        {
            "id": "evidence",
            "type": "evidence",
            "required": True,
            "data": {
                "heading": evidence.get("heading") or "证据",
                "proof_points": evidence.get("proof_points") or page_json.get("proof_points") or [],
                "page_signal_summary": evidence.get("page_signal_summary") or page_json.get("evidence_basis") or "",
                "keyword_signal_summary": evidence.get("keyword_signal_summary") or "",
            },
        },
        {
            "id": "faq",
            "type": "faq",
            "required": kind == "comparison_page",
            "data": {
                "heading": "常见问题",
                "items": faq,
            },
        },
    ]
    return {
        "version": "2026-06-11",
        "template": kind,
        "route": {
            "slug": slug,
            "path": target_path,
        },
        "seo": {
            "title": page_json.get("meta_title") or page_json.get("title") or page_json.get("h1"),
            "description": page_json.get("meta_description") or evidence.get("page_signal_summary") or "",
            "h1": page_json.get("h1") or page_json.get("title"),
        },
        "hero": {
            "eyebrow": hero.get("eyebrow"),
            "headline": hero.get("headline"),
            "subheadline": hero.get("subheadline"),
            "primary_cta": hero.get("primary_cta") or {},
            "supporting_proof": hero.get("supporting_proof") or page_json.get("proof_points") or [],
        },
        "sections": [
            {
                "type": block["type"],
                **block["data"],
            }
            for block in blocks
        ],
        "blocks": blocks,
        "navigation": {
            "internal_links": page_json.get("internal_links") or [],
        },
        "editorial": {
            "notes": editorial.get("seo_notes") or [],
            "manual_fill_required_rows": editorial.get("manual_fill_required_rows") or [],
            "fit_section_rule": editorial.get("fit_section_rule") or "",
        },
        "source_context": {
            "query": get_path(workflow, "input", "query", default=""),
            "mode": workflow.get("mode"),
            "recommended_action": get_path(workflow, "decision", "recommended_action", default=""),
        },
    }


def build_publishable_page(
    *,
    kind: str,
    slug: str,
    target_path: str,
    page_json: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    frontend = build_frontend_payload(
        kind=kind,
        slug=slug,
        target_path=target_path,
        page_json=page_json,
        workflow=workflow,
    )
    hero = frontend.get("hero") or {}
    blocks = frontend.get("blocks") or []
    sections = []
    for block in blocks:
        block_type = block.get("type")
        data = block.get("data") or {}
        sections.append(
            {
                "id": block.get("id"),
                "type": block_type,
                "required": bool(block.get("required")),
                "heading": data.get("heading") or "",
                "body": data,
            }
        )
    return {
        "version": "2026-06-11",
        "slug": slug,
        "path": target_path,
        "template": kind,
        "seo": frontend.get("seo") or {},
        "hero": {
            "eyebrow": hero.get("eyebrow"),
            "headline": hero.get("headline"),
            "subheadline": hero.get("subheadline"),
            "primary_cta": hero.get("primary_cta") or {},
            "supporting_proof": hero.get("supporting_proof") or [],
        },
        "sections": sections,
        "navigation": frontend.get("navigation") or {},
        "editorial": frontend.get("editorial") or {},
        "source_context": frontend.get("source_context") or {},
    }


def build_page_artifacts(workflow: dict[str, Any], brand_context: dict[str, str] | None = None) -> dict[str, Any]:
    context = brand_context or brand_context_payload()
    first_pages = get_path(workflow, "report", "first_batch_of_pages", default=[])
    artifacts = []
    publishable_pages = []
    for page in first_pages:
        if (page.get("page_type") or "") == "对比页":
            artifact = build_comparison_page_artifact(page, workflow, context)
        else:
            artifact = build_generic_page_artifact(page, workflow, context)
        artifacts.append(artifact)
        publishable_pages.append(
            build_publishable_page(
                kind=artifact.get("kind") or "page_brief",
                slug=artifact.get("slug") or "page-artifact",
                target_path=artifact.get("target_path") or "/",
                page_json=artifact.get("page_json") or {},
                workflow=workflow,
            )
        )
    return {
        "available": bool(artifacts),
        "brand_context": context,
        "page_count": len(artifacts),
        "pages": artifacts,
        "publishable_pages": publishable_pages,
        "frontend_protocol": {
            "version": "2026-06-11",
            "page_template_types": sorted({artifact.get("kind") for artifact in artifacts if artifact.get("kind")}),
            "block_types": sorted(
                {
                    block.get("type")
                    for artifact in artifacts
                    for block in ((artifact.get("frontend_payload") or {}).get("blocks") or [])
                    if block.get("type")
                }
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate page artifacts from a workflow JSON file.")
    parser.add_argument("--workflow-input", required=True)
    parser.add_argument("--brand-name", default="")
    parser.add_argument("--brand-url", default="")
    parser.add_argument("--primary-cta-url", default="")
    parser.add_argument("--primary-cta-label", default="")
    parser.add_argument("--output")
    args = parser.parse_args()

    workflow = json.loads(Path(args.workflow_input).read_text())
    artifacts = build_page_artifacts(
        workflow,
        brand_context=brand_context_payload(
            brand_name=args.brand_name,
            brand_url=args.brand_url,
            primary_cta_url=args.primary_cta_url,
            primary_cta_label=args.primary_cta_label,
        ),
    )
    text = json.dumps(artifacts, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
