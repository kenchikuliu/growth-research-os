#!/usr/bin/env python3
"""Lightweight adapter for seo.web.cafe KD-style evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from browser_capture import iso_utc_now


def classify_kd_bucket(value: int | None) -> str:
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


def infer_kd_guidance(value: int | None) -> str:
    bucket = classify_kd_bucket(value)
    return {
        "easy": "优先考虑直接切入，适合先做单页或首批 cluster。",
        "possible": "可以切入，但更适合找更窄页面型或替代词开局。",
        "moderate": "不要只看这个词本身，先找对比页、模板页或长尾场景页切入。",
        "hard": "正面抢主词风险高，更适合 brand alternative、scenario、template 或 narrower cluster。",
        "very_hard": "不建议直接正面争夺主词，优先做截流页、替代页或明显更窄的意图页面。",
        "unknown": "当前没有稳定 KD 值，不能把难度判断当成定量结论。",
    }[bucket]


def build_payload(
    *,
    query: str,
    kd_score: int | None = None,
    source_url: str = "https://seo.web.cafe/kd/",
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "query": query,
        "source": {
            "provider": "web-cafe-kd",
            "url": source_url,
            "captured_at": iso_utc_now(),
        },
        "available": kd_score is not None,
        "kd_score": kd_score,
        "kd_bucket": classify_kd_bucket(kd_score),
        "guidance": infer_kd_guidance(kd_score),
        "notes": notes or [],
    }


def collect(
    *,
    query: str,
    kd_score: int | None = None,
    kd_input: str | None = None,
) -> dict[str, Any]:
    if kd_input:
        payload = json.loads(Path(kd_input).read_text())
        if isinstance(payload, dict):
            return payload
    return build_payload(query=query, kd_score=kd_score)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a lightweight web.cafe KD evidence payload.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--kd-score", type=int)
    parser.add_argument("--kd-input", help="Reuse an existing KD JSON payload")
    parser.add_argument("--output")
    args = parser.parse_args()

    payload = collect(query=args.query, kd_score=args.kd_score, kd_input=args.kd_input)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

