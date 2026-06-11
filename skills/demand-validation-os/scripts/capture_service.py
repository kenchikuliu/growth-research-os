#!/usr/bin/env python3
"""Local HTTP/JSON service for the unified 3ue capture API."""

from __future__ import annotations

import argparse
import json
import os
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import capture_api
from browser_capture import iso_utc_now
from capture_normalize import build_normalized_capture


SERVICE_NAME = "demand-validation-os.capture_service"
SERVICE_VERSION = "2026-06-11"
SERVICE_LOCK = threading.Lock()


def json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def request_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    body = handler.rfile.read(length)
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def response_meta(request_id: str | None = None) -> dict[str, Any]:
    return {
        "service": {
            "name": SERVICE_NAME,
            "version": SERVICE_VERSION,
        },
        "served_at": iso_utc_now(),
        "request_id": request_id or None,
    }


def make_error(
    *,
    status: int,
    code: str,
    message: str,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    payload = {
        **response_meta(request_id),
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
    return status, payload


def credentials_from_payload(payload: dict[str, Any]) -> tuple[str, str]:
    username = (payload.get("username") or os.environ.get("THREEUE_USERNAME") or "").strip()
    password = payload.get("password") or os.environ.get("THREEUE_PASSWORD") or ""
    return username, password


def build_capture_kwargs(payload: dict[str, Any], tool_override: str | None = None) -> dict[str, Any]:
    username, password = credentials_from_payload(payload)
    if not username or not password:
        raise ValueError("Missing 3ue credentials. Pass username/password or set THREEUE_USERNAME / THREEUE_PASSWORD.")

    query = (payload.get("query") or "").strip()
    if not query:
        raise ValueError("Missing query.")

    tools = payload.get("tools")
    if tool_override:
        tools = [tool_override]

    return {
        "query": query,
        "username": username,
        "password": password,
        "tools": tools,
        "session_prefix": payload.get("session_prefix") or "dvos-service",
        "keep_session": bool(payload.get("keep_session", False)),
        "max_node_rotations": int(payload.get("max_node_rotations", 2)),
        "continue_on_error": bool(payload.get("continue_on_error", False)),
        "request_id": payload.get("request_id") or "",
    }


class CaptureServiceHandler(BaseHTTPRequestHandler):
    server_version = "CaptureService/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            qs = parse_qs(parsed.query)
            payload = {
                **response_meta(qs.get("request_id", [None])[0]),
                "ok": True,
                "status": "healthy",
                "busy": SERVICE_LOCK.locked(),
                "policy": {
                    "device_scope": "single_device",
                    "browser_scope": "single_browser",
                    "page_scope": "single_active_page",
                    "run_mode": "serial",
                },
            }
            self.write_json(HTTPStatus.OK, payload)
            return

        status, payload = make_error(
            status=HTTPStatus.NOT_FOUND,
            code="not_found",
            message=f"Unknown path: {parsed.path}",
        )
        self.write_json(status, payload)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = request_json(self)
        except json.JSONDecodeError as exc:
            status, error_payload = make_error(
                status=HTTPStatus.BAD_REQUEST,
                code="invalid_json",
                message="Request body must be valid JSON.",
                details={"error": str(exc)},
            )
            self.write_json(status, error_payload)
            return

        request_id = payload.get("request_id") if isinstance(payload, dict) else None

        if parsed.path not in {"/capture", "/capture/tool"}:
            status, error_payload = make_error(
                status=HTTPStatus.NOT_FOUND,
                code="not_found",
                message=f"Unknown path: {parsed.path}",
                request_id=request_id,
            )
            self.write_json(status, error_payload)
            return

        if not isinstance(payload, dict):
            status, error_payload = make_error(
                status=HTTPStatus.BAD_REQUEST,
                code="invalid_payload",
                message="JSON body must be an object.",
                request_id=request_id,
            )
            self.write_json(status, error_payload)
            return

        tool_override = None
        if parsed.path == "/capture/tool":
            tool_override = (payload.get("tool") or "").strip()
            if tool_override not in capture_api.SUPPORTED_TOOLS:
                status, error_payload = make_error(
                    status=HTTPStatus.BAD_REQUEST,
                    code="invalid_tool",
                    message=f"tool must be one of: {', '.join(capture_api.SUPPORTED_TOOLS)}",
                    request_id=request_id,
                )
                self.write_json(status, error_payload)
                return

        if not SERVICE_LOCK.acquire(blocking=False):
            status, error_payload = make_error(
                status=HTTPStatus.CONFLICT,
                code="capture_busy",
                message="Another capture is already running. This service enforces serial execution.",
                request_id=request_id,
                details={
                    "device_scope": "single_device",
                    "browser_scope": "single_browser",
                    "page_scope": "single_active_page",
                    "run_mode": "serial",
                },
            )
            self.write_json(status, error_payload)
            return

        try:
            kwargs = build_capture_kwargs(payload, tool_override=tool_override)
            bundle = capture_api.run_capture_plan(**kwargs)
            if payload.get("normalize") is False:
                bundle = dict(bundle)
                bundle.pop("normalized", None)
            elif "normalized" not in bundle:
                bundle["normalized"] = build_normalized_capture(bundle)
            response = {
                **response_meta(kwargs.get("request_id") or None),
                "ok": True,
                "data": bundle,
            }
            self.write_json(HTTPStatus.OK, response)
        except ValueError as exc:
            status, error_payload = make_error(
                status=HTTPStatus.BAD_REQUEST,
                code="bad_request",
                message=str(exc),
                request_id=request_id,
            )
            self.write_json(status, error_payload)
        except Exception as exc:  # pragma: no cover
            status, error_payload = make_error(
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="capture_failed",
                message="Capture service failed.",
                request_id=request_id,
                details={
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            self.write_json(status, error_payload)
        finally:
            SERVICE_LOCK.release()


def build_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), CaptureServiceHandler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local HTTP/JSON service for serial 3ue-backed capture.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = build_server(args.host, args.port)
    print(
        json.dumps(
            {
                "service": SERVICE_NAME,
                "version": SERVICE_VERSION,
                "host": args.host,
                "port": args.port,
                "policy": {
                    "device_scope": "single_device",
                    "browser_scope": "single_browser",
                    "page_scope": "single_active_page",
                    "run_mode": "serial",
                },
            },
            ensure_ascii=False,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
