#!/usr/bin/env python3
"""Capture Similarweb account and report evidence from a logged-in 3ue session."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from browser_capture import BrowseError, ThreeUEExecutor, iso_utc_now, load_network_entries


WEBSITE_PERFORMANCE_ROUTE_FRAGMENT = "/websiteanalysis/overview/website-performance/"
ACTIVATION_HOME_FRAGMENT = "/#/activation/home"
DIGITALSUITE_HOME_FRAGMENT = "/#/digitalsuite/home"
SEARCH_BOX_TEXT = "搜索任何网站、关键词或报告"
PRIORITY_ALERT_HEADER_RE = re.compile(
    r"^(?P<domain>[^\s]+)有\s+(?P<count>\d+)\s+个新 Organic (?P<metric>landing pages|keywords)\s*(?P<summary>.*)$",
    re.S,
)
PRIORITY_ALERT_INLINE_RE = re.compile(r"[^\n]*有\s+\d+\s+个新 Organic (?:landing pages|keywords)[^\n]*")


def find_first(entries: list[dict[str, Any]], needle: str) -> Any:
    for entry in entries:
        if needle in entry["request"].get("url", ""):
            return entry["parsed_body"]
    return None


def first_non_null(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def non_empty_lines(text: str | None) -> list[str]:
    if not text:
        return []
    return [line.strip() for line in text.replace("\u00a0", " ").splitlines() if line.strip()]


def looks_like_percent(value: str) -> bool:
    return "%" in value


def normalize_website_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "blocked": 1 in item.get("blockStatus", []),
            }
        )
    return normalized


def build_website_performance_route(query: str) -> str:
    return (
        "/#/digitalsuite/websiteanalysis/overview/website-performance/"
        f"*/999/3m?webSource=Total&key={quote(query, safe='')}"
    )


def extract_shell_markers(snapshot: Any, body_text: str, eval_state: Any) -> dict[str, Any]:
    tree = snapshot.get("tree", "") if isinstance(snapshot, dict) else ""
    quick_marker = SEARCH_BOX_TEXT in tree or SEARCH_BOX_TEXT in body_text or "快速搜索" in tree or "快速搜索" in body_text
    activation_marker = "优先提醒" in tree or "最近活动" in tree or "优先提醒" in body_text or "最近活动" in body_text
    eval_dict = eval_state if isinstance(eval_state, dict) else {}
    return {
        "tree_has_search_box": SEARCH_BOX_TEXT in tree,
        "body_has_search_box": SEARCH_BOX_TEXT in body_text,
        "tree_has_quick_search": "快速搜索" in tree,
        "body_has_activation_alerts": "优先提醒" in body_text,
        "quick_marker": quick_marker,
        "activation_marker": activation_marker,
        "page_frame": bool(eval_dict.get("page_frame")),
        "modal_input": bool(eval_dict.get("modal_input")),
        "quick": bool(eval_dict.get("quick")),
        "react_app": bool(eval_dict.get("react_app")),
    }


def wait_for_similarweb_shell_ready(browser: Any, timeout: int = 60) -> dict[str, Any]:
    deadline = time.time() + timeout
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        url = browser.current_url(timeout=10)
        title = browser.current_title(timeout=10)
        snapshot = browser.try_snapshot(timeout=20)
        body_text = browser.try_get_text("body", timeout=20)
        eval_state = browser.try_eval(
            """
            (() => ({
              href: window.location.href,
              title: document.title,
              quick: !!document.querySelector('[data-automation="quick-search-bar"]'),
              modal_input: !!document.querySelector('input[placeholder*="搜索任何网站、关键词或报告"]'),
              react_app: !!document.querySelector('#react-app'),
              page_frame: !!document.querySelector('[data-automation="page-frame-container"]')
            }))()
            """,
            timeout=8,
        )
        markers = extract_shell_markers(snapshot, body_text, eval_state)
        state = {
            "href": url,
            "title": title,
            "body_excerpt": body_text[:500],
            **markers,
        }
        if isinstance(eval_state, dict):
            state.update(eval_state)
        last_state = state
        if (
            markers["quick_marker"]
            or markers["activation_marker"]
            or markers["page_frame"]
            or markers["modal_input"]
            or ACTIVATION_HOME_FRAGMENT in url
            or DIGITALSUITE_HOME_FRAGMENT in url
        ):
            return state
        time.sleep(1.0)
    raise BrowseError(f"Timed out waiting for Similarweb shell DOM to become ready: {last_state}")


def wait_for_website_performance_ready(browser: Any, timeout: int = 60) -> dict[str, Any]:
    deadline = time.time() + timeout
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        url = browser.current_url(timeout=10)
        title = browser.current_title(timeout=10)
        body_text = browser.try_get_text("body", timeout=20)
        snapshot = browser.try_snapshot(timeout=20)
        tree = snapshot.get("tree", "") if isinstance(snapshot, dict) else ""
        eval_state = browser.try_eval(
            f"""
            (() => {{
              const pageFrame = document.querySelector('[data-automation="page-frame-container"]');
              const totalVisits = document.querySelector('[data-automation="total-visits-widget"]');
              return {{
                href: window.location.href,
                title: document.title,
                page_frame: !!pageFrame,
                total_visits: !!totalVisits,
                body_has_total_visits: (document.body.innerText || '').includes('总访问量'),
              }};
            }})()
            """,
            timeout=8,
        )
        state = {
            "href": url,
            "title": title,
            "body_has_total_visits": "总访问量" in body_text,
            "tree_has_total_visits": "总访问量" in tree,
        }
        if isinstance(eval_state, dict):
            state.update(eval_state)
        last_state = state
        if (
            WEBSITE_PERFORMANCE_ROUTE_FRAGMENT in url
            and (
                state.get("total_visits")
                or state.get("body_has_total_visits")
                or state.get("tree_has_total_visits")
            )
        ):
            return state
        time.sleep(1.0)
    raise BrowseError(f"Timed out waiting for Similarweb website-performance DOM: {last_state}")


def parse_priority_alert_row(raw_text: str) -> dict[str, Any] | None:
    compact = " ".join(non_empty_lines(raw_text))
    if len(re.findall(r"有\s+\d+\s+个新 Organic (?:landing pages|keywords)", compact)) > 1:
        return None
    match = PRIORITY_ALERT_HEADER_RE.match(compact)
    if not match:
        return None
    metric = match.group("metric").strip().lower().replace(" ", "_")
    return {
        "domain": match.group("domain").strip(),
        "new_count": int(match.group("count")),
        "metric": metric,
        "summary": match.group("summary").strip() or None,
    }


def extract_home_signals(browser: Any) -> dict[str, Any]:
    state = browser.try_eval(
        """
        (() => {
          const text = (el) => (el?.innerText || el?.textContent || "").trim();
          const unique = (items) => Array.from(new Set(items.filter(Boolean)));
          const alertRows = unique(
            Array.from(document.querySelectorAll("div"))
              .map((el) => text(el))
              .filter((value) => /有\\s+\\d+\\s+个新 Organic (landing pages|keywords)/i.test(value) && value.length < 2500)
          ).slice(0, 20);
          return {
            href: window.location.href,
            title: document.title,
            alert_rows: alertRows,
          };
        })()
        """,
        timeout=10,
    )
    if not isinstance(state, dict):
        state = {
            "href": browser.current_url(timeout=10),
            "title": browser.current_title(timeout=10),
            "alert_rows": [],
        }
    if not state.get("alert_rows"):
        body_text = browser.try_get_text("body", timeout=20)
        matches = PRIORITY_ALERT_INLINE_RE.findall(body_text)
        state["alert_rows"] = matches[:20]
    alerts = []
    seen: set[tuple[str, int, str, str | None]] = set()
    for row in state.get("alert_rows", []):
        parsed = parse_priority_alert_row(str(row))
        if parsed:
            key = (
                parsed["domain"],
                parsed["new_count"],
                parsed["metric"],
                parsed.get("summary"),
            )
            if key in seen:
                continue
            seen.add(key)
            alerts.append(parsed)
    return {
        "route": state.get("href"),
        "title": state.get("title"),
        "priority_alerts": alerts,
    }


def parse_total_visits(text: str | None) -> dict[str, Any] | None:
    lines = non_empty_lines(text)
    if len(lines) < 4:
        return None
    result: dict[str, Any] = {
        "title": lines[0],
        "date_range": lines[1],
        "geography": lines[2],
        "visits": lines[3],
    }
    if len(lines) > 4:
        result["change_pct"] = lines[4]
    if len(lines) > 5:
        result["change_period"] = lines[5]
    return result


def parse_device_distribution(text: str | None) -> dict[str, Any] | None:
    lines = non_empty_lines(text)
    if len(lines) < 7:
        return None
    split_index = 3
    pairs = []
    values = lines[split_index:]
    for idx in range(0, len(values) - 1, 2):
        pairs.append({"device": values[idx], "share": values[idx + 1]})
    return {
        "title": lines[0],
        "date_range": lines[1],
        "geography": lines[2],
        "breakdown": pairs,
    }


def parse_rank_rows(rows: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for row_text in rows:
        lines = non_empty_lines(row_text)
        if not lines:
            continue
        title = lines[0]
        if title == "全球排名" and len(lines) >= 2:
            parsed["global_rank"] = lines[1]
        elif title == "国家/地区排名" and len(lines) >= 3:
            parsed["country_rank"] = {
                "country": lines[1],
                "rank": lines[2],
            }
        elif title == "行业排名" and len(lines) >= 3:
            parsed["industry_rank"] = {
                "industry": lines[1],
                "rank": lines[2],
            }
    return parsed


def parse_engagement(page_text: str | None) -> dict[str, Any] | None:
    lines = non_empty_lines(page_text)
    try:
        start = lines.index("参与度概览")
    except ValueError:
        return None
    try:
        end = lines.index("See trends over time", start + 1)
    except ValueError:
        end = min(len(lines), start + 20)
    section = lines[start:end]
    if len(section) < 10:
        return None
    metrics: dict[str, Any] = {}
    metric_lines = section[4:]
    for idx in range(0, len(metric_lines) - 1, 2):
        label = metric_lines[idx]
        value = metric_lines[idx + 1]
        metrics[label] = value
    return {
        "title": section[0],
        "date_range": section[1] if len(section) > 1 else None,
        "geography": section[2] if len(section) > 2 else None,
        "traffic_source": section[3] if len(section) > 3 else None,
        "metrics": metrics,
    }


def parse_top_countries(page_text: str | None) -> dict[str, Any] | None:
    lines = non_empty_lines(page_text)
    try:
        start = lines.index("热门国家/地区")
        end = lines.index("流量来源渠道", start + 1)
    except ValueError:
        return None
    section = lines[start:end]
    if "流量份额" not in section:
        return None
    share_index = section.index("流量份额")
    change_index = section.index("变动") if "变动" in section else len(section)
    countries = section[4:share_index]
    shares = section[share_index + 1 : change_index]
    changes = section[change_index + 1 :]
    if changes and changes[-1].startswith("查看更多"):
        changes = changes[:-1]
    rows = []
    for idx, country in enumerate(countries):
        rows.append(
            {
                "country": country,
                "share": shares[idx] if idx < len(shares) else None,
                "change": changes[idx] if idx < len(changes) else None,
            }
        )
    return {
        "title": section[0],
        "date_range": section[1] if len(section) > 1 else None,
        "traffic_source": section[2] if len(section) > 2 else None,
        "rows": rows,
    }


def parse_channel_breakdown(text: str | None) -> dict[str, Any] | None:
    lines = non_empty_lines(text)
    if len(lines) < 10 or "0%" not in lines:
        return None
    tick_index = lines.index("0%")
    labels = lines[3:tick_index]
    values = [line for line in lines[tick_index + 4 :] if not line.startswith("查看")]
    rows = []
    for idx, label in enumerate(labels):
        rows.append({"channel": label, "share": values[idx] if idx < len(values) else None})
    return {
        "date_range": lines[0],
        "geography": lines[1],
        "traffic_source": lines[2],
        "rows": rows,
    }


def parse_share_table(
    text: str | None,
    entity_header: str,
    share_header: str,
    change_header: str | None,
) -> dict[str, Any] | None:
    lines = non_empty_lines(text)
    if not lines or entity_header not in lines or share_header not in lines:
        return None
    entity_index = lines.index(entity_header)
    share_index = lines.index(share_header)
    change_index = lines.index(change_header) if change_header and change_header in lines else len(lines)
    title = lines[0]
    meta = lines[1:entity_index]
    entities = lines[entity_index + 1 : share_index]
    shares = lines[share_index + 1 : change_index]
    changes = lines[change_index + 1 :] if change_index < len(lines) else []
    while changes and (changes[-1].startswith("查看") or changes[-1].startswith("See more")):
        changes.pop()
    rows = []
    for idx, entity in enumerate(entities):
        rows.append(
            {
                "name": entity,
                "share": shares[idx] if idx < len(shares) else None,
                "change": changes[idx] if idx < len(changes) else None,
            }
        )
    result: dict[str, Any] = {
        "title": title,
        "rows": rows,
    }
    if meta:
        result["date_range"] = meta[0]
    if len(meta) > 1:
        result["geography"] = meta[1]
    if len(meta) > 2:
        result["traffic_source"] = meta[2]
    return result


def parse_social_breakdown(text: str | None) -> dict[str, Any] | None:
    lines = non_empty_lines(text)
    if len(lines) < 8 or "0%" not in lines:
        return None
    tick_index = lines.index("0%")
    networks = lines[3:tick_index]
    values = [line for line in lines[tick_index + 3 :] if not line.startswith("查看")]
    rows = []
    for idx, network in enumerate(networks):
        rows.append({"network": network, "share": values[idx] if idx < len(values) else None})
    return {
        "date_range": lines[0],
        "geography": lines[1],
        "traffic_source": lines[2],
        "rows": rows,
    }


def parse_keyword_breakdown(page_text: str | None, section_title: str, next_title: str) -> dict[str, Any] | None:
    lines = non_empty_lines(page_text)
    start = None
    for idx, line in enumerate(lines):
        if line == section_title:
            next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
            if next_line.startswith(f"{section_title}构成网站流量的"):
                start = idx
                break
    if start is None:
        return None
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx] == next_title and idx + 1 < len(lines) and lines[idx + 1].startswith(f"{next_title}构成网站流量的"):
            end = idx
            break
    section = lines[start:end]
    text = "\n".join(section)
    share_match = re.search(rf"{re.escape(section_title)}构成网站流量的\s*([^\n]+)", text)
    result: dict[str, Any] = {
        "share_of_traffic": share_match.group(1).strip() if share_match else None,
        "top_keywords": [],
    }
    if "品牌 vs.非品牌" in section:
        brands_index = section.index("品牌 vs.非品牌")
        brand_lines = section[brands_index + 4 :]
        percentages = [line for line in brand_lines if looks_like_percent(line)]
        if len(percentages) >= 2:
            result["brand_vs_non_brand"] = {
                "branded_share": percentages[0],
                "non_branded_share": percentages[1],
            }
    marker = "热门自然非品牌搜索词" if section_title == "自然搜索" else "热门付费非品牌搜索词"
    if marker in section:
        marker_index = section.index(marker)
        keyword_lines = section[marker_index + 4 :]
        keywords: list[str] = []
        cursor = 0
        while cursor < len(keyword_lines) and not looks_like_percent(keyword_lines[cursor]):
            if not keyword_lines[cursor].startswith("查看") and not keyword_lines[cursor].startswith("更多"):
                keywords.append(keyword_lines[cursor])
            cursor += 1
        metrics = [line for line in keyword_lines[cursor:] if line and not line.startswith("查看更多")]
        shares = metrics[: len(keywords)]
        changes = metrics[len(keywords) : len(keywords) * 2]
        result["top_keywords"] = [
            {
                "keyword": keyword,
                "share": shares[idx] if idx < len(shares) else None,
                "change": changes[idx] if idx < len(changes) else None,
            }
            for idx, keyword in enumerate(keywords)
        ]
    return result


def extract_report_snapshot(browser: Any) -> dict[str, Any]:
    return browser.eval(
        """
        (() => {
          const text = (el) => (el?.innerText || el?.textContent || "").trim();
          const rows = Array.from(document.querySelectorAll("[data-automation=website-rank-row]"))
            .map((el) => text(el))
            .filter(Boolean);
          const reportLinks = Array.from(document.querySelectorAll("a[href]"))
            .map((el) => ({
              text: text(el),
              href: el.getAttribute("href"),
              data: el.getAttribute("data-automation"),
            }))
            .filter((item) =>
              (item.href || "").includes("key=") &&
              (
                (item.href || "").includes("/websiteanalysis/") ||
                (item.href || "").includes("/social/") ||
                (item.href || "").includes("/referrals/")
              )
            )
            .slice(0, 50);

          return {
            url: window.location.href,
            title: document.title,
            query_domain: text(document.querySelector("[data-automation=query-bar-item-text]")),
            total_visits_text: text(document.querySelector("[data-automation=total-visits-widget]")),
            device_distribution_text: text(document.querySelector("[data-automation=device-distribution-widget]")),
            rank_rows: rows,
            channels_text: text(document.querySelector("[data-automation=channelsOverviewContainer]")),
            social_text: text(document.querySelector("[data-automation=social-traffic]")),
            top_referring_websites_text: text(document.querySelector("[data-automation=wwo-top-referring-websites]")),
            top_referring_industries_text: text(document.querySelector("[data-automation=wwo-top-referring-industries]")),
            top_outgoing_links_text: text(document.querySelector("[data-automation=wwo-top-link-destinations]")),
            top_ad_destinations_text: text(document.querySelector("[data-automation=wwo-top-ad-destination]")),
            top_publishers_text: text(document.querySelector("[data-automation=wwo-top-publishers]")),
            page_frame_text: text(document.querySelector("[data-automation=page-frame-container]")),
            report_links: reportLinks,
          };
        })()
        """,
        timeout=30,
    )


def extract_quick_search_state(browser: Any) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    quick_search = browser.eval(
        """
        (() => {
          const modalInput = document.querySelector('[data-automation="quick-search-modal"] input[placeholder*="搜索任何网站、关键词或报告"]');
          const input = modalInput
            || [...document.querySelectorAll("input")]
              .find((el) => (el.placeholder || "").includes("搜索任何网站、关键词或报告"));
          if (!input) return { ok: false, reason: "quick-search-input-missing" };
          return {
            ok: true,
            placeholder: input.placeholder,
            className: input.className,
          };
        })()
        """,
        timeout=20,
    )

    modal_state = browser.eval(
        """
        (() => {
          const websites = [...document.querySelectorAll('[data-automation=quick-search-tab-all-websites] .sc-fVULQU')]
            .map((row) => (row.innerText || row.textContent || "").trim())
            .filter(Boolean);
          const keywords = [...document.querySelectorAll('[data-automation=quick-search-tab-all-keywords] .sc-VHjGu.cDCAeK > div')]
            .map((row) => (row.innerText || row.textContent || "").trim())
            .filter((value) => value && !value.includes("显示更多") && value !== "关键字")
            .slice(0, 10);
          return {
            modal_open: !!document.querySelector("[data-automation=quick-search-modal]"),
            websites,
            keywords,
          };
        })()
        """,
        timeout=20,
    )

    report_suggestions = browser.eval(
        """
        (() => {
          return [...document.querySelectorAll('[data-automation^="quick-search-all-tab-report-row-"]')]
            .map((el) => {
              const parts = (el.innerText || el.textContent || "")
                .split(/\\n+/)
                .map((part) => part.trim())
                .filter(Boolean);
              return {
                automation: el.getAttribute("data-automation"),
                title: parts[0] || "",
                path: parts.slice(1).join(" > "),
              };
            })
            .filter((item) => item.title);
        })()
        """,
        timeout=20,
    )
    return quick_search, modal_state, report_suggestions or []


def fill_quick_search(browser: Any, query: str) -> None:
    browser.eval(
        f"""
        (() => {{
          const modalInput = document.querySelector('[data-automation="quick-search-modal"] input[placeholder*="搜索任何网站、关键词或报告"]');
          const input = modalInput
            || [...document.querySelectorAll("input")]
              .find((el) => (el.placeholder || "").includes("搜索任何网站、关键词或报告"));
          if (!input) return {{ ok: false }};
          const desc = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), "value")
            || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
          desc.set.call(input, {json.dumps(query)});
          input.dispatchEvent(new Event("input", {{ bubbles: true }}));
          input.dispatchEvent(new Event("change", {{ bubbles: true }}));
          input.focus();
          return {{ ok: true, value: input.value }};
        }})()
        """,
        timeout=20,
    )


def click_exact_website_candidate(browser: Any, query: str) -> bool:
    result = browser.eval(
        f"""
        (() => {{
          const rows = [...document.querySelectorAll('[data-automation=quick-search-tab-all-websites] .sc-fVULQU')];
          const target = rows.find((row) => (row.innerText || row.textContent || "").trim() === {json.dumps(query)});
          if (!target) return {{ ok: false, reason: "website-candidate-missing" }};
          target.click();
          return {{ ok: true }};
        }})()
        """,
        timeout=20,
    )
    return bool(isinstance(result, dict) and result.get("ok"))


def build_website_performance(report_snapshot: dict[str, Any]) -> dict[str, Any]:
    page_text = report_snapshot.get("page_frame_text")
    return {
        "available": WEBSITE_PERFORMANCE_ROUTE_FRAGMENT in (report_snapshot.get("url") or ""),
        "route": report_snapshot.get("url"),
        "title": report_snapshot.get("title"),
        "domain": report_snapshot.get("query_domain"),
        "total_visits": parse_total_visits(report_snapshot.get("total_visits_text")),
        "device_distribution": parse_device_distribution(report_snapshot.get("device_distribution_text")),
        "ranks": parse_rank_rows(report_snapshot.get("rank_rows") or []),
        "engagement": parse_engagement(page_text),
        "top_countries": parse_top_countries(page_text),
        "traffic_channels": parse_channel_breakdown(report_snapshot.get("channels_text")),
        "organic_search": parse_keyword_breakdown(page_text, "自然搜索", "付费搜索"),
        "paid_search": parse_keyword_breakdown(page_text, "付费搜索", "外链"),
        "top_referring_websites": parse_share_table(
            report_snapshot.get("top_referring_websites_text"),
            entity_header="域",
            share_header="共享",
            change_header="变动",
        ),
        "top_referring_industries": parse_share_table(
            report_snapshot.get("top_referring_industries_text"),
            entity_header="网站类别",
            share_header="流量份额",
            change_header=None,
        ),
        "top_outgoing_links": parse_share_table(
            report_snapshot.get("top_outgoing_links_text"),
            entity_header="Domain",
            share_header="共享",
            change_header="变动",
        ),
        "top_ad_destinations": parse_share_table(
            report_snapshot.get("top_ad_destinations_text"),
            entity_header="域",
            share_header="共享",
            change_header="变动",
        ),
        "social_breakdown": parse_social_breakdown(report_snapshot.get("social_text")),
        "top_publishers": parse_share_table(
            report_snapshot.get("top_publishers_text"),
            entity_header="发布商",
            share_header="共享",
            change_header="变动",
        ),
        "route_hints": report_snapshot.get("report_links") or [],
    }


def navigate_to_website_performance(browser: Any, query: str) -> tuple[bool, str]:
    route = build_website_performance_route(query)
    target = f"https://sim.3ue.com{route}"

    try:
        browser.eval(
            f"""
            (() => {{
              window.location.assign({json.dumps(target)});
              return {{ ok: true, target: {json.dumps(target)} }};
            }})()
            """,
            timeout=20,
        )
        wait_for_website_performance_ready(browser, timeout=45)
        return True, "hash_route_assign"
    except BrowseError:
        pass

    try:
        browser.open(target, timeout=90)
        wait_for_website_performance_ready(browser, timeout=45)
        return True, "direct_route_open_after_entry"
    except BrowseError:
        return False, "unresolved"


def collect(query: str, username: str, password: str, session: str, keep_session: bool = False) -> dict[str, Any]:
    executor = ThreeUEExecutor(username=username, password=password, session=session)
    try:
        executor.reset_session()
        login = executor.login()
        executor.browser.network_on()
        network_dir = executor.browser.network_clear()
        open_result = executor.open_tool("similarweb")

        shell_notes: list[str] = []
        try:
            shell_state = wait_for_similarweb_shell_ready(executor.browser, timeout=75)
        except BrowseError as exc:
            shell_state = {
                "href": executor.browser.current_url(),
                "title": executor.browser.current_title(),
                "fallback": True,
            }
            shell_notes.append(f"Similarweb shell readiness fell back to url/title-only state: {exc}")
        shell_url = str(shell_state.get("href", executor.browser.current_url()))
        tool_title = str(shell_state.get("title", executor.browser.current_title()))
        home_signals = extract_home_signals(executor.browser)

        quick_search: dict[str, Any] = {"ok": False, "reason": "not-attempted"}
        modal_state: dict[str, Any] = {"modal_open": False, "websites": [], "keywords": []}
        report_suggestions: list[dict[str, Any]] = []
        quick_search_notes: list[str] = []
        try:
            executor.browser.press("Ctrl+K")
            executor.browser.wait_timeout(1.5)
            fill_quick_search(executor.browser, query)
            executor.browser.wait_timeout(3)
            quick_search, modal_state, report_suggestions = extract_quick_search_state(executor.browser)
        except BrowseError as exc:
            quick_search_notes.append(f"Quick search extraction failed in this session: {exc}")

        clicked_candidate = False
        report_navigation_ok = False
        route_navigation_used = "not-attempted"
        try:
            report_navigation_ok, route_navigation_used = navigate_to_website_performance(executor.browser, query)
            if not report_navigation_ok:
                clicked_candidate = click_exact_website_candidate(executor.browser, query)
                route_navigation_used = "quick_search_candidate_click" if clicked_candidate else route_navigation_used
        except BrowseError as exc:
            route_navigation_used = "navigation-error"
            quick_search_notes.append(f"Website-performance navigation failed in this session: {exc}")

        report_snapshot: dict[str, Any] = {}
        if report_navigation_ok or clicked_candidate:
            try:
                wait_for_website_performance_ready(executor.browser, timeout=60)
                executor.browser.wait_timeout(3)
                report_snapshot = extract_report_snapshot(executor.browser)
            except BrowseError:
                report_snapshot = {}

        final_url = executor.browser.try_current_url() or report_snapshot.get("url") or shell_url
        final_title = executor.browser.try_current_title() or report_snapshot.get("title") or tool_title
        entries = load_network_entries(network_dir)

        identities = first_non_null(
            find_first(entries, "/api/identities"),
            executor.browser.fetch_json("/api/identities"),
        )
        startup = first_non_null(
            find_first(entries, "/api/startupSettings"),
            executor.browser.fetch_json("/api/startupSettings?force=false"),
        )
        autocomplete_websites = first_non_null(
            find_first(entries, "/autocomplete/websites"),
            executor.browser.fetch_json(
                f"/autocomplete/websites?size=25&term={quote(query)}&webSource=Desktop&validate=true"
            ),
        )
        preferences = find_first(entries, "/api/userdata/preferences")
        recent = find_first(entries, "/api/userdata/recent")
        favorites = find_first(entries, "/api/userdata/favorites")
        dashboards = find_first(entries, "/api/userdata/dashboards")
        googletag = find_first(entries, "/api/googletag")
        autocomplete_keywords = find_first(entries, "/autocomplete/keywords")
        similar_sites = find_first(entries, "/api/WebsiteOverview/getsimilarsites")
        subscription_context = executor.get_subscription_context()

        recent_items = []
        if isinstance(recent, list):
            for item in recent[:10]:
                data = item.get("data", {})
                recent_items.append(
                    {
                        "main_item": data.get("mainItem"),
                        "state_name": data.get("stateName"),
                        "page_title": data.get("pageTitle"),
                        "duration": data.get("duration"),
                        "country": data.get("country"),
                        "params": data.get("params"),
                    }
                )

        favorite_items = []
        if isinstance(favorites, dict):
            for item in favorites.get("items", [])[:10]:
                data = item.get("data", {})
                favorite_items.append(
                    {
                        "main_item": data.get("mainItem"),
                        "state_name": data.get("stateName"),
                        "page_title": data.get("pageTitle"),
                        "duration": data.get("duration"),
                        "country": data.get("country"),
                        "params": data.get("params"),
                    }
                )

        available_components = {}
        if isinstance(startup, dict):
            for name, info in list(startup.get("settings", {}).get("components", {}).items())[:25]:
                resources = info.get("resources", {})
                available_components[name] = {
                    "mode": resources.get("AvaliabilityMode"),
                    "disabled": resources.get("IsDisabled"),
                    "type": resources.get("type"),
                }

        website_performance = build_website_performance(report_snapshot)

        notes = [
            "3ue Similarweb session opened via dashboard card.",
            "Capture now tolerates Similarweb shell stalls by falling back to url/title, snapshot, and body-text markers.",
            "Activation-home priority alerts were extracted when available so the capture can still return structured growth signals even if deeper report routing stalls.",
        ]
        notes.extend(shell_notes)
        notes.extend(quick_search_notes)
        if quick_search.get("ok"):
            notes.append("Quick-search website candidates and report suggestions were captured from the real Similarweb shell.")
        if website_performance.get("available"):
            notes.append("Website-performance report metrics were extracted from DOM blocks after entering the 3ue-backed Similarweb shell.")
        if route_navigation_used == "hash_route_assign":
            notes.append("Report navigation used an authenticated hash-route jump inside the already-open 3ue Similarweb shell.")
        elif route_navigation_used == "direct_route_open_after_entry":
            notes.append("Report navigation used a same-session direct report open after the 3ue Similarweb shell was established.")
        elif route_navigation_used == "quick_search_candidate_click":
            notes.append("Report navigation used a quick-search website candidate click.")
        else:
            notes.append("No stable report navigation path succeeded in this session.")
        if not website_performance.get("available"):
            notes.append("Full website-performance report was not reached in this session; account-state and route evidence were still captured.")
        if not keep_session:
            notes.append("Browser session was closed automatically after capture.")

        return {
            "tool": "similarweb",
            "query": {"type": "domain", "value": query},
            "source": {
                "provider": "3ue",
                "dashboard": "https://dash.3ue.com/zh-Hans/#/page/m/home",
                "tool_url": final_url or shell_url,
                "captured_at": iso_utc_now(),
            },
            "account_context": {
                "login": login,
                "subscription": subscription_context.get("subscription"),
                "auditing": subscription_context.get("auditing"),
            },
            "capture_method": {
                "login": "automated_3ue_login",
                "primary": "page_json_and_dom",
                "fallback": "network",
            },
            "raw_artifacts": {
                "network_dir": network_dir,
                "open_result": open_result,
                "shell_url": shell_url,
                "final_title": final_title,
                "notes": notes,
            },
            "account_state": {
                "identity": identities[0] if isinstance(identities, list) and identities else identities,
                "preferences": preferences,
                "favorites": favorite_items,
                "recent_items": recent_items,
                "available_components": available_components,
                "dashboard_count": len(dashboards.get("data", [])) if isinstance(dashboards, dict) else 0,
                "googletag_user": googletag.get("user") if isinstance(googletag, dict) else None,
                "tool_title": final_title or tool_title,
            },
            "website_evidence": {
                "domain": query,
                "quick_search": quick_search,
                "quick_search_modal": modal_state,
                "report_suggestions": report_suggestions,
                "website_candidate_clicked": clicked_candidate,
                "report_navigation_used": route_navigation_used,
                "website_performance_route_candidates": [
                    item for item in favorite_items if item.get("state_name") == "digitalsuite_website_websiteperformance"
                ],
                "landing_pages_route_candidates": [
                    item for item in favorite_items if item.get("state_name") == "organicsearch_website_landingpages_v2"
                ],
                "autocomplete_websites": normalize_website_rows(autocomplete_websites or []),
                "autocomplete_keywords": autocomplete_keywords or [],
                "similar_sites": similar_sites or [],
                "home_signals": home_signals,
                "website_performance": website_performance,
            },
        }
    finally:
        if not keep_session:
            executor.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture Similarweb evidence into structured JSON.")
    parser.add_argument("--query", required=True, help="Domain to inspect")
    parser.add_argument("--username", default=os.environ.get("THREEUE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("THREEUE_PASSWORD", ""))
    parser.add_argument("--session", default="dvos-sim")
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
