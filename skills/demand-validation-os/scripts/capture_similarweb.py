#!/usr/bin/env python3
"""Capture Similarweb account and route evidence from a logged-in 3ue session."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from browser_capture import ThreeUEExecutor, iso_utc_now, load_network_entries


def find_first(entries: list[dict[str, Any]], needle: str) -> Any:
    for entry in entries:
        if needle in entry["request"]["url"]:
            return entry["parsed_body"]
    return None


def first_non_null(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def collect(query: str, username: str, password: str, session: str) -> dict[str, Any]:
    executor = ThreeUEExecutor(username=username, password=password, session=session)
    executor.reset_session()
    login = executor.login()
    executor.browser.network_on()
    network_dir = executor.browser.network_clear()
    open_result = executor.open_tool("similarweb")
    executor.browser.wait_timeout(8)
    tool_url = executor.browser.get("url").get("url")
    tool_title = executor.browser.get("title").get("title")

    executor.browser.press("Ctrl+K")
    executor.browser.wait_timeout(1.5)

    quick_search = executor.browser.eval(
        """
        (() => {
          const input = [...document.querySelectorAll("input")]
            .find((el) => (el.placeholder || "").includes("搜索任何网站、关键词或报告"));
          if (!input) return { ok: false, reason: "quick-search-input-missing" };
          return {
            ok: true,
            placeholder: input.placeholder,
            className: input.className
          };
        })()
        """,
        timeout=20,
    )

    # Populate autocomplete for target evidence.
    executor.browser.eval(
        f"""
        (() => {{
          const input = [...document.querySelectorAll("input")]
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
    executor.browser.wait_timeout(3)

    modal_state = executor.browser.eval(
        """
        (() => {
          const modal = document.querySelector("[data-automation=quick-search-modal]");
          const websites = [...document.querySelectorAll("[data-automation=quick-search-tab-all-websites] .sc-fVULQU")]
            .map((el) => (el.textContent || "").trim())
            .filter(Boolean);
          const keywords = [...document.querySelectorAll("[data-automation-item=keywords] span")]
            .map((el) => (el.textContent || "").trim())
            .filter(Boolean)
            .slice(0, 10);
          return {
            modal_open: !!modal,
            websites,
            keywords
          };
        })()
        """,
        timeout=20,
    )

    report_suggestions = executor.browser.eval(
        """
        (() => {
          return [...document.querySelectorAll('[data-automation^="quick-search-all-tab-report-row-"]')]
            .map((el) => {
              const parts = (el.innerText || el.textContent || "")
                .split(/\\n+/)
                .map((part) => part.trim())
                .filter(Boolean);
              return {
                title: parts[0] || "",
                path: parts.slice(1).join(" > "),
              };
            })
            .filter((item) => item.title);
        })()
        """,
        timeout=20,
    )

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

    return {
        "tool": "similarweb",
        "query": {"type": "domain", "value": query},
        "source": {
            "provider": "3ue",
            "dashboard": "https://dash.3ue.com/zh-Hans/#/page/m/home",
            "tool_url": tool_url,
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
            "notes": [
                "3ue Similarweb session opened via dashboard card.",
                "Page-level JSON endpoints were preferred when available because Similarweb network capture under 3ue is session-sensitive.",
                "Quick-search modal suggestions and report candidates were captured from DOM.",
            ],
        },
        "account_state": {
            "identity": identities[0] if isinstance(identities, list) and identities else identities,
            "preferences": preferences,
            "favorites": favorite_items,
            "recent_items": recent_items,
            "available_components": available_components,
            "dashboard_count": len(dashboards.get("data", [])) if isinstance(dashboards, dict) else 0,
            "googletag_user": googletag.get("user") if isinstance(googletag, dict) else None,
            "tool_title": tool_title,
        },
        "website_evidence": {
            "domain": query,
            "quick_search": quick_search,
            "quick_search_modal": modal_state,
            "report_suggestions": report_suggestions or [],
            "website_performance_route_candidates": [
                item for item in favorite_items if item.get("state_name") == "digitalsuite_website_websiteperformance"
            ],
            "landing_pages_route_candidates": [
                item for item in favorite_items if item.get("state_name") == "organicsearch_website_landingpages_v2"
            ],
            "autocomplete_websites": [
                {
                    "name": item.get("name"),
                    "blocked": 1 in item.get("blockStatus", []),
                }
                for item in (autocomplete_websites or [])
            ],
            "autocomplete_keywords": autocomplete_keywords or [],
            "similar_sites": similar_sites or [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture Similarweb evidence into structured JSON.")
    parser.add_argument("--query", required=True, help="Domain to inspect")
    parser.add_argument("--username", default=os.environ.get("THREEUE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("THREEUE_PASSWORD", ""))
    parser.add_argument("--session", default="dvos-sim")
    parser.add_argument("--output", help="Write JSON to a file")
    args = parser.parse_args()

    if not args.username or not args.password:
        raise SystemExit("Missing 3ue credentials. Set THREEUE_USERNAME and THREEUE_PASSWORD or pass --username/--password.")

    data = collect(args.query, args.username, args.password, args.session)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
