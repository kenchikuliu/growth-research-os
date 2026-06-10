#!/usr/bin/env python3
"""Capture Semrush domain evidence from a logged-in 3ue browser session."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from browser_capture import ThreeUEExecutor, iso_utc_now, load_network_entries


def find_first(entries: list[dict[str, Any]], needle: str) -> Any:
    for entry in entries:
        if needle in entry["request"].get("url", ""):
            return entry["parsed_body"]
    return None


def flatten_rpc_results(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for entry in entries:
        if "dpa/rpc" not in entry["request"].get("url", ""):
            continue
        body = entry["parsed_body"]
        items = body if isinstance(body, list) else [body]
        for item in items:
            if not isinstance(item, dict) or "result" not in item:
                continue
            results.append(
                {
                    "entry_dir": entry["dir"],
                    "id": item.get("id"),
                    "result": item.get("result"),
                }
            )
    return results


def is_dict_with_keys(value: Any, keys: set[str]) -> bool:
    return isinstance(value, dict) and keys.issubset(value.keys())


def first_list_row(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return None


def classify_rpc_results(rpc_results: list[dict[str, Any]]) -> dict[str, Any]:
    classified: dict[str, Any] = {
        "is_root_domain": None,
        "anchor_backlink_profile": None,
        "organic_competitors": [],
        "competitor_intersections": [],
        "top_organic_keywords": [],
        "top_pages": [],
        "database_trend_daily": [],
        "database_trend_monthly": [],
        "domain_trend_daily": [],
        "domain_trend_monthly": [],
        "keyword_distribution": None,
        "market_samples_current": [],
        "market_samples_snapshot": [],
        "backlink_overview": None,
        "ai_overview": None,
        "ai_sources": None,
        "ai_countries": [],
        "top_topics": None,
        "unclassified_ids": [],
    }

    for item in rpc_results:
        rid = item.get("id")
        result = item.get("result")

        if is_dict_with_keys(result, {"isRootDomain"}):
            classified["is_root_domain"] = result
            continue
        if is_dict_with_keys(result, {"authorityScore", "backlinks", "anchors", "referralDomains"}):
            classified["anchor_backlink_profile"] = result
            continue
        if is_dict_with_keys(result, {"authorityScore", "backlinks", "referringDomains", "health"}):
            classified["backlink_overview"] = result
            continue
        if is_dict_with_keys(result, {"ai_visibility", "ai_visibility_benchmark", "cited_pages", "mention_stats"}):
            classified["ai_overview"] = result
            continue
        if is_dict_with_keys(result, {"sources"}):
            classified["ai_sources"] = result
            continue
        if is_dict_with_keys(result, {"keyword", "position", "totalPositions"}):
            classified["keyword_distribution"] = result
            continue
        if is_dict_with_keys(result, {"status", "target", "topics"}):
            classified["top_topics"] = result
            continue

        row = first_list_row(result)
        if row is None:
            classified["unclassified_ids"].append(rid)
            continue

        row_keys = set(row.keys())

        if {"database", "mentions", "visibility"}.issubset(row_keys):
            classified["ai_countries"] = result
            continue
        if {"domain", "commonKeywords", "organicTraffic", "organicPositions", "positions"}.issubset(row_keys):
            classified["organic_competitors"] = result
            continue
        if {"domain", "commonKeywords", "traffic", "trafficCost"}.issubset(row_keys) and "organicTraffic" not in row_keys:
            classified["competitor_intersections"] = result
            continue
        if {"phrase", "position", "volume", "trafficPercent", "url"}.issubset(row_keys) and "title" not in row_keys:
            classified["top_organic_keywords"] = result
            continue
        if {"title", "description", "phrase", "visibleUrl", "trafficPercent"}.issubset(row_keys):
            classified["top_pages"] = result
            continue
        if {"database", "organicTraffic", "traffic", "rank"}.issubset(row_keys):
            if rid == 18 or not classified["market_samples_current"]:
                classified["market_samples_current"] = result
            else:
                classified["market_samples_snapshot"] = result
            continue
        if {"date", "organicTraffic", "traffic", "rank", "organicPositions"}.issubset(row_keys):
            if rid == 13 or (len(result) >= 300 and not classified["database_trend_daily"]):
                classified["database_trend_daily"] = result
            elif rid == 14 or (len(result) < 300 and not classified["database_trend_monthly"]):
                classified["database_trend_monthly"] = result
            elif rid == 15 or (len(result) >= 300 and not classified["domain_trend_daily"]):
                classified["domain_trend_daily"] = result
            elif rid == 16 or (len(result) < 300 and not classified["domain_trend_monthly"]):
                classified["domain_trend_monthly"] = result
            else:
                classified["unclassified_ids"].append(rid)
            continue

        classified["unclassified_ids"].append(rid)

    return classified


def pick_market_row(rows: list[dict[str, Any]], database: str) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("database") == database), None)


def normalize_competitor_rows(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    normalized = []
    for row in rows[:limit]:
        normalized.append(
            {
                "domain": row.get("domain"),
                "common_keywords": row.get("commonKeywords"),
                "competition_level": row.get("competitionLvl"),
                "organic_positions": row.get("organicPositions"),
                "organic_traffic": row.get("organicTraffic"),
                "organic_traffic_cost": row.get("organicTrafficCost"),
                "traffic": row.get("traffic"),
                "traffic_cost": row.get("trafficCost"),
            }
        )
    return normalized


def normalize_intersection_rows(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    normalized = []
    for row in rows[:limit]:
        normalized.append(
            {
                "domain": row.get("domain"),
                "common_keywords": row.get("commonKeywords"),
                "competition_level": row.get("competitionLvl"),
                "organic_positions": row.get("organicPositions"),
                "traffic": row.get("traffic"),
                "traffic_cost": row.get("trafficCost"),
            }
        )
    return normalized


def normalize_keyword_rows(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    normalized = []
    for row in rows[:limit]:
        normalized.append(
            {
                "keyword": row.get("phrase"),
                "position": row.get("position"),
                "position_difference": row.get("positionDifference"),
                "volume": row.get("volume"),
                "traffic": row.get("traffic"),
                "traffic_percent": row.get("trafficPercent"),
                "traffic_cost": row.get("trafficCost"),
                "keyword_difficulty": row.get("keywordDifficulty"),
                "intent_codes": row.get("intents", []),
                "url": row.get("url"),
            }
        )
    return normalized


def normalize_page_rows(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    normalized = []
    for row in rows[:limit]:
        normalized.append(
            {
                "title": row.get("title"),
                "description": row.get("description"),
                "url": row.get("url"),
                "visible_url": row.get("visibleUrl"),
                "top_keyword": row.get("phrase"),
                "position": row.get("position"),
                "traffic": row.get("traffic"),
                "traffic_percent": row.get("trafficPercent"),
                "traffic_cost": row.get("trafficCost"),
                "volume": row.get("volume"),
            }
        )
    return normalized


def normalize_topic_rows(top_topics: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    rows = []
    for topic in top_topics.get("topics", [])[:limit]:
        top_page = topic.get("pages", [{}])[0] if topic.get("pages") else {}
        top_keyword = (top_page.get("top_keywords") or [{}])[0]
        rows.append(
            {
                "topic": topic.get("name"),
                "keywords_count": topic.get("keywords_count"),
                "traffic": topic.get("traffic"),
                "top_page_url": top_keyword.get("url"),
                "top_page_keyword": top_keyword.get("keyword"),
                "top_page_volume": top_keyword.get("volume"),
                "top_page_traffic": top_keyword.get("traffic"),
            }
        )
    return rows


def normalize_market_rows(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    normalized = []
    for row in rows[:limit]:
        normalized.append(
            {
                "database": row.get("database"),
                "rank": row.get("rank"),
                "organic_positions": row.get("organicPositions"),
                "organic_traffic": row.get("organicTraffic"),
                "organic_traffic_branded": row.get("organicTrafficBranded"),
                "organic_traffic_non_branded": row.get("organicTrafficNonBranded"),
                "paid_traffic": row.get("adwordsTraffic"),
                "paid_positions": row.get("adwordsPositions"),
                "traffic": row.get("traffic"),
                "traffic_cost": row.get("trafficCost"),
            }
        )
    return normalized


def normalize_trend_rows(rows: list[dict[str, Any]], limit: int = 24) -> list[dict[str, Any]]:
    normalized = []
    for row in rows[:limit]:
        normalized.append(
            {
                "date": row.get("date"),
                "rank": row.get("rank"),
                "organic_positions": row.get("organicPositions"),
                "organic_traffic": row.get("organicTraffic"),
                "organic_traffic_branded": row.get("organicTrafficBranded"),
                "organic_traffic_non_branded": row.get("organicTrafficNonBranded"),
                "paid_positions": row.get("adwordsPositions"),
                "paid_traffic": row.get("adwordsTraffic"),
                "traffic": row.get("traffic"),
                "traffic_cost": row.get("trafficCost"),
                "ai_overview_positions": row.get("aiOverviewPositions"),
            }
        )
    return normalized


def build_notes(classified: dict[str, Any]) -> list[str]:
    notes = [
        "Semrush domain overview route was opened directly under an authenticated 3ue session.",
        "DPA RPC responses were classified by payload shape, not by unstable RPC id alone.",
    ]
    if classified["unclassified_ids"]:
        notes.append(f"Unclassified RPC ids: {sorted(set(x for x in classified['unclassified_ids'] if x is not None))}")
    return notes


def open_semrush_overview(
    executor: Any, query: str, network_dir: str
) -> tuple[str, str, str, list[dict[str, Any]], list[dict[str, Any]], int]:
    route = f"https://sem.3ue.com/analytics/overview/?q={query}&searchType=domain"
    page_url = ""
    page_title = ""
    entries: list[dict[str, Any]] = []
    rpc_results: list[dict[str, Any]] = []
    attempts_used = 0

    for attempt in range(1, 3):
        attempts_used = attempt
        if attempt > 1:
            executor.ensure_home()
            executor.browser.wait_timeout(2)
            network_dir = executor.browser.network_clear()
        executor.browser.open(route)
        executor.browser.wait_timeout(12)
        page_url = executor.browser.try_current_url() or route
        page_title = executor.browser.try_current_title()
        entries = load_network_entries(network_dir)
        rpc_results = flatten_rpc_results(entries)
        if rpc_results:
            break
    return page_url, page_title, network_dir, entries, rpc_results, attempts_used


def collect(query: str, username: str, password: str, session: str, keep_session: bool = False) -> dict[str, Any]:
    executor = ThreeUEExecutor(username=username, password=password, session=session)
    try:
        executor.reset_session()
        login = executor.login()
        executor.browser.network_on()
        network_dir = executor.browser.network_clear()
        executor.ensure_home()
        executor.browser.wait_timeout(2)

        page_url, page_title, network_dir, entries, rpc_results, attempts_used = open_semrush_overview(
            executor, query, network_dir
        )
        subscription_context = executor.get_subscription_context()
        classified = classify_rpc_results(rpc_results)

        search_bar_context = find_first(entries, "search-bar/api/search?")
        current_market = pick_market_row(classified["market_samples_current"], "us") or {}
        latest_database_daily = classified["database_trend_daily"][-1] if classified["database_trend_daily"] else {}
        latest_domain_daily = classified["domain_trend_daily"][-1] if classified["domain_trend_daily"] else {}
        backlink_overview = classified["backlink_overview"] or {}
        anchor_backlink_profile = classified["anchor_backlink_profile"] or {}
        ai_overview = classified["ai_overview"] or {}
        ai_sources = classified["ai_sources"] or {}
        top_topics = classified["top_topics"] or {}
        auditing = subscription_context.get("auditing") or {}
        auditing_items = auditing.get("data", []) if isinstance(auditing, dict) else []
        fallback_snapshot_date = auditing_items[0].get("date") if auditing_items else None

        output = {
            "tool": "semrush",
            "query": {"type": "domain", "value": query},
            "source": {
                "provider": "3ue",
                "dashboard": "https://dash.3ue.com/zh-Hans/#/page/m/home",
                "tool_url": page_url,
                "captured_at": iso_utc_now(),
            },
            "account_context": {
                "login": login,
                "subscription": subscription_context.get("subscription"),
                "auditing": auditing,
            },
            "capture_method": {
                "login": "automated_3ue_login",
                "primary": "network",
                "fallback": "dom",
            },
            "raw_artifacts": {
                "network_dir": network_dir,
                "overview_attempts": attempts_used,
                "rpc_result_count": len(rpc_results),
                "notes": build_notes(classified)
                + (["Semrush overview route was retried because the first pass returned no RPC payloads."] if attempts_used > 1 else [])
                + (["Browser session was closed automatically after capture."] if not keep_session else []),
            },
            "domain_overview": {
                "domain": query,
                "database": "us",
                "snapshot_date": latest_database_daily.get("date") or fallback_snapshot_date,
                "page_title": page_title,
                "is_root_domain": classified["is_root_domain"].get("isRootDomain") if classified["is_root_domain"] else None,
                "authority_score": backlink_overview.get("authorityScore"),
                "organic_traffic": current_market.get("organicTraffic"),
                "organic_traffic_branded": current_market.get("organicTrafficBranded"),
                "organic_traffic_non_branded": current_market.get("organicTrafficNonBranded"),
                "paid_traffic": current_market.get("adwordsTraffic"),
                "organic_positions": current_market.get("organicPositions"),
                "adwords_positions": current_market.get("adwordsPositions"),
                "organic_keywords": classified["keyword_distribution"].get("totalPositions") if classified["keyword_distribution"] else None,
                "traffic": current_market.get("traffic"),
                "backlinks": backlink_overview.get("backlinks"),
                "referring_domains": backlink_overview.get("referringDomains"),
                "global_rank": current_market.get("rank"),
            },
            "search_bar_context": search_bar_context,
            "organic_competitors": normalize_competitor_rows(classified["organic_competitors"]),
            "competitor_intersections": normalize_intersection_rows(classified["competitor_intersections"]),
            "top_organic_keywords": normalize_keyword_rows(classified["top_organic_keywords"]),
            "top_pages": normalize_page_rows(classified["top_pages"]),
            "database_trend_daily": normalize_trend_rows(classified["database_trend_daily"]),
            "database_trend_monthly": normalize_trend_rows(classified["database_trend_monthly"]),
            "domain_trend_daily": normalize_trend_rows(classified["domain_trend_daily"]),
            "domain_trend_monthly": normalize_trend_rows(classified["domain_trend_monthly"]),
            "keyword_distribution": classified["keyword_distribution"],
            "top_topics": normalize_topic_rows(top_topics),
            "markets_current": normalize_market_rows(classified["market_samples_current"]),
            "markets_snapshot": normalize_market_rows(classified["market_samples_snapshot"]),
            "ai_overview": {
                "visibility": ai_overview.get("ai_visibility"),
                "visibility_benchmark": ai_overview.get("ai_visibility_benchmark"),
                "cited_pages": ai_overview.get("cited_pages"),
                "mention_stats": ai_overview.get("mention_stats", []),
                "sources": ai_sources.get("sources", []),
                "country_breakdown": classified["ai_countries"][:20],
            },
            "backlink_overview": {
                "authority_score": backlink_overview.get("authorityScore"),
                "backlinks": backlink_overview.get("backlinks"),
                "health": backlink_overview.get("health"),
                "link_power": backlink_overview.get("linkPower"),
                "naturalness": backlink_overview.get("naturalness"),
                "referring_domains": backlink_overview.get("referringDomains"),
                "top_anchors": anchor_backlink_profile.get("anchors", [])[:10],
                "top_referral_domains": anchor_backlink_profile.get("referralDomains", [])[:10],
                "top_pages": anchor_backlink_profile.get("pages", [])[:10],
            },
            "debug": {
                "latest_database_daily": latest_database_daily,
                "latest_domain_daily": latest_domain_daily,
            },
        }
        return output
    finally:
        if not keep_session:
            executor.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture Semrush domain evidence into structured JSON.")
    parser.add_argument("--query", required=True, help="Domain to analyze")
    parser.add_argument("--username", default=os.environ.get("THREEUE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("THREEUE_PASSWORD", ""))
    parser.add_argument("--session", default="dvos-sem")
    parser.add_argument("--output", help="Write JSON to a file")
    parser.add_argument("--keep-session", action="store_true", help="Keep the browse session open after capture")
    args = parser.parse_args()

    if not args.username or not args.password:
        raise SystemExit("Missing 3ue credentials. Set THREEUE_USERNAME and THREEUE_PASSWORD or pass --username/--password.")

    data = collect(args.query, args.username, args.password, args.session, keep_session=args.keep_session)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
