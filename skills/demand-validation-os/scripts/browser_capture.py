#!/usr/bin/env python3
"""Shared browser/session helpers for demand-validation-os captures."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_DASHBOARD_URL = "https://dash.3ue.com/zh-Hans/#/login"


class BrowseError(RuntimeError):
    pass


@dataclass
class BrowseClient:
    session: str = "dvos"

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["BROWSE_SESSION"] = self.session
        return env

    def run(self, *args: str, expect_json: bool = True, timeout: int = 30) -> Any:
        cmd = ["browse", *args]
        try:
            proc = subprocess.run(
                cmd,
                env=self._env(),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise BrowseError(
                f"browse command timed out after {timeout}s: {' '.join(shlex.quote(p) for p in cmd)}"
            ) from exc
        if proc.returncode != 0:
            raise BrowseError(
                f"browse command failed: {' '.join(shlex.quote(p) for p in cmd)}\n"
                f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
            )
        stdout = proc.stdout.strip()
        if not expect_json:
            return stdout
        if not stdout:
            return None
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise BrowseError(f"Invalid JSON from browse {' '.join(args)}:\n{stdout}") from exc

    def stop(self, ignore_errors: bool = True, timeout: int = 15) -> str:
        cmd = ["browse", "stop"]
        proc = subprocess.run(
            cmd,
            env=self._env(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0 and not ignore_errors:
            raise BrowseError(
                f"browse command failed: {' '.join(shlex.quote(p) for p in cmd)}\n"
                f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
            )
        return proc.stdout.strip()

    def _is_retryable_open_error(self, error: BrowseError) -> bool:
        text = str(error)
        return (
            "Navigation was superseded by a new request" in text
            or "No Page found for awaitActivePage: no page available" in text
            or "browse command timed out" in text
        )

    def open(self, url: str, timeout: int = 60) -> Any:
        last_error: BrowseError | None = None
        for attempt in range(3):
            try:
                return self.run("open", url, timeout=timeout)
            except BrowseError as exc:
                last_error = exc
                if not self._is_retryable_open_error(exc) or attempt == 2:
                    raise
                time.sleep(2 + attempt)
        if last_error is not None:
            raise last_error
        raise BrowseError(f"browse open failed unexpectedly for {url}")

    def wait_timeout(self, seconds: float) -> Any:
        ms = int(seconds * 1000)
        return self.run("wait", "timeout", str(ms), timeout=max(10, int(seconds) + 10))

    def eval(self, expression: str, timeout: int = 30) -> Any:
        data = self.run("eval", expression, timeout=timeout)
        if isinstance(data, dict) and "result" in data:
            return data["result"]
        return data

    def get(self, what: str, selector: str | None = None, timeout: int = 30) -> Any:
        args = ["get", what]
        if selector is not None:
            args.append(selector)
        return self.run(*args, timeout=timeout)

    def current_url(self, timeout: int = 15) -> str:
        data = self.get("url", timeout=timeout)
        if isinstance(data, dict):
            return str(data.get("url", ""))
        return str(data or "")

    def current_title(self, timeout: int = 15) -> str:
        data = self.get("title", timeout=timeout)
        if isinstance(data, dict):
            return str(data.get("title", ""))
        return str(data or "")

    def press(self, key: str, timeout: int = 15) -> Any:
        return self.run("press", key, timeout=timeout)

    def pages(self) -> list[dict[str, Any]]:
        data = self.run("pages", timeout=15)
        return data.get("pages", []) if isinstance(data, dict) else []

    def tab_switch(self, index: int) -> Any:
        return self.run("tab_switch", str(index), timeout=15)

    def click(self, ref: str, timeout: int = 20) -> Any:
        return self.run("click", ref, timeout=timeout)

    def snapshot(self, timeout: int = 20) -> Any:
        return self.run("snapshot", timeout=timeout)

    def fetch_json(self, url: str, timeout: int = 30) -> Any:
        result = self.eval(
            f"""
            (() => {{
              try {{
                const xhr = new XMLHttpRequest();
                xhr.open("GET", {json.dumps(url)}, false);
                xhr.withCredentials = true;
                xhr.send(null);
                const text = xhr.responseText || "";
                let body = null;
                try {{
                  body = text ? JSON.parse(text) : null;
                }} catch {{
                  body = text;
                }}
                return {{
                  ok: xhr.status >= 200 && xhr.status < 300,
                  status: xhr.status,
                  body
                }};
              }} catch (error) {{
                return {{
                  ok: false,
                  error: String(error)
                }};
              }}
            }})()
            """,
            timeout=timeout,
        )
        if isinstance(result, dict) and result.get("ok"):
            return result.get("body")
        return None

    def _extract_network_path(self, data: Any) -> str:
        if isinstance(data, dict) and data.get("path"):
            return str(data["path"])
        current = self.network_path()
        if not current:
            raise BrowseError(f"browse network command did not return a path: {data!r}")
        return current

    def network_on(self) -> str:
        data = self.run("network", "on", timeout=15)
        return self._extract_network_path(data)

    def network_clear(self) -> str:
        data = self.run("network", "clear", timeout=15)
        return self._extract_network_path(data)

    def network_path(self) -> str:
        data = self.run("network", "path", timeout=15)
        if isinstance(data, dict) and data.get("path"):
            return str(data["path"])
        return ""

    def wait_for_url_contains_any(
        self,
        fragments: list[str] | tuple[str, ...],
        timeout: int = 30,
        poll_seconds: float = 1.0,
    ) -> str:
        deadline = time.time() + timeout
        last_url = ""
        while time.time() < deadline:
            last_url = self.current_url(timeout=15)
            if any(fragment in last_url for fragment in fragments):
                return last_url
            time.sleep(poll_seconds)
        raise BrowseError(
            f"Timed out after {timeout}s waiting for url to contain one of {list(fragments)!r}. "
            f"Last url: {last_url}"
        )


class ThreeUEExecutor:
    def __init__(self, username: str, password: str, session: str = "dvos") -> None:
        self.username = username
        self.password = password
        self.browser = BrowseClient(session=session)

    def reset_session(self) -> None:
        self.browser.stop(ignore_errors=True)
        time.sleep(1)

    def stop(self) -> None:
        self.browser.stop(ignore_errors=True)

    def login(self) -> dict[str, Any]:
        self.browser.open(DEFAULT_DASHBOARD_URL, timeout=90)
        self.browser.wait_timeout(3)
        result = self.browser.eval(
            f"""
            (() => {{
              const u = document.querySelector("#input-username");
              const p = document.querySelector("#input-password");
              const btn = document.querySelector('button[status="primary"], button');
              if (!u || !p || !btn) return {{ ok: true, reusedSession: true, reason: "login-form-missing" }};
              const set = (el, value) => {{
                const desc = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value")
                  || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
                desc.set.call(el, value);
                el.dispatchEvent(new Event("input", {{ bubbles: true }}));
                el.dispatchEvent(new Event("change", {{ bubbles: true }}));
              }};
              set(u, {json.dumps(self.username, ensure_ascii=False)});
              set(p, {json.dumps(self.password, ensure_ascii=False)});
              btn.click();
              return {{ ok: true }};
            }})()
            """,
            timeout=30,
        )
        self.browser.wait_timeout(4)
        self.ensure_home()
        url = self.browser.get("url")
        title = self.browser.get("title")
        current_url = url.get("url") if isinstance(url, dict) else url
        return {
            "login_result": {
                **(result if isinstance(result, dict) else {"raw": result}),
                "home_ready": isinstance(current_url, str) and "/page/m/home" in current_url,
            },
            "url": current_url,
            "title": title.get("title") if isinstance(title, dict) else title,
        }

    def ensure_home(self) -> None:
        self.browser.open("https://dash.3ue.com/zh-Hans/#/page/m/home", timeout=90)
        self.browser.wait_timeout(2)

    def _sync_get_json(self, url: str) -> Any:
        self.ensure_home()
        return self.browser.fetch_json(url, timeout=30)

    def get_subscription_context(self) -> dict[str, Any]:
        subscription = self._sync_get_json("/api/subscription/self")
        role_limit = self._sync_get_json("/api/config/kv?key=RoleLimit")
        auditing = self._sync_get_json("/api/auditing/self")

        if subscription is None or role_limit is None or auditing is None:
            path_value = self.browser.network_path()
            if path_value:
                path = Path(path_value)
                for req_file in path.glob("*/request.json"):
                    req = json.loads(req_file.read_text())
                    url = req.get("url", "")
                    resp_file = req_file.with_name("response.json")
                    if not resp_file.exists():
                        continue
                    resp = json.loads(resp_file.read_text())
                    body = resp.get("body")
                    if isinstance(body, str):
                        try:
                            parsed = json.loads(body)
                        except json.JSONDecodeError:
                            continue
                    else:
                        parsed = body
                    if subscription is None and url.endswith("/api/subscription/self"):
                        subscription = parsed
                    elif role_limit is None and "key=RoleLimit" in url:
                        role_limit = parsed
                    elif auditing is None and url.endswith("/api/auditing/self"):
                        auditing = parsed
        return {
            "subscription": subscription,
            "role_limit": role_limit,
            "auditing": auditing,
        }

    def open_tool(self, tool: str) -> dict[str, Any]:
        self.ensure_home()
        index = {"similarweb": 0, "semrush": 1}[tool]
        pages_before = self.browser.pages()
        snapshot = self.browser.snapshot(timeout=30)
        tree = snapshot.get("tree", "") if isinstance(snapshot, dict) else ""
        refs = re.findall(r"\[(\d+-\d+)\]\s+button: 打开", tree)
        if len(refs) <= index:
            result = {"ok": False, "count": len(refs), "reason": "open-button-ref-missing"}
        else:
            result = self.browser.click(f"@{refs[index]}", timeout=30)
        try:
            self.browser.wait_timeout(5)
        except BrowseError:
            pass
        pages = self.browser.pages()
        target_index = len(pages) - 1 if pages else 0
        if pages and len(pages) >= len(pages_before):
            self.browser.tab_switch(target_index)
            try:
                self.browser.wait_timeout(1)
            except BrowseError:
                pass
            pages = self.browser.pages()
        active = pages[target_index] if pages else {}
        return {
            "result": result,
            "pages_before": pages_before,
            "pages": pages,
            "active_index": target_index,
            "active": active,
        }


def load_network_entries(network_dir: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    base = Path(network_dir)
    for req_file in sorted(base.glob("*/request.json")):
        resp_file = req_file.with_name("response.json")
        if not resp_file.exists():
            continue
        req = json.loads(req_file.read_text())
        resp = json.loads(resp_file.read_text())
        request_body = req.get("postData")
        if request_body is None:
            request_body = req.get("body")
        parsed_request_body: Any = request_body
        if isinstance(request_body, str):
            try:
                parsed_request_body = json.loads(request_body)
            except json.JSONDecodeError:
                parsed_request_body = request_body
        body = resp.get("body")
        parsed_body: Any = body
        if isinstance(body, str):
            try:
                parsed_body = json.loads(body)
            except json.JSONDecodeError:
                parsed_body = body
        entries.append(
            {
                "dir": req_file.parent.name,
                "request": req,
                "response": resp,
                "request_body": request_body,
                "parsed_request_body": parsed_request_body,
                "parsed_body": parsed_body,
            }
        )
    return entries


def iso_utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
