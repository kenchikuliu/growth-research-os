#!/usr/bin/env python3
"""Adapter for live and manual seo.web.cafe KD evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import requests

from browser_capture import iso_utc_now


KD_HOME_URL = "https://seo.web.cafe/kd/"
KD_API_URL = "https://seo.web.cafe/kd/api/kd"
TOKEN_PATTERN = re.compile(r'name="kd-token"\s+content="([^"]+)"')
DEFAULT_TIMEOUT = 30
CACHE_DIR = Path.home() / ".cache" / "growth-research-os" / "web_cafe_kd"


def classify_kd_bucket(value: int | float | None) -> str:
    if value is None:
        return "unknown"
    if value <= 14:
        return "easy"
    if value <= 29:
        return "possible"
    if value <= 49:
        return "moderate"
    if value <= 69:
        return "hard"
    return "very_hard"


def infer_kd_guidance(value: int | float | None) -> str:
    bucket = classify_kd_bucket(value)
    return {
        "easy": "优先考虑直接切入，适合先做单页或首批 cluster。",
        "possible": "可以切入，但更适合找更窄页面型或替代词开局。",
        "moderate": "不要只看这个词本身，先找对比页、模板页或长尾场景页切入。",
        "hard": "正面抢主词风险高，更适合 brand alternative、scenario、template 或 narrower cluster。",
        "very_hard": "不建议直接正面争夺主词，优先做截流页、替代页或明显更窄的意图页面。",
        "unknown": "当前没有稳定 KD 值，不能把难度判断当成定量结论。",
    }[bucket]


def session_with_headers() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
            )
        }
    )
    return session


def extract_page_token(html: str) -> str | None:
    match = TOKEN_PATTERN.search(html or "")
    return match.group(1) if match else None


def round_score(value: Any) -> float | int | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric.is_integer():
        return int(numeric)
    return round(numeric, 1)


def kd_level_to_bucket(level: str | None, score: int | float | None) -> str:
    normalized = (level or "").strip()
    by_label = {
        "极易": "easy",
        "容易": "possible",
        "中等": "moderate",
        "困难": "hard",
        "极难": "very_hard",
    }.get(normalized)
    return by_label or classify_kd_bucket(score)


def normalize_detail_rows(rows: list[Any] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "position": row.get("position"),
                "domain": row.get("domain"),
                "url": row.get("url"),
                "title": row.get("title"),
                "page_type": row.get("pageType"),
                "is_homepage": row.get("isHomepage"),
                "dr": row.get("dr"),
                "monthly_visits": row.get("visits"),
                "monthly_visits_label": row.get("visitsLabel"),
                "age_years": row.get("ageYears"),
                "age_label": row.get("ageLabel"),
                "dedicated": row.get("dedicated"),
                "title_hit": row.get("titleHit"),
                "keyword_hit": row.get("kwHit"),
                "keyword_hit_term": row.get("kwHitTerm"),
                "keyword_hit_traffic": row.get("kwHitTraffic"),
                "search_share": row.get("searchShare"),
                "sitelinks": row.get("sitelinks"),
                "engagement": row.get("eng"),
                "strength": row.get("strength"),
                "contribution": row.get("contribution"),
                "data_note": row.get("dataNote"),
            }
        )
    return normalized


def normalize_api_payload(
    *,
    query: str,
    gl: str,
    raw: dict[str, Any],
    request_meta: dict[str, Any],
) -> dict[str, Any]:
    score = round_score(raw.get("score"))
    generic_score = round_score(raw.get("genericScore"))
    bucket = kd_level_to_bucket(raw.get("level"), score)
    keyword_type = raw.get("keywordType")
    link_budget = raw.get("linkBudget") if isinstance(raw.get("linkBudget"), dict) else None
    keyword_trend = raw.get("keywordTrend") if isinstance(raw.get("keywordTrend"), dict) else None
    details = normalize_detail_rows(raw.get("details"))

    notes: list[str] = []
    if raw.get("cached") is True:
        notes.append("Result came from web.cafe 7-day cache.")
    if keyword_type == "brand":
        notes.append("Brand-mode KD represents interception difficulty, not direct official-site competition.")

    return {
        "query": query,
        "gl": gl.lower(),
        "source": {
            "provider": "web-cafe-kd",
            "url": KD_HOME_URL,
            "api_url": KD_API_URL,
            "captured_at": iso_utc_now(),
            "mode": "live_page_token_api",
        },
        "available": score is not None,
        "kd_score": score,
        "kd_bucket": bucket,
        "guidance": infer_kd_guidance(score),
        "level_label": raw.get("level"),
        "keyword_type": keyword_type,
        "generic_score": generic_score,
        "keyword_volume": raw.get("keywordVolume"),
        "keyword_trend": keyword_trend,
        "link_budget": link_budget,
        "reasons": raw.get("reasons") or [],
        "details": details,
        "top_competitors": [
            {
                "position": row.get("position"),
                "domain": row.get("domain"),
                "page_type": row.get("page_type"),
                "dr": row.get("dr"),
                "monthly_visits": row.get("monthly_visits"),
                "monthly_visits_label": row.get("monthly_visits_label"),
                "strength": row.get("strength"),
                "contribution": row.get("contribution"),
            }
            for row in details[:10]
        ],
        "request": {
            "gl": gl.lower(),
            "hl": request_meta.get("hl") or "en",
            "force": bool(request_meta.get("force")),
        },
        "cache": {
            "cached": bool(raw.get("cached")),
            "computed_at": raw.get("computedAt"),
        },
        "raw": raw,
        "notes": notes,
    }


def build_payload(
    *,
    query: str,
    kd_score: int | float | None = None,
    source_url: str = KD_HOME_URL,
    notes: list[str] | None = None,
    mode: str = "manual",
) -> dict[str, Any]:
    return {
        "query": query,
        "source": {
            "provider": "web-cafe-kd",
            "url": source_url,
            "captured_at": iso_utc_now(),
            "mode": mode,
        },
        "available": kd_score is not None,
        "kd_score": round_score(kd_score),
        "kd_bucket": classify_kd_bucket(kd_score),
        "guidance": infer_kd_guidance(kd_score),
        "notes": notes or [],
    }


def cache_key(*, query: str, gl: str, hl: str) -> str:
    digest = hashlib.sha256(f"{query.strip().lower()}|{gl.lower()}|{hl.lower()}".encode("utf-8")).hexdigest()
    return digest[:32]


def cache_path(*, query: str, gl: str, hl: str) -> Path:
    return CACHE_DIR / f"{cache_key(query=query, gl=gl, hl=hl)}.json"


def read_cached_payload(*, query: str, gl: str, hl: str) -> dict[str, Any] | None:
    path = cache_path(query=query, gl=gl, hl=hl)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def write_cached_payload(payload: dict[str, Any], *, query: str, gl: str, hl: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path(query=query, gl=gl, hl=hl).write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def fetch_home_html(
    *,
    session: requests.Session | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[requests.Session, str]:
    active = session or session_with_headers()
    response = active.get(KD_HOME_URL, timeout=timeout)
    response.raise_for_status()
    return active, response.text


def fetch_live_payload(
    *,
    query: str,
    gl: str = "us",
    hl: str = "en",
    force: bool = False,
    token: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    session, html = fetch_home_html(timeout=timeout)
    page_token = token or extract_page_token(html)
    if not page_token:
        raise RuntimeError("web.cafe KD page token missing")

    response = session.get(
        KD_API_URL,
        params={
            "keyword": query,
            "gl": gl.lower(),
            "hl": hl,
            **({"force": 1} if force else {}),
        },
        headers={
            "X-KD-Token": page_token,
            "Referer": KD_HOME_URL,
            "Origin": "https://seo.web.cafe",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, dict):
        raise RuntimeError("web.cafe KD response was not a JSON object")
    if raw.get("error"):
        raise RuntimeError(str(raw.get("error")))
    payload = normalize_api_payload(
        query=query,
        gl=gl,
        raw=raw,
        request_meta={"hl": hl, "force": force},
    )
    write_cached_payload(payload, query=query, gl=gl, hl=hl)
    return payload


def collect(
    *,
    query: str,
    kd_score: int | float | None = None,
    kd_input: str | None = None,
    live: bool = True,
    gl: str = "us",
    hl: str = "en",
    force: bool = False,
    token: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    normalized_gl = gl.lower()
    normalized_hl = hl.lower()
    if kd_input:
        payload = json.loads(Path(kd_input).read_text())
        if isinstance(payload, dict):
            return payload
    if kd_score is not None:
        return build_payload(
            query=query,
            kd_score=kd_score,
            notes=["Manual KD override provided by caller."],
            mode="manual_score",
        )
    if live:
        try:
            return fetch_live_payload(
                query=query,
                gl=normalized_gl,
                hl=normalized_hl,
                force=force,
                token=token,
                timeout=timeout,
            )
        except Exception as exc:
            cached = read_cached_payload(query=query, gl=normalized_gl, hl=normalized_hl)
            if cached:
                notes = list(cached.get("notes") or [])
                notes.append(f"Live web.cafe KD fetch failed and cached result was reused: {type(exc).__name__}: {exc}")
                cached["notes"] = notes
                cached_source = dict(cached.get("source") or {})
                cached_source["mode"] = "cached_fallback_after_live_failure"
                cached["source"] = cached_source
                return cached
            return build_payload(
                query=query,
                notes=[f"Live web.cafe KD fetch failed: {type(exc).__name__}: {exc}"],
                mode="live_failed",
            )
    return build_payload(
        query=query,
        notes=["Live web.cafe KD fetch disabled."],
        mode="disabled",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect web.cafe KD evidence as normalized JSON.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--kd-score", type=float)
    parser.add_argument("--kd-input", help="Reuse an existing KD JSON payload")
    parser.add_argument("--gl", default="us", help="Google country code for live KD fetch")
    parser.add_argument("--hl", default="en", help="Language code for live KD fetch")
    parser.add_argument("--force", action="store_true", help="Force live KD recompute instead of cached result")
    parser.add_argument("--token", help="Optional explicit page token override")
    parser.add_argument("--disable-live", action="store_true", help="Skip live web.cafe fetch and fall back to manual/unknown")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--output")
    args = parser.parse_args()

    payload = collect(
        query=args.query,
        kd_score=args.kd_score,
        kd_input=args.kd_input,
        live=not args.disable_live,
        gl=args.gl,
        hl=args.hl,
        force=args.force,
        token=args.token,
        timeout=args.timeout,
    )
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
