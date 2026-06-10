#!/usr/bin/env python3
"""Collect structured Google Trends evidence with browser-backed fallback."""

from __future__ import annotations

import argparse
import json
import os
from statistics import mean
from typing import Any
from urllib.parse import quote, urlparse

import requests

from browser_capture import BrowseClient, iso_utc_now


DEFAULT_TIMEFRAMES = ["today 1-m", "today 3-m", "today 12-m", "today 5-y"]
TRENDS_HOME = "https://trends.google.com/trends/"
DATAFORSEO_EXPLORE_URL = "https://api.dataforseo.com/v3/keywords_data/google_trends/explore/live"
DATAFORSEO_TIMEFRAME_MAP = {
    "today 1-m": "past_30_days",
    "today 3-m": "past_90_days",
    "today 12-m": "past_12_months",
    "today 5-y": "past_5_years",
}
DATAFORSEO_TYPE_MAP = {
    "": "web",
    "web": "web",
    "news": "news",
    "images": "images",
    "shopping": "froogle",
    "youtube": "youtube",
}
GEO_NAME_MAP = {
    "US": "United States",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "CA": "Canada",
    "AU": "Australia",
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "BR": "Brazil",
    "IN": "India",
    "JP": "Japan",
    "KR": "South Korea",
    "SG": "Singapore",
}


class TrendsError(RuntimeError):
    pass


def configured_rapidapi() -> bool:
    return bool(
        os.environ.get("RAPIDAPI_KEY")
        and os.environ.get("RAPIDAPI_GOOGLE_TRENDS_HOST")
        and os.environ.get("RAPIDAPI_GOOGLE_TRENDS_INTEREST_PATH")
    )


def configured_dataforseo() -> bool:
    return bool(os.environ.get("DATAFORSEO_LOGIN") and os.environ.get("DATAFORSEO_PASSWORD"))


def build_empty_window(
    timeframe: str,
    *,
    provider: str,
    error: str,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "timeframe": timeframe,
        "label": timeframe_label(timeframe),
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
        "fetch_modes": {
            "PRIMARY": {
                "mode": "failed",
                "provider": provider,
                "error": error,
            }
        },
        "available": False,
        "notes": notes or [error],
    }


def build_payload(
    *,
    query: str,
    geo: str,
    hl: str,
    property_name: str,
    provider: str,
    windows: list[dict[str, Any]],
    notes: list[str] | None = None,
    provider_attempts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "query": {"type": "keyword", "value": query},
        "source": {
            "provider": provider,
            "captured_at": iso_utc_now(),
        },
        "available": any(window.get("available") for window in windows),
        "geo": geo,
        "language": hl,
        "property": property_name or "web",
        "windows": windows,
        "summary": summarize_windows(windows),
        "notes": notes or [],
    }
    if provider_attempts is not None:
        payload["provider_attempts"] = provider_attempts
    return payload


def first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def scalar_value(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def strip_xssi_prefix(text: str) -> str:
    if text.startswith(")]}'"):
        parts = text.split("\n", 1)
        return parts[1] if len(parts) == 2 else ""
    return text


def parse_json_response(text: str) -> Any:
    return json.loads(strip_xssi_prefix(text))


def timeframe_label(timeframe: str) -> str:
    mapping = {
        "today 1-m": "30d",
        "today 3-m": "90d",
        "today 12-m": "12m",
        "today 5-y": "5y",
    }
    return mapping.get(timeframe, timeframe.replace(" ", "_"))


def build_explore_request(query: str, geo: str, timeframe: str, category: int, property_name: str) -> dict[str, Any]:
    return {
        "comparisonItem": [
            {
                "keyword": query,
                "geo": geo,
                "time": timeframe,
            }
        ],
        "category": category,
        "property": property_name,
    }


def build_explore_url(query: str, geo: str, timeframe: str, category: int, property_name: str, hl: str, tz: int) -> str:
    req = build_explore_request(query, geo, timeframe, category, property_name)
    req_str = quote(json.dumps(req, ensure_ascii=False, separators=(",", ":")))
    return f"https://trends.google.com/trends/api/explore?hl={quote(hl)}&tz={tz}&req={req_str}"


def widget_endpoint(widget_id: str) -> str | None:
    return {
        "TIMESERIES": "widgetdata/multiline",
        "GEO_MAP": "widgetdata/comparedgeo",
        "RELATED_QUERIES": "widgetdata/relatedsearches",
    }.get(widget_id)


def build_widget_url(widget: dict[str, Any], endpoint: str, hl: str, tz: int) -> str:
    req = quote(json.dumps(widget["request"], ensure_ascii=False, separators=(",", ":")))
    token = quote(widget["token"], safe="")
    return f"https://trends.google.com/trends/api/{endpoint}?hl={quote(hl)}&tz={tz}&req={req}&token={token}"


def requests_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "accept-language": "en-US,en;q=0.9",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
            ),
        }
    )
    session.get(TRENDS_HOME, timeout=20)
    return session


def direct_get_json(session: requests.Session, url: str) -> Any:
    response = session.get(url, timeout=30)
    if response.status_code != 200:
        raise TrendsError(f"Google Trends returned HTTP {response.status_code} for {url}")
    return parse_json_response(response.text)


def browser_get_json(url: str, *, session_name: str, open_url: str) -> Any:
    browser = BrowseClient(session=session_name)
    try:
        browser.stop(ignore_errors=True)
        browser.open(open_url, timeout=90)
        browser.wait_timeout(5)
        request_url = url
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.netloc == "trends.google.com":
            request_url = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        result = browser.eval(
            f"""
            (() => {{
              try {{
                const xhr = new XMLHttpRequest();
                xhr.open("GET", {json.dumps(request_url)}, false);
                xhr.withCredentials = true;
                xhr.send(null);
                const raw = xhr.responseText || "";
                const cleaned = raw.startsWith(")]}}'") ? raw : raw;
                const text = raw.replace(/^\\)\\]\\}}',?\\n/, "");
                let body = text;
                try {{
                  body = text ? JSON.parse(text) : null;
                }} catch (_error) {{}}
                return {{
                  ok: xhr.status >= 200 && xhr.status < 300,
                  status: xhr.status,
                  body
                }};
              }} catch (error) {{
                return {{
                  ok: false,
                  status: 0,
                  error: String(error)
                }};
              }}
            }})()
            """,
            timeout=40,
        )
        if not isinstance(result, dict) or not result.get("ok"):
            raise TrendsError(f"Browser fallback failed for {url}: {result}")
        return result.get("body")
    finally:
        browser.stop(ignore_errors=True)


def fetch_widget_payload(
    *,
    session: requests.Session,
    widget: dict[str, Any],
    query: str,
    geo: str,
    timeframe: str,
    hl: str,
    tz: int,
    browser_session: str,
    allow_browser_fallback: bool = True,
) -> tuple[Any | None, str, str | None]:
    endpoint = widget_endpoint(widget["id"])
    if endpoint is None:
        return None, "unsupported", "widget-not-supported"
    url = build_widget_url(widget, endpoint, hl, tz)
    try:
        return direct_get_json(session, url), "requests", None
    except Exception as exc:
        if not allow_browser_fallback:
            return None, "failed", f"requests:{type(exc).__name__}"
        open_url = (
            "https://trends.google.com/trends/explore"
            f"?geo={quote(geo)}&q={quote(query)}&hl={quote(hl)}&date={quote(timeframe)}"
        )
        try:
            return browser_get_json(url, session_name=browser_session, open_url=open_url), "browser", None
        except Exception as browser_exc:
            reason = f"requests:{type(exc).__name__};browser:{type(browser_exc).__name__}"
            return None, "failed", reason


def normalize_timeline(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    data = (((payload or {}).get("default") or {}).get("timelineData") or [])
    rows = []
    for row in data:
        values = row.get("value") or []
        value = values[0] if values else None
        rows.append(
            {
                "time": row.get("time"),
                "formatted_time": row.get("formattedTime"),
                "value": value,
                "has_data": row.get("hasData", []),
                "formatted_value": (row.get("formattedValue") or [None])[0],
            }
        )
    return rows


def normalize_regions(payload: dict[str, Any] | None, limit: int = 15) -> list[dict[str, Any]]:
    data = (((payload or {}).get("default") or {}).get("geoMapData") or [])[:limit]
    rows = []
    for row in data:
        values = row.get("value") or []
        rows.append(
            {
                "name": row.get("geoName") or row.get("name"),
                "code": row.get("geoCode"),
                "value": values[0] if values else None,
                "formatted_value": (row.get("formattedValue") or [None])[0],
            }
        )
    return rows


def normalize_related_queries(payload: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    ranked_lists = (((payload or {}).get("default") or {}).get("rankedList") or [])
    result = {"top": [], "rising": []}
    for ranked in ranked_lists:
        kind = str(ranked.get("rankedKeywordType") or "").lower()
        target = "rising" if "rising" in kind else "top"
        for item in ranked.get("rankedKeyword", [])[:10]:
            result[target].append(
                {
                    "query": item.get("query"),
                    "value": item.get("value"),
                    "formatted_value": item.get("formattedValue"),
                    "link": item.get("link"),
                }
            )
    return result


def average(values: list[float]) -> float:
    return round(mean(values), 2) if values else 0.0


def segment_mean(values: list[float], start: int, end: int) -> float:
    if not values:
        return 0.0
    chunk = values[start:end] or values
    return average(chunk)


def classify_trend_shape(values: list[float]) -> str:
    if len(values) < 4:
        return "unknown"
    peak = max(values)
    avg_value = average(values)
    first = segment_mean(values, 0, max(1, len(values) // 4))
    last = segment_mean(values, max(0, len(values) - max(1, len(values) // 4)), len(values))
    latest = values[-1]
    if peak >= max(avg_value * 1.9, 35) and latest <= peak * 0.55:
        return "spike"
    if last >= first * 1.25 and latest >= avg_value:
        return "rising"
    if last <= first * 0.75:
        return "declining"
    if abs(last - first) <= max(5, avg_value * 0.15):
        return "stable"
    return "mixed"


def summarize_timeline(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["value"]) for row in rows if isinstance(row.get("value"), (int, float))]
    if not values:
        return {
            "points": 0,
            "average_interest": None,
            "latest_interest": None,
            "peak_interest": None,
            "shape": "missing",
        }
    non_zero = [value for value in values if value > 0]
    first_value = values[0]
    latest = values[-1]
    peak = max(values)
    avg_value = average(values)
    delta = round(latest - first_value, 2)
    pct_change = None
    if first_value > 0:
        pct_change = round((latest - first_value) / first_value * 100, 2)
    elif latest > 0:
        pct_change = 100.0
    return {
        "points": len(values),
        "non_zero_points": len(non_zero),
        "average_interest": avg_value,
        "latest_interest": latest,
        "peak_interest": peak,
        "delta": delta,
        "pct_change": pct_change,
        "shape": classify_trend_shape(values),
    }


def collect_timeframe(
    *,
    session: requests.Session,
    query: str,
    geo: str,
    timeframe: str,
    category: int,
    property_name: str,
    hl: str,
    tz: int,
    browser_session: str,
    include_regions: bool,
    include_related: bool,
) -> dict[str, Any]:
    explore_url = build_explore_url(query, geo, timeframe, category, property_name, hl, tz)
    open_url = (
        "https://trends.google.com/trends/explore"
        f"?geo={quote(geo)}&q={quote(query)}&hl={quote(hl)}&date={quote(timeframe)}"
    )
    try:
        explore = direct_get_json(session, explore_url)
        explore_mode = "requests"
        explore_error = None
    except Exception as exc:
        try:
            explore = browser_get_json(explore_url, session_name=f"{browser_session}-{timeframe_label(timeframe)}-explore", open_url=open_url)
            explore_mode = "browser"
            explore_error = None
        except Exception as browser_exc:
            return {
                "timeframe": timeframe,
                "label": timeframe_label(timeframe),
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
                "fetch_modes": {
                    "EXPLORE": {
                        "mode": "failed",
                        "error": (
                            f"requests:{type(exc).__name__};"
                            f"browser:{type(browser_exc).__name__}"
                        ),
                    },
                    "TIMESERIES": {"mode": "skipped", "error": "explore-unavailable"},
                    "GEO_MAP": {"mode": "skipped", "error": "explore-unavailable"},
                    "RELATED_QUERIES": {"mode": "skipped", "error": "explore-unavailable"},
                },
                "available": False,
                "notes": [
                    "Google Trends explore metadata was unavailable for this timeframe.",
                    f"requests failure: {type(exc).__name__}",
                    f"browser failure: {type(browser_exc).__name__}",
                ],
            }
    widgets = {item.get("id"): item for item in explore.get("widgets", []) if item.get("id")}
    widget_fetch = {"EXPLORE": {"mode": explore_mode, "error": explore_error}}

    timeline_payload, timeline_mode, timeline_error = fetch_widget_payload(
        session=session,
        widget=widgets["TIMESERIES"],
        query=query,
        geo=geo,
        timeframe=timeframe,
        hl=hl,
        tz=tz,
        browser_session=f"{browser_session}-{timeframe_label(timeframe)}-ts",
    )
    widget_fetch["TIMESERIES"] = {"mode": timeline_mode, "error": timeline_error}

    geo_payload = None
    geo_mode = "skipped"
    geo_error = None
    if include_regions and "GEO_MAP" in widgets:
        geo_payload, geo_mode, geo_error = fetch_widget_payload(
            session=session,
            widget=widgets["GEO_MAP"],
            query=query,
            geo=geo,
            timeframe=timeframe,
            hl=hl,
            tz=tz,
            browser_session=f"{browser_session}-{timeframe_label(timeframe)}-geo",
        )
    widget_fetch["GEO_MAP"] = {"mode": geo_mode, "error": geo_error}

    related_payload = None
    related_mode = "skipped"
    related_error = None
    if include_related and "RELATED_QUERIES" in widgets:
        related_payload, related_mode, related_error = fetch_widget_payload(
            session=session,
            widget=widgets["RELATED_QUERIES"],
            query=query,
            geo=geo,
            timeframe=timeframe,
            hl=hl,
            tz=tz,
            browser_session=f"{browser_session}-{timeframe_label(timeframe)}-rq",
            allow_browser_fallback=False,
        )
    widget_fetch["RELATED_QUERIES"] = {"mode": related_mode, "error": related_error}

    timeline = normalize_timeline(timeline_payload if isinstance(timeline_payload, dict) else None)
    regions = normalize_regions(geo_payload if isinstance(geo_payload, dict) else None)
    related_queries = normalize_related_queries(related_payload if isinstance(related_payload, dict) else None)
    notes = []
    for key, meta in widget_fetch.items():
        if meta["error"]:
            notes.append(f"{key} fetch degraded: {meta['error']}")

    return {
        "timeframe": timeframe,
        "label": timeframe_label(timeframe),
        "interest_over_time": {
            "rows": timeline,
            "summary": summarize_timeline(timeline),
        },
        "interest_by_region": regions,
        "related_queries": related_queries,
        "fetch_modes": widget_fetch,
        "available": True,
        "notes": notes,
    }


def nested_find(payload: Any, keys: list[str]) -> Any:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload:
                return payload[key]
        for value in payload.values():
            found = nested_find(value, keys)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = nested_find(item, keys)
            if found is not None:
                return found
    return None


def normalize_rapidapi_window(payload: dict[str, Any], *, timeframe: str) -> dict[str, Any]:
    raw_interest = nested_find(payload, ["interest", "timeline", "series", "graph"])
    if not isinstance(raw_interest, list):
        raw_interest = []
    timeline = []
    for row in raw_interest:
        if not isinstance(row, dict):
            continue
        value = scalar_value(first_present(row, "value", "values", "interest", "score", "y"))
        timeline.append(
            {
                "time": first_present(row, "timestamp", "time", "date", "x"),
                "formatted_time": first_present(row, "formatted_time", "formattedTime", "date"),
                "value": value,
                "has_data": [value is not None],
                "formatted_value": str(value) if value is not None else None,
            }
        )

    raw_regions = nested_find(payload, ["top_regions", "topRegions", "interest_by_region", "regions"])
    if not isinstance(raw_regions, list):
        raw_regions = []
    regions = []
    for row in raw_regions[:15]:
        if not isinstance(row, dict):
            continue
        value = scalar_value(first_present(row, "value", "values", "interest", "score"))
        regions.append(
            {
                "name": first_present(row, "name", "geo_name", "region"),
                "code": first_present(row, "code", "geo_code", "geo_id"),
                "value": value,
                "formatted_value": str(value) if value is not None else None,
            }
        )

    raw_related = nested_find(payload, ["related_queries", "relatedQueries", "queries"])
    related_queries = {"top": [], "rising": []}
    if isinstance(raw_related, dict):
        top_rows = raw_related.get("top") or []
        rising_rows = raw_related.get("rising") or []
        if isinstance(top_rows, list):
            for row in top_rows[:10]:
                if isinstance(row, dict):
                    related_queries["top"].append(
                        {
                            "query": first_present(row, "query", "keyword", "term"),
                            "value": scalar_value(first_present(row, "value", "score")),
                            "formatted_value": str(first_present(row, "value", "score")) if first_present(row, "value", "score") is not None else None,
                            "link": row.get("link"),
                        }
                    )
        if isinstance(rising_rows, list):
            for row in rising_rows[:10]:
                if isinstance(row, dict):
                    related_queries["rising"].append(
                        {
                            "query": first_present(row, "query", "keyword", "term"),
                            "value": scalar_value(first_present(row, "value", "score")),
                            "formatted_value": str(first_present(row, "value", "score")) if first_present(row, "value", "score") is not None else None,
                            "link": row.get("link"),
                        }
                    )
    elif isinstance(raw_related, list):
        for row in raw_related[:10]:
            if isinstance(row, dict):
                related_queries["top"].append(
                    {
                        "query": first_present(row, "query", "keyword", "term"),
                        "value": scalar_value(first_present(row, "value", "score")),
                        "formatted_value": str(first_present(row, "value", "score")) if first_present(row, "value", "score") is not None else None,
                        "link": row.get("link"),
                    }
                )

    return {
        "timeframe": timeframe,
        "label": timeframe_label(timeframe),
        "interest_over_time": {
            "rows": timeline,
            "summary": summarize_timeline(timeline),
        },
        "interest_by_region": regions,
        "related_queries": related_queries,
        "fetch_modes": {
            "PRIMARY": {
                "mode": "requests",
                "provider": "rapidapi",
                "error": None,
            }
        },
        "available": bool(timeline or regions or related_queries["top"] or related_queries["rising"]),
        "notes": [
            "RapidAPI provider schema was normalized into the standard Google Trends window shape.",
        ],
    }


def collect_rapidapi(
    query: str,
    *,
    geo: str,
    timeframes: list[str],
    property_name: str,
    hl: str,
) -> dict[str, Any]:
    if not configured_rapidapi():
        raise TrendsError("RapidAPI Google Trends provider is not configured")

    api_key = os.environ["RAPIDAPI_KEY"]
    host = os.environ["RAPIDAPI_GOOGLE_TRENDS_HOST"]
    path = os.environ["RAPIDAPI_GOOGLE_TRENDS_INTEREST_PATH"]
    url = path if path.startswith("http") else f"https://{host}{path}"
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": host,
    }
    windows = []
    for timeframe in timeframes:
        response = requests.get(
            url,
            headers=headers,
            params={
                "query": query,
                "geo": geo,
                "timeframe": timeframe,
                "hl": hl,
                "property": property_name or "web",
            },
            timeout=30,
        )
        if response.status_code != 200:
            windows.append(
                build_empty_window(
                    timeframe,
                    provider="rapidapi",
                    error=f"HTTP {response.status_code}",
                    notes=[f"RapidAPI provider returned HTTP {response.status_code} for {timeframe_label(timeframe)}."],
                )
            )
            continue
        windows.append(normalize_rapidapi_window(response.json(), timeframe=timeframe))
    return build_payload(
        query=query,
        geo=geo,
        hl=hl,
        property_name=property_name,
        provider="rapidapi-google-trends",
        windows=windows,
        notes=[
            "RapidAPI was used as a fallback provider for Google Trends.",
            "Provider-specific fields are normalized into the standard window format.",
        ],
    )


def dataforseo_language_name(hl: str) -> str:
    if hl.lower().startswith("en"):
        return "English"
    if hl.lower().startswith("zh"):
        return "Chinese"
    if hl.lower().startswith("ja"):
        return "Japanese"
    return "English"


def dataforseo_location_name(geo: str) -> str:
    return GEO_NAME_MAP.get(geo.upper(), geo)


def normalize_dataforseo_window(result: dict[str, Any], *, timeframe: str) -> dict[str, Any]:
    items = result.get("items") or []
    graph_item = next((item for item in items if item.get("type") == "google_trends_graph"), None)
    map_item = next((item for item in items if item.get("type") == "google_trends_map"), None)
    queries_item = next((item for item in items if item.get("type") == "google_trends_queries_list"), None)

    timeline = []
    for row in (graph_item or {}).get("data") or []:
        value = scalar_value(row.get("values"))
        timeline.append(
            {
                "time": row.get("timestamp"),
                "formatted_time": f"{row.get('date_from')} -> {row.get('date_to')}",
                "value": value,
                "has_data": [not bool(row.get("missing_data"))],
                "formatted_value": str(value) if value is not None else None,
            }
        )

    regions = []
    for row in ((map_item or {}).get("data") or [])[:15]:
        value = scalar_value(row.get("values"))
        regions.append(
            {
                "name": row.get("geo_name"),
                "code": row.get("geo_id"),
                "value": value,
                "formatted_value": str(value) if value is not None else None,
            }
        )

    related_queries = {"top": [], "rising": []}
    queries_data = (queries_item or {}).get("data") or {}
    for row in (queries_data.get("top") or [])[:10]:
        related_queries["top"].append(
            {
                "query": row.get("query"),
                "value": scalar_value(row.get("value")),
                "formatted_value": str(row.get("value")) if row.get("value") is not None else None,
                "link": None,
            }
        )
    for row in (queries_data.get("rising") or [])[:10]:
        related_queries["rising"].append(
            {
                "query": row.get("query"),
                "value": scalar_value(row.get("value")),
                "formatted_value": str(row.get("value")) if row.get("value") is not None else None,
                "link": None,
            }
        )

    return {
        "timeframe": timeframe,
        "label": timeframe_label(timeframe),
        "interest_over_time": {
            "rows": timeline,
            "summary": summarize_timeline(timeline),
        },
        "interest_by_region": regions,
        "related_queries": related_queries,
        "fetch_modes": {
            "PRIMARY": {
                "mode": "requests",
                "provider": "dataforseo",
                "error": None,
            }
        },
        "available": bool(timeline or regions or related_queries["top"] or related_queries["rising"]),
        "notes": [
            "DataForSEO Google Trends Explore Live was normalized into the standard window format.",
        ],
    }


def collect_dataforseo(
    query: str,
    *,
    geo: str,
    timeframes: list[str],
    category: int,
    property_name: str,
    hl: str,
) -> dict[str, Any]:
    if not configured_dataforseo():
        raise TrendsError("DataForSEO Google Trends provider is not configured")

    auth = (os.environ["DATAFORSEO_LOGIN"], os.environ["DATAFORSEO_PASSWORD"])
    windows = []
    detail_timeframe = "today 3-m" if "today 3-m" in timeframes else timeframes[0]
    for timeframe in timeframes:
        body = [
            {
                "keywords": [query],
                "location_name": dataforseo_location_name(geo),
                "language_name": dataforseo_language_name(hl),
                "type": DATAFORSEO_TYPE_MAP.get(property_name or "", "web"),
                "category_code": category,
                "time_range": DATAFORSEO_TIMEFRAME_MAP.get(timeframe, "past_90_days"),
                "item_types": (
                    ["google_trends_graph", "google_trends_map", "google_trends_queries_list"]
                    if timeframe == detail_timeframe
                    else ["google_trends_graph"]
                ),
            }
        ]
        response = requests.post(
            DATAFORSEO_EXPLORE_URL,
            auth=auth,
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=45,
        )
        if response.status_code != 200:
            windows.append(
                build_empty_window(
                    timeframe,
                    provider="dataforseo",
                    error=f"HTTP {response.status_code}",
                    notes=[f"DataForSEO provider returned HTTP {response.status_code} for {timeframe_label(timeframe)}."],
                )
            )
            continue

        payload = response.json()
        tasks = payload.get("tasks") or []
        task = tasks[0] if tasks else {}
        if payload.get("status_code") != 20000 or task.get("status_code", 0) >= 30000:
            windows.append(
                build_empty_window(
                    timeframe,
                    provider="dataforseo",
                    error=f"status_code={task.get('status_code') or payload.get('status_code')}",
                    notes=[str(task.get("status_message") or payload.get("status_message") or "DataForSEO request failed")],
                )
            )
            continue
        results = task.get("result") or []
        if not results:
            windows.append(
                build_empty_window(
                    timeframe,
                    provider="dataforseo",
                    error="empty-result",
                    notes=["DataForSEO returned no trend result items for this timeframe."],
                )
            )
            continue
        windows.append(normalize_dataforseo_window(results[0], timeframe=timeframe))

    return build_payload(
        query=query,
        geo=geo,
        hl=hl,
        property_name=property_name,
        provider="dataforseo-google-trends",
        windows=windows,
        notes=[
            "DataForSEO Google Trends Explore Live was used as a fallback provider.",
            "Provider-specific fields are normalized into the standard window format.",
        ],
    )


def summarize_windows(windows: list[dict[str, Any]]) -> dict[str, Any]:
    shape_by_window = {}
    top_rising = []
    top_regions = []
    available_windows = 0
    for window in windows:
        label = window["label"]
        shape_by_window[label] = window["interest_over_time"]["summary"].get("shape")
        if window.get("available"):
            available_windows += 1
        if not top_rising and window["related_queries"]["rising"]:
            top_rising = window["related_queries"]["rising"][:5]
        if not top_regions and window["interest_by_region"]:
            top_regions = window["interest_by_region"][:5]

    preferred = next((shape_by_window[label] for label in ["90d", "12m", "30d", "5y"] if label in shape_by_window), None)
    return {
        "available_windows": available_windows,
        "all_windows_available": available_windows == len(windows),
        "shape_by_window": shape_by_window,
        "primary_shape": preferred or "unknown",
        "top_rising_queries": top_rising,
        "top_regions": top_regions,
    }


def collect_official(
    query: str,
    *,
    geo: str = "US",
    timeframes: list[str] | None = None,
    category: int = 0,
    property_name: str = "",
    hl: str = "en-US",
    tz: int = -480,
    browser_session: str = "dvos-trends",
) -> dict[str, Any]:
    session = requests_session()
    selected_timeframes = timeframes or DEFAULT_TIMEFRAMES
    detail_timeframe = "today 3-m" if "today 3-m" in selected_timeframes else selected_timeframes[0]
    windows = []
    for timeframe in selected_timeframes:
        windows.append(
            collect_timeframe(
                session=session,
                query=query,
                geo=geo,
                timeframe=timeframe,
                category=category,
                property_name=property_name,
                hl=hl,
                tz=tz,
                browser_session=browser_session,
                include_regions=timeframe == detail_timeframe,
                include_related=timeframe == detail_timeframe,
            )
        )
    return build_payload(
        query=query,
        geo=geo,
        hl=hl,
        property_name=property_name,
        provider="google-trends",
        windows=windows,
        notes=[
            "Explore metadata is fetched with direct HTTP requests.",
            "Widget data falls back to a same-origin browser request when Google returns HTTP 429 to direct calls.",
            "Google Trends values are normalized interest, not absolute search volume.",
        ],
    )


def collect(
    query: str,
    *,
    geo: str = "US",
    timeframes: list[str] | None = None,
    category: int = 0,
    property_name: str = "",
    hl: str = "en-US",
    tz: int = -480,
    browser_session: str = "dvos-trends",
) -> dict[str, Any]:
    selected_timeframes = timeframes or DEFAULT_TIMEFRAMES
    provider_attempts: list[dict[str, Any]] = []

    try:
        official = collect_official(
            query,
            geo=geo,
            timeframes=selected_timeframes,
            category=category,
            property_name=property_name,
            hl=hl,
            tz=tz,
            browser_session=browser_session,
        )
    except Exception as exc:
        official = build_payload(
            query=query,
            geo=geo,
            hl=hl,
            property_name=property_name,
            provider="google-trends",
            windows=[
                build_empty_window(
                    timeframe,
                    provider="google-trends",
                    error=f"{type(exc).__name__}: {exc}",
                    notes=[f"Official Google Trends collection raised {type(exc).__name__} before windows could be collected."],
                )
                for timeframe in selected_timeframes
            ],
            notes=[
                "Official Google Trends collection failed before structured windows were available.",
            ],
        )
    provider_attempts.append(
        {
            "provider": "google-trends",
            "configured": True,
            "available": official.get("available", False),
        }
    )
    if official.get("available"):
        official["provider_attempts"] = provider_attempts
        return official

    if configured_rapidapi():
        try:
            rapidapi = collect_rapidapi(
                query,
                geo=geo,
                timeframes=selected_timeframes,
                property_name=property_name,
                hl=hl,
            )
            provider_attempts.append(
                {
                    "provider": "rapidapi-google-trends",
                    "configured": True,
                    "available": rapidapi.get("available", False),
                }
            )
            if rapidapi.get("available"):
                rapidapi["provider_attempts"] = provider_attempts
                rapidapi["notes"] = official.get("notes", []) + rapidapi.get("notes", [])
                return rapidapi
        except Exception as exc:
            provider_attempts.append(
                {
                    "provider": "rapidapi-google-trends",
                    "configured": True,
                    "available": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    else:
        provider_attempts.append(
            {
                "provider": "rapidapi-google-trends",
                "configured": False,
                "available": False,
            }
        )

    if configured_dataforseo():
        try:
            dataforseo = collect_dataforseo(
                query,
                geo=geo,
                timeframes=selected_timeframes,
                category=category,
                property_name=property_name,
                hl=hl,
            )
            provider_attempts.append(
                {
                    "provider": "dataforseo-google-trends",
                    "configured": True,
                    "available": dataforseo.get("available", False),
                }
            )
            if dataforseo.get("available"):
                dataforseo["provider_attempts"] = provider_attempts
                dataforseo["notes"] = official.get("notes", []) + dataforseo.get("notes", [])
                return dataforseo
        except Exception as exc:
            provider_attempts.append(
                {
                    "provider": "dataforseo-google-trends",
                    "configured": True,
                    "available": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    else:
        provider_attempts.append(
            {
                "provider": "dataforseo-google-trends",
                "configured": False,
                "available": False,
            }
        )

    official["provider_attempts"] = provider_attempts
    official["notes"] = official.get("notes", []) + [
        "All configured Google Trends providers failed or returned no usable data.",
    ]
    return official


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture structured Google Trends evidence.")
    parser.add_argument("--query", required=True, help="Keyword or topic to inspect")
    parser.add_argument("--geo", default="US", help="Country code, default US")
    parser.add_argument("--timeframe", action="append", dest="timeframes", help="Timeframe, may be repeated")
    parser.add_argument("--category", type=int, default=0)
    parser.add_argument("--property", default="")
    parser.add_argument("--hl", default="en-US")
    parser.add_argument("--tz", type=int, default=-480)
    parser.add_argument("--browser-session", default=os.environ.get("BROWSE_SESSION", "dvos-trends"))
    parser.add_argument("--output", help="Write JSON to a file")
    args = parser.parse_args()

    data = collect(
        args.query,
        geo=args.geo,
        timeframes=args.timeframes or DEFAULT_TIMEFRAMES,
        category=args.category,
        property_name=args.property,
        hl=args.hl,
        tz=args.tz,
        browser_session=args.browser_session,
    )
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
