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
from workflow_scale import build_scale_output, parse_csv_set, rank_filtered_pairs


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
        "kd_input": payload.get("kd_input") or None,
        "kd_score": payload.get("kd_score"),
    }


def compact_result(result: dict[str, Any], include_workflow: bool) -> dict[str, Any]:
    if include_workflow:
        return result
    return {
        "scale_output": result.get("scale_output") or {},
        "page_artifacts": result.get("page_artifacts") or {},
        "playbook": result.get("playbook") or {},
    }


def flatten_scale_result(*, index: int | None, mode: str | None, query: str | None, result: dict[str, Any]) -> dict[str, Any]:
    scale_output = result.get("scale_output") or {}
    decision = scale_output.get("decision") or {}
    direct_answer = scale_output.get("direct_answer") or {}
    page_plan = scale_output.get("page_plan") or {}
    normalized_snapshot = scale_output.get("normalized_snapshot") or {}
    page_artifacts = result.get("page_artifacts") or {}
    first_pages = page_plan.get("first_batch_of_pages") or []
    slugs = [page.get("slug") for page in (page_artifacts.get("pages") or []) if isinstance(page, dict) and page.get("slug")]
    return {
        "index": index if index is not None else "",
        "mode": mode or scale_output.get("mode") or "",
        "query": query or scale_output.get("query") or "",
        "domain": scale_output.get("domain") or "",
        "band": decision.get("band") or "",
        "recommended_action": decision.get("recommended_action") or "",
        "total_score": decision.get("total_score") or "",
        "all_hard_gates_passed": decision.get("all_hard_gates_passed"),
        "core_conclusion": direct_answer.get("core_conclusion") or "",
        "page_type_recommendation": direct_answer.get("page_type_recommendation") or "",
        "tools_ready": ",".join(normalized_snapshot.get("tools_ready") or []),
        "top_page_count": normalized_snapshot.get("top_page_count") or 0,
        "top_keyword_count": normalized_snapshot.get("top_keyword_count") or 0,
        "landing_page_count": normalized_snapshot.get("landing_page_count") or 0,
        "page_cluster_count": normalized_snapshot.get("page_cluster_count") or 0,
        "page_artifact_count": page_plan.get("page_artifact_count") or 0,
        "artifacts_available": page_plan.get("artifacts_available"),
        "first_page_titles": " | ".join(
            page.get("working_title") or page.get("primary_keyword") or ""
            for page in first_pages
            if isinstance(page, dict)
        ),
        "artifact_slugs": " | ".join(slugs),
    }


def run_workflow_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    kwargs = build_workflow_kwargs(payload)
    workflow = run_demand_workflow.build_workflow(**kwargs)
    scale_output = build_scale_output(workflow)
    return {
        "workflow": workflow,
        "scale_output": scale_output,
        "page_artifacts": scale_output.get("artifacts") or {},
        "playbook": workflow.get("playbook") or {},
    }


def build_scale_batch_response(payload: dict[str, Any]) -> dict[str, Any]:
    jobs = payload.get("jobs")
    include_workflow = bool(payload.get("include_workflow"))
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("scale batch requests must include a non-empty 'jobs' array.")

    results = []
    flat_rows = []
    for idx, job in enumerate(jobs, start=1):
        if not isinstance(job, dict):
            raise ValueError("Each job in 'jobs' must be an object.")
        merged_job = {**payload, **job}
        merged_job.pop("jobs", None)
        result = run_workflow_from_payload(merged_job)
        mode = merged_job.get("mode")
        query = merged_job.get("query")
        results.append(
            {
                "index": idx,
                "mode": mode,
                "query": query,
                **compact_result(result, include_workflow),
            }
        )
        flat_rows.append(flatten_scale_result(index=idx, mode=mode, query=query, result=result))

    allowed_actions = parse_csv_set(payload.get("allowed_actions"))
    required_tools = parse_csv_set(payload.get("require_tools_ready"))
    results, flat_rows = rank_filtered_pairs(
        results,
        flat_rows,
        min_score=payload.get("min_score"),
        allowed_actions=allowed_actions or None,
        require_tools_ready=required_tools or None,
        sort_by=(payload.get("sort_by") or "total_score"),
        ascending=bool(payload.get("ascending")),
        top=payload.get("top"),
    )
    return {
        "job_count": len(results),
        "filters": {
            "min_score": payload.get("min_score"),
            "allowed_actions": sorted(allowed_actions),
            "require_tools_ready": sorted(required_tools),
            "sort_by": payload.get("sort_by") or "total_score",
            "ascending": bool(payload.get("ascending")),
            "top": payload.get("top"),
        },
        "results": results,
        "table_rows": flat_rows,
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
        if parsed.path not in {
            "/workflow",
            "/workflow/page-artifacts",
            "/workflow/playbook",
            "/scale",
            "/scale/page-artifacts",
            "/scale/playbook",
        }:
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

        if parsed.path.startswith("/workflow") and isinstance(payload.get("jobs"), list):
            status, error_payload = make_error(
                status=HTTPStatus.BAD_REQUEST,
                code="invalid_payload",
                message="Batch jobs are only supported on /scale and /scale/page-artifacts.",
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
            if parsed.path.startswith("/scale") and isinstance(payload.get("jobs"), list):
                data = build_scale_batch_response(payload)
            else:
                result = run_workflow_from_payload(payload)
                workflow = result["workflow"]
                scale_output = result["scale_output"]
                page_artifacts = result["page_artifacts"]
                if parsed.path == "/workflow/page-artifacts":
                    data = {
                        "workflow_summary": scale_output,
                        "page_artifacts": page_artifacts,
                    }
                elif parsed.path == "/workflow/playbook":
                    data = {
                        "workflow_summary": scale_output,
                        "playbook": result["playbook"],
                    }
                elif parsed.path == "/scale/page-artifacts":
                    data = {
                        "scale_output": scale_output,
                        "page_artifacts": page_artifacts,
                    }
                elif parsed.path == "/scale/playbook":
                    data = {
                        "scale_output": scale_output,
                        "playbook": result["playbook"],
                    }
                elif parsed.path == "/scale":
                    data = {
                        "scale_output": scale_output,
                        "playbook": result["playbook"],
                    }
                else:
                    data = {
                        "workflow": workflow,
                        "scale_output": scale_output,
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
