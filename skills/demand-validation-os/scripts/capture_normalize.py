#!/usr/bin/env python3
"""Normalize Semrush and Similarweb capture bundles into one shared schema."""

from __future__ import annotations

import re
from typing import Any


COMPACT_MULTIPLIERS = {
    "K": 1_000,
    "M": 1_000_000,
    "B": 1_000_000_000,
    "T": 1_000_000_000_000,
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_compact_number(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value

    text = clean_text(value)
    if not text or "%" in text or "pp" in text.lower():
        return None
    text = text.replace(",", "").replace("$", "").replace("¥", "").replace("€", "")
    match = re.search(r"([+-]?\d+(?:\.\d+)?)([KMBT])?\b", text, re.I)
    if not match:
        return None
    base = float(match.group(1))
    unit = (match.group(2) or "").upper()
    multiplier = COMPACT_MULTIPLIERS.get(unit, 1)
    value_num = base * multiplier
    return int(round(value_num)) if float(value_num).is_integer() else value_num


def parse_percent(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"[+-]?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    return float(match.group(0))


def parse_rank(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"#?(\d+)", text.replace(",", ""))
    return int(match.group(1)) if match else None


def change_fields(value: Any) -> dict[str, float | None]:
    text = clean_text(value)
    if not text:
        return {
            "change_percent": None,
            "change_pp": None,
        }
    parsed = parse_percent(text)
    lowered = text.lower()
    return {
        "change_percent": parsed if "%" in lowered else None,
        "change_pp": parsed if "pp" in lowered else None,
    }


def normalize_url(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if text.startswith(("http://", "https://")):
        return text
    if re.fullmatch(r"(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/.*)?", text):
        return f"https://{text.lstrip('/')}"
    return text


def coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def result_meta(bundle: dict[str, Any], tool: str) -> dict[str, Any]:
    return bundle.get("results", {}).get(tool, {}).get("best_attempt", {}) or {}


def semrush_tool_signals(bundle: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    meta = result_meta(bundle, "semrush")
    overview = data.get("domain_overview") or {}
    backlink = data.get("backlink_overview") or {}
    return {
        "available": bool(data),
        "core_ready": bool(meta.get("quality", {}).get("core_ready")),
        "status": meta.get("status"),
        "quality_reasons": meta.get("quality", {}).get("reasons", []),
        "database": overview.get("database"),
        "snapshot_date": overview.get("snapshot_date"),
        "top_page_count": len(data.get("top_pages") or []),
        "top_keyword_count": len(data.get("top_organic_keywords") or []),
        "competitor_count": len(data.get("organic_competitors") or []),
        "topic_count": len(data.get("top_topics") or []),
        "referring_domains": backlink.get("referring_domains"),
    }


def similarweb_tool_signals(bundle: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    meta = result_meta(bundle, "similarweb")
    evidence = data.get("website_evidence") or {}
    performance = evidence.get("website_performance") or {}
    keyword_research = evidence.get("keyword_research") or {}
    landing_research = evidence.get("landing_pages_research") or {}
    home_signals = evidence.get("home_signals") or {}
    brand_mix = ((evidence.get("search_overview") or {}).get("summary") or {}).get("brand_vs_non_brand") or {}
    return {
        "available": bool(data),
        "core_ready": bool(meta.get("quality", {}).get("core_ready")),
        "status": meta.get("status"),
        "quality_reasons": meta.get("quality", {}).get("reasons", []),
        "route_navigation_used": evidence.get("report_navigation_used"),
        "website_performance_ready": bool(performance.get("available")),
        "keyword_research_readiness": keyword_research.get("readiness"),
        "landing_pages_research_readiness": landing_research.get("readiness"),
        "top_page_count": len((((evidence.get("website_content_top_pages") or {}).get("summary") or {}).get("rows") or [])),
        "keyword_count": len((((keyword_research.get("top_non_brand_keywords") or {}).get("rows") or []))),
        "landing_page_count": len((((landing_research.get("paid_landing_pages") or {}).get("rows") or []))),
        "folder_count": len(landing_research.get("folder_rows") or []),
        "priority_alert_count": len(home_signals.get("priority_alerts") or []),
        "seed_keywords": (keyword_research.get("quick_search_keywords") or [])[:10],
        "keyword_research_row_counts": keyword_research.get("row_counts") or {},
        "landing_pages_research_row_counts": landing_research.get("row_counts") or {},
        "branded_share_percent": parse_percent(brand_mix.get("branded")),
        "non_branded_share_percent": parse_percent(brand_mix.get("non_branded")),
    }


def build_semrush_top_pages(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in data.get("top_pages") or []:
        rows.append(
            {
                "url": normalize_url(coalesce(row.get("url"), row.get("visible_url"))),
                "title": row.get("title"),
                "page_kind": "organic_top_page",
                "traffic_estimate": parse_compact_number(row.get("traffic")),
                "traffic_share_percent": parse_percent(row.get("traffic_percent")),
                "traffic_cost_estimate": parse_compact_number(row.get("traffic_cost")),
                "top_keyword": row.get("top_keyword"),
                "keyword_volume": parse_compact_number(row.get("volume")),
                "position": parse_compact_number(row.get("position")),
                "source_tool": "semrush",
                "source_section": "top_pages",
            }
        )
    return rows


def build_similarweb_top_pages(data: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = data.get("website_evidence") or {}
    rows = ((((evidence.get("website_content_top_pages") or {}).get("summary") or {}).get("rows")) or [])
    normalized = []
    for row in rows:
        change = change_fields(row.get("month_over_month_change"))
        normalized.append(
            {
                "url": normalize_url(row.get("url")),
                "title": None,
                "page_kind": "popular_page",
                "traffic_estimate": None,
                "traffic_share_percent": parse_percent(row.get("share")),
                "traffic_change_percent": change["change_percent"],
                "traffic_change_pp": change["change_pp"],
                "traffic_cost_estimate": None,
                "top_keyword": None,
                "keyword_volume": None,
                "position": parse_compact_number(row.get("rank")),
                "source_tool": "similarweb",
                "source_section": "website_content_top_pages",
            }
        )
    return normalized


def build_semrush_top_keywords(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in data.get("top_organic_keywords") or []:
        rows.append(
            {
                "keyword": row.get("keyword"),
                "keyword_kind": "organic",
                "search_channel": "organic",
                "position": parse_compact_number(row.get("position")),
                "position_change": parse_compact_number(row.get("position_difference")),
                "volume": parse_compact_number(row.get("volume")),
                "traffic_estimate": parse_compact_number(row.get("traffic")),
                "traffic_share_percent": parse_percent(row.get("traffic_percent")),
                "traffic_cost_estimate": parse_compact_number(row.get("traffic_cost")),
                "keyword_difficulty": parse_compact_number(row.get("keyword_difficulty")),
                "organic_share_percent": None,
                "paid_share_percent": None,
                "url": normalize_url(row.get("url")),
                "intent_codes": row.get("intent_codes") or [],
                "source_tool": "semrush",
                "source_section": "top_organic_keywords",
            }
        )
    return rows


def build_similarweb_top_keywords(data: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = data.get("website_evidence") or {}
    rows = ((((evidence.get("keyword_research") or {}).get("top_non_brand_keywords") or {}).get("rows")) or [])
    normalized = []
    for row in rows:
        normalized.append(
            {
                "keyword": row.get("keyword"),
                "keyword_kind": "non_brand",
                "search_channel": "mixed",
                "position": None,
                "position_change": None,
                "volume": None,
                "traffic_estimate": parse_compact_number(row.get("clicks")),
                "traffic_share_percent": parse_percent(row.get("share")),
                "traffic_change_percent": parse_percent(row.get("year_over_year_change")),
                "traffic_cost_estimate": None,
                "keyword_difficulty": None,
                "organic_share_percent": parse_percent(row.get("organic_share")),
                "paid_share_percent": parse_percent(row.get("paid_share")),
                "url": None,
                "intent_codes": [],
                "source_tool": "similarweb",
                "source_section": "keyword_research.top_non_brand_keywords",
            }
        )
    return normalized


def build_similarweb_landing_pages(data: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = data.get("website_evidence") or {}
    landing = evidence.get("landing_pages_research") or {}
    normalized = []

    for row in ((((landing.get("top_pages") or {}).get("summary") or {}).get("rows")) or []):
        change = change_fields(row.get("month_over_month_change"))
        normalized.append(
            {
                "url": normalize_url(row.get("url")),
                "landing_type": "popular_page",
                "clicks_estimate": None,
                "traffic_share_percent": parse_percent(row.get("share")),
                "traffic_change_percent": change["change_percent"],
                "traffic_change_pp": change["change_pp"],
                "top_keyword": None,
                "new_keyword_count": None,
                "source_tool": "similarweb",
                "source_section": "landing_pages_research.top_pages",
            }
        )

    for row in (((landing.get("paid_landing_pages") or {}).get("rows")) or []):
        change = change_fields(row.get("month_over_month_change"))
        top_keyword = row.get("top_keyword")
        keyword_text = top_keyword.get("keyword") if isinstance(top_keyword, dict) else top_keyword
        new_keyword_count = top_keyword.get("new_keywords") if isinstance(top_keyword, dict) else None
        normalized.append(
            {
                "url": normalize_url(row.get("url")),
                "landing_type": "paid_landing_page",
                "clicks_estimate": parse_compact_number(row.get("clicks")),
                "traffic_share_percent": parse_percent(row.get("share")),
                "traffic_change_percent": change["change_percent"],
                "traffic_change_pp": change["change_pp"],
                "top_keyword": keyword_text,
                "new_keyword_count": parse_compact_number(new_keyword_count),
                "source_tool": "similarweb",
                "source_section": "landing_pages_research.paid_landing_pages",
            }
        )

    return normalized


def build_page_clusters(semrush_data: dict[str, Any], similarweb_data: dict[str, Any]) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []

    for row in semrush_data.get("top_topics") or []:
        clusters.append(
            {
                "cluster_type": "topic",
                "label": row.get("topic"),
                "traffic_estimate": parse_compact_number(row.get("traffic")),
                "traffic_share_percent": None,
                "traffic_change_percent": None,
                "traffic_change_pp": None,
                "keyword_count": parse_compact_number(row.get("keywords_count")),
                "top_page_url": normalize_url(row.get("top_page_url")),
                "top_keyword": row.get("top_page_keyword"),
                "source_tool": "semrush",
                "source_section": "top_topics",
            }
        )

    evidence = similarweb_data.get("website_evidence") or {}
    for row in (((evidence.get("landing_pages_research") or {}).get("folder_rows")) or []):
        change = change_fields(row.get("month_over_month_change"))
        clusters.append(
            {
                "cluster_type": "folder",
                "label": row.get("folder"),
                "traffic_estimate": None,
                "traffic_share_percent": parse_percent(row.get("share")),
                "traffic_change_percent": change["change_percent"],
                "traffic_change_pp": change["change_pp"],
                "keyword_count": None,
                "top_page_url": None,
                "top_keyword": None,
                "source_tool": "similarweb",
                "source_section": "landing_pages_research.folder_rows",
            }
        )

    return clusters


def build_competitors(semrush_data: dict[str, Any], similarweb_data: dict[str, Any]) -> list[dict[str, Any]]:
    competitors: list[dict[str, Any]] = []

    for row in semrush_data.get("organic_competitors") or []:
        competitors.append(
            {
                "domain": row.get("domain"),
                "relation": "organic_competitor",
                "common_keywords": parse_compact_number(row.get("common_keywords")),
                "competition_level": row.get("competition_level"),
                "organic_positions": parse_compact_number(row.get("organic_positions")),
                "organic_traffic_estimate": parse_compact_number(row.get("organic_traffic")),
                "traffic_estimate": parse_compact_number(row.get("traffic")),
                "traffic_cost_estimate": parse_compact_number(row.get("traffic_cost")),
                "source_tool": "semrush",
                "source_section": "organic_competitors",
            }
        )

    evidence = similarweb_data.get("website_evidence") or {}
    for row in evidence.get("similar_sites") or []:
        if isinstance(row, str):
            domain = row
            extras: dict[str, Any] = {}
        else:
            domain = coalesce(
                row.get("domain"),
                row.get("site"),
                row.get("name"),
                row.get("url"),
                row.get("host"),
            )
            extras = row
        if not domain:
            continue
        competitors.append(
            {
                "domain": clean_text(domain),
                "relation": "similar_site",
                "common_keywords": parse_compact_number(extras.get("commonKeywords")),
                "competition_level": extras.get("competitionLevel"),
                "organic_positions": parse_compact_number(extras.get("organicPositions")),
                "organic_traffic_estimate": parse_compact_number(extras.get("organicTraffic")),
                "traffic_estimate": parse_compact_number(coalesce(extras.get("visits"), extras.get("traffic"))),
                "traffic_cost_estimate": parse_compact_number(extras.get("trafficCost")),
                "source_tool": "similarweb",
                "source_section": "similar_sites",
            }
        )

    return competitors


def build_geo_signals(semrush_data: dict[str, Any], similarweb_data: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []

    for row in semrush_data.get("markets_current") or []:
        signals.append(
            {
                "location": row.get("database"),
                "signal_type": "database_market",
                "traffic_share_percent": None,
                "organic_traffic_estimate": parse_compact_number(row.get("organic_traffic")),
                "organic_branded_traffic_estimate": parse_compact_number(row.get("organic_traffic_branded")),
                "organic_non_branded_traffic_estimate": parse_compact_number(row.get("organic_traffic_non_branded")),
                "paid_traffic_estimate": parse_compact_number(row.get("paid_traffic")),
                "rank": parse_rank(row.get("rank")),
                "change_percent": None,
                "source_tool": "semrush",
                "source_section": "markets_current",
            }
        )

    evidence = similarweb_data.get("website_evidence") or {}
    top_countries = (((evidence.get("website_performance") or {}).get("top_countries")) or {}).get("rows") or []
    for row in top_countries:
        signals.append(
            {
                "location": row.get("country"),
                "signal_type": "country_share",
                "traffic_share_percent": parse_percent(row.get("share")),
                "organic_traffic_estimate": None,
                "organic_branded_traffic_estimate": None,
                "organic_non_branded_traffic_estimate": None,
                "paid_traffic_estimate": None,
                "rank": None,
                "change_percent": parse_percent(row.get("change")),
                "source_tool": "similarweb",
                "source_section": "website_performance.top_countries",
            }
        )

    return signals


def build_traffic_summary(semrush_data: dict[str, Any], similarweb_data: dict[str, Any]) -> dict[str, Any]:
    semrush_overview = semrush_data.get("domain_overview") or {}
    evidence = similarweb_data.get("website_evidence") or {}
    performance = evidence.get("website_performance") or {}
    total_visits = performance.get("total_visits") or {}
    channels = (performance.get("traffic_channels") or {}).get("rows") or []
    top_countries = (performance.get("top_countries") or {}).get("rows") or []
    organic_search = performance.get("organic_search") or {}
    paid_search = performance.get("paid_search") or {}

    return {
        "monthly_visits_estimate": parse_compact_number(total_visits.get("visits")),
        "monthly_visits_source": "similarweb.website_performance.total_visits.visits" if total_visits.get("visits") else None,
        "visits_date_range": total_visits.get("date_range"),
        "visits_geography": total_visits.get("geography"),
        "visits_change_percent": parse_percent(total_visits.get("change_pct")),
        "organic_traffic_estimate": parse_compact_number(semrush_overview.get("organic_traffic")),
        "organic_traffic_source": "semrush.domain_overview.organic_traffic" if semrush_overview.get("organic_traffic") is not None else None,
        "paid_traffic_estimate": parse_compact_number(semrush_overview.get("paid_traffic")),
        "paid_traffic_source": "semrush.domain_overview.paid_traffic" if semrush_overview.get("paid_traffic") is not None else None,
        "organic_share_percent": parse_percent(organic_search.get("share_of_traffic")),
        "paid_share_percent": parse_percent(paid_search.get("share_of_traffic")),
        "global_rank": coalesce(
            parse_rank(((performance.get("ranks") or {}).get("global_rank"))),
            parse_rank(semrush_overview.get("global_rank")),
        ),
        "global_rank_source": (
            "similarweb.website_performance.ranks.global_rank"
            if ((performance.get("ranks") or {}).get("global_rank"))
            else "semrush.domain_overview.global_rank"
            if semrush_overview.get("global_rank") is not None
            else None
        ),
        "top_country_shares": [
            {
                "location": row.get("country"),
                "share_percent": parse_percent(row.get("share")),
                "change_percent": parse_percent(row.get("change")),
            }
            for row in top_countries
        ],
        "channel_mix": [
            {
                "channel": row.get("channel"),
                "share_percent": parse_percent(row.get("share")),
            }
            for row in channels
        ],
    }


def build_notes(bundle: dict[str, Any]) -> list[str]:
    summary = bundle.get("summary", {}) or {}
    notes = [
        "All Similarweb and Semrush traffic metrics remain third-party estimates.",
        "Normalized output is additive; raw capture payloads remain under results.<tool>.data.",
    ]
    if summary.get("partial_tools"):
        notes.append(f"Partial tools: {', '.join(summary.get('partial_tools') or [])}.")
    if summary.get("failed_tools"):
        notes.append(f"Failed tools: {', '.join(summary.get('failed_tools') or [])}.")
    return notes


def build_normalized_capture(bundle: dict[str, Any]) -> dict[str, Any]:
    request = bundle.get("request") or {}
    query = request.get("query") or {}
    results = bundle.get("results") or {}
    semrush_data = (results.get("semrush") or {}).get("data") or {}
    similarweb_data = (results.get("similarweb") or {}).get("data") or {}
    summary = bundle.get("summary") or {}
    requested_tools = request.get("tools") or []
    attempted_tools = list(results.keys())
    ready_tools = summary.get("core_ready_tools") or []

    if requested_tools and len(ready_tools) == len(requested_tools):
        coverage_status = "ok"
    elif attempted_tools:
        coverage_status = "partial"
    else:
        coverage_status = "error"

    return {
        "query": {
            "type": query.get("type") or "domain",
            "value": query.get("value"),
        },
        "tools_requested": requested_tools,
        "tools_attempted": attempted_tools,
        "tools_ready": ready_tools,
        "coverage": {
            "status": coverage_status,
            "requested_tools": requested_tools,
            "attempted_tools": attempted_tools,
            "ready_tools": ready_tools,
            "partial_tools": summary.get("partial_tools") or [],
            "failed_tools": summary.get("failed_tools") or [],
        },
        "traffic_summary": build_traffic_summary(semrush_data, similarweb_data),
        "top_pages": build_semrush_top_pages(semrush_data) + build_similarweb_top_pages(similarweb_data),
        "top_keywords": build_semrush_top_keywords(semrush_data) + build_similarweb_top_keywords(similarweb_data),
        "landing_pages": build_similarweb_landing_pages(similarweb_data),
        "page_clusters": build_page_clusters(semrush_data, similarweb_data),
        "competitors": build_competitors(semrush_data, similarweb_data),
        "geo_signals": build_geo_signals(semrush_data, similarweb_data),
        "tool_signals": {
            "semrush": semrush_tool_signals(bundle, semrush_data),
            "similarweb": similarweb_tool_signals(bundle, similarweb_data),
        },
        "notes": build_notes(bundle),
    }
