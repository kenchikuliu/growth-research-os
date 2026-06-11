#!/usr/bin/env python3
"""Local HTTP/JSON service for full demand-validation workflow execution."""

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

import run_demand_workflow
from browser_capture import iso_utc_now


SERVICE_NAME = "demand-validation-os.workflow_service"
SERVICE_VERSION = "2026-06-11"
WORKFLOW_LOCK = threading.Lock()


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


def build_workflow_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    mode = (payload.get("mode") or "").strip()
    if mode not in {"demand", "attribution"}:
        raise ValueError("mode must be 'demand' or 'attribution'.")

    query = (payload.get("query") or "").strip()
    if not query:
        raise ValueError("Missing query.")

    domain = (payload.get("domain") or "").strip() or None
    bundle_payload = payload.get("bundle_payload")
    bundle_input = payload.get("bundle_input") or None
    needs_live_capture = bool(domain and not bundle_input and not bundle_payload)
    username, password = credentials_from_payload(payload)
    if needs_live_capture and (not username or not password):
        raise ValueError("Missing 3ue credentials for live capture.")

    return {
        "mode": mode,
        "query": query,
        "domain": domain or (query if run_demand_workflow.looks_like_domain(query) else None),
        "geo": (payload.get("geo") or "US").strip() or "US",
        "username": username,
        "password": password,
        "max_node_rotations": int(payload.get("max_node_rotations", 2)),
        "brand_name": payload.get("brand_name") or "",
        "brand_url": payload.get("brand_url") or "",
        "primary_cta_url": payload.get("primary_cta_url") or "",
        "primary_cta_label": payload.get("primary_cta_label") or "",
        "bundle_input": bundle_input,
        "bundle_payload": bundle_payload,
        "trends_input": payload.get("trends_input") or None,
    }


def build_scale_output(workflow: dict[str, Any]) -> dict[str, Any]:
    report = workflow.get("report") or {}
    decision = workflow.get("decision") or {}
    artifacts = (workflow.get("artifacts") or {}).get("page_artifacts") or {}
    normalized = ((workflow.get("evidence") or {}).get("tool_capture") or {}).get("normalized") or {}
    return {
        "mode": workflow.get("mode"),
        "query": (workflow.get("input") or {}).get("query"),
        "domain": (workflow.get("input") or {}).get("domain"),
        "decision": {
            "band": decision.get("band"),
            "recommended_action": decision.get("recommended_action"),
            "total_score": decision.get("total_score"),
            "all_hard_gates_passed": decision.get("all_hard_gates_passed"),
        },
        "direct_answer": {
            "core_conclusion": report.get("core_conclusion"),
            "recommended_action": report.get("recommended_action") or decision.get("recommended_action"),
            "page_type_recommendation": report.get("page_type_recommendation"),
            "main_growth_terms": report.get("main_growth_terms"),
            "main_growth_pages": report.get("main_growth_pages"),
        },
        "page_plan": {
            "first_batch_of_pages": report.get("first_batch_of_pages") or [],
            "page_artifact_count": artifacts.get("page_count", 0),
            "artifacts_available": bool(artifacts.get("available")),
        },
        "normalized_snapshot": {
            "tools_ready": normalized.get("tools_ready") or [],
            "coverage": normalized.get("coverage") or {},
            "traffic_summary": normalized.get("traffic_summary") or {},
            "top_page_count": len(normalized.get("top_pages") or []),
            "top_keyword_count": len(normalized.get("top_keywords") or []),
            "landing_page_count": len(normalized.get("landing_pages") or []),
            "page_cluster_count": len(normalized.get("page_clusters") or []),
        },
        "artifacts": artifacts,
    }


class WorkflowServiceHandler(BaseHTTPRequestHandler):
    server_version = "WorkflowService/1.0"
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
                "busy": WORKFLOW_LOCK.locked(),
                "supported_modes": ["demand", "attribution"],
                "policy": {
                    "capture_scope": "single_device_single_browser_single_active_page_serial",
                    "workflow_scope": "single_request_at_a_time",
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
        if parsed.path not in {"/workflow", "/workflow/page-artifacts"}:
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

        if not WORKFLOW_LOCK.acquire(blocking=False):
            status, error_payload = make_error(
                status=HTTPStatus.CONFLICT,
                code="workflow_busy",
                message="Another workflow is already running. This service stays serial to protect the capture layer.",
                request_id=request_id,
            )
            self.write_json(status, error_payload)
            return

        try:
            kwargs = build_workflow_kwargs(payload)
            workflow = run_demand_workflow.build_workflow(**kwargs)
            if parsed.path == "/workflow/page-artifacts":
                data = {
                    "workflow_summary": build_scale_output(workflow),
                    "page_artifacts": (workflow.get("artifacts") or {}).get("page_artifacts") or {},
                }
            else:
                data = {
                    "workflow": workflow,
                    "scale_output": build_scale_output(workflow),
                }
            response = {
                **response_meta(request_id),
                "ok": True,
                "data": data,
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
                code="workflow_failed",
                message="Workflow service failed.",
                request_id=request_id,
                details={
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            self.write_json(status, error_payload)
        finally:
            WORKFLOW_LOCK.release()


def build_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), WorkflowServiceHandler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local HTTP/JSON service for full demand-validation workflows.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    server = build_server(args.host, args.port)
    print(
        json.dumps(
            {
                "service": SERVICE_NAME,
                "version": SERVICE_VERSION,
                "host": args.host,
                "port": args.port,
                "supported_modes": ["demand", "attribution"],
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
