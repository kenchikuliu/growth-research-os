#!/usr/bin/env python3
"""Backward-compatible wrapper around capture_api."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from capture_api import (
    SUPPORTED_TOOLS,
    assess_capture_quality,
    preferred_attempts,
    pick_better_result,
    run_capture_once,
    run_capture_plan,
    run_capture_with_retries,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Semrush and Similarweb captures serially and emit a combined JSON bundle.")
    parser.add_argument("--query", required=True, help="Domain to inspect")
    parser.add_argument("--username", default=os.environ.get("THREEUE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("THREEUE_PASSWORD", ""))
    parser.add_argument("--session-prefix", default="dvos-bundle", help="Base session prefix for serial tool runs")
    parser.add_argument("--output", help="Write combined JSON bundle to a file")
    parser.add_argument(
        "--tools",
        nargs="+",
        choices=list(SUPPORTED_TOOLS),
        default=list(SUPPORTED_TOOLS),
        help="Tools to run, in order. Default: semrush similarweb",
    )
    parser.add_argument("--keep-session", action="store_true", help="Keep the final tool session(s) open after capture")
    parser.add_argument(
        "--max-node-rotations",
        type=int,
        default=2,
        help="Rotate to a different 3ue node when daily usage limit is detected",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue to the next tool if one capture fails. Default behavior is fail fast.",
    )
    args = parser.parse_args()

    if not args.username or not args.password:
        raise SystemExit("Missing 3ue credentials. Set THREEUE_USERNAME and THREEUE_PASSWORD or pass --username/--password.")

    bundle = run_capture_plan(
        query=args.query,
        username=args.username,
        password=args.password,
        tools=args.tools,
        session_prefix=args.session_prefix,
        keep_session=args.keep_session,
        max_node_rotations=args.max_node_rotations,
        continue_on_error=args.continue_on_error,
        request_id="capture-bundle-cli",
    )
    text = json.dumps(bundle, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text)
    print(text)
    return 0 if bundle["summary"]["all_succeeded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
