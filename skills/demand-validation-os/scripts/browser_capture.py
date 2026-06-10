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
DEFAULT_DASHBOARD_HOME_URL = "https://dash.3ue.com/zh-Hans/#/page/m/home"
TOOL_HOSTS = {
    "similarweb": "https://sim.3ue.com",
    "semrush": "https://sem.3ue.com",
}
USAGE_LIMIT_PATTERNS = [
    "daily usage limit reached",
    "to continue, either purchase a package or wait until your limit resets",
    "wait until your limit resets",
    "purchase a package",
]


class BrowseError(RuntimeError):
    pass


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def detect_usage_limit_text(text: str | None) -> dict[str, Any] | None:
    normalized = normalize_whitespace(text or "")
    lowered = normalized.lower()
    matched = [pattern for pattern in USAGE_LIMIT_PATTERNS if pattern in lowered]
    if not matched:
        return None
    return {
        "matched_patterns": matched,
        "excerpt": normalized[:1000],
    }


def extract_usage_limit_state(browser: "BrowseClient", timeout: int = 20) -> dict[str, Any] | None:
    body_text = browser.try_get_text("body", timeout=timeout)
    detected = detect_usage_limit_text(body_text)
    if not detected:
        return None
    return {
        "url": browser.try_current_url(timeout=10),
        "title": browser.try_current_title(timeout=10),
        "body": body_text[:2000],
        **detected,
    }


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
            or "waitForMainLoadState(load) timed out" in text
            or "waitForMainLoadState(domcontentloaded) timed out" in text
        )

    def open(self, url: str, timeout: int = 60) -> Any:
        last_error: BrowseError | None = None
        for attempt in range(3):
            try:
                return self.run("open", url, timeout=timeout)
            except BrowseError as exc:
                last_error = exc
                if self._is_retryable_open_error(exc):
                    current = ""
                    try:
                        current = self.current_url(timeout=10)
                    except BrowseError:
                        current = ""
                    if current and (current == url or current.startswith(url) or url in current):
                        return {
                            "url": current,
                            "recovered": True,
                            "warning": str(exc),
                        }
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

    def try_current_url(self, timeout: int = 15) -> str:
        try:
            return self.current_url(timeout=timeout)
        except BrowseError:
            return ""

    def current_title(self, timeout: int = 15) -> str:
        data = self.get("title", timeout=timeout)
        if isinstance(data, dict):
            return str(data.get("title", ""))
        return str(data or "")

    def try_current_title(self, timeout: int = 15) -> str:
        try:
            return self.current_title(timeout=timeout)
        except BrowseError:
            return ""

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

    def try_snapshot(self, timeout: int = 20) -> Any:
        try:
            return self.snapshot(timeout=timeout)
        except BrowseError:
            return None

    def get_text(self, selector: str = "body", timeout: int = 30) -> str:
        data = self.get("text", selector, timeout=timeout)
        if isinstance(data, dict):
            return str(data.get("text", ""))
        return str(data or "")

    def try_get_text(self, selector: str = "body", timeout: int = 30) -> str:
        try:
            return self.get_text(selector=selector, timeout=timeout)
        except BrowseError:
            return ""

    def try_eval(self, expression: str, timeout: int = 30) -> Any:
        try:
            return self.eval(expression, timeout=timeout)
        except BrowseError:
            return None

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

    def _dashboard_state(self) -> dict[str, Any]:
        url = self.browser.current_url(timeout=10)
        title = self.browser.current_title(timeout=10)
        body_text = self.browser.try_get_text("body", timeout=15)
        eval_state = self.browser.try_eval(
            """
            (() => {
              const text = (el) => (el?.innerText || el?.textContent || "").trim();
              const username = document.querySelector("#input-username")
                || [...document.querySelectorAll("input")]
                  .find((el) => /user|账户|账号|用户名/i.test([el.id, el.name, el.placeholder].filter(Boolean).join(" ")));
              const password = document.querySelector("#input-password")
                || [...document.querySelectorAll("input[type='password'], input")]
                  .find((el) => el.type === "password" || /pass|密码/i.test([el.id, el.name, el.placeholder].filter(Boolean).join(" ")));
              const loginButton = [...document.querySelectorAll("button")]
                .find((el) => /登录/.test(text(el)) || el.getAttribute("status") === "primary");
              return {
                has_username: !!username,
                has_password: !!password,
                has_login_button: !!loginButton,
              };
            })()
            """,
            timeout=8,
        )
        has_form = bool(
            isinstance(eval_state, dict)
            and eval_state.get("has_username")
            and eval_state.get("has_password")
        )
        home_ready = "/page/m/home" in url or "用户中心" in body_text or "套餐中心" in body_text
        login_ready = has_form or ("用户名" in body_text and "密码" in body_text)
        return {
            "url": url,
            "title": title,
            "body_excerpt": body_text[:300],
            "home_ready": home_ready,
            "login_ready": login_ready,
            "login_form_ready": has_form,
            "eval_state": eval_state if isinstance(eval_state, dict) else {},
        }

    def _wait_for_dashboard_surface(self, timeout: int = 60) -> dict[str, Any]:
        deadline = time.time() + timeout
        last_state: dict[str, Any] = {}
        while time.time() < deadline:
            state = self._dashboard_state()
            last_state = state
            if state["home_ready"] or state["login_ready"]:
                return state
            time.sleep(1)
        raise BrowseError(f"Timed out waiting for dashboard login or home surface: {last_state}")

    def _submit_login_form(self) -> dict[str, Any]:
        result = self.browser.eval(
            f"""
            (() => {{
              const text = (el) => (el?.innerText || el?.textContent || "").trim();
              const u = document.querySelector("#input-username")
                || [...document.querySelectorAll("input")]
                  .find((el) => /user|账户|账号|用户名/i.test([el.id, el.name, el.placeholder].filter(Boolean).join(" ")));
              const p = document.querySelector("#input-password")
                || [...document.querySelectorAll("input[type='password'], input")]
                  .find((el) => el.type === "password" || /pass|密码/i.test([el.id, el.name, el.placeholder].filter(Boolean).join(" ")));
              const btn = [...document.querySelectorAll('button')]
                .find((el) => /登录/.test(text(el)) || el.getAttribute("status") === "primary");
              if (!u || !p || !btn) return {{ ok: false, reason: "login-form-missing" }};
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
        if not isinstance(result, dict) or not result.get("ok"):
            raise BrowseError(f"Failed to submit 3ue login form: {result}")
        return result

    def login(self) -> dict[str, Any]:
        self.browser.open(DEFAULT_DASHBOARD_URL, timeout=90)
        state = self._wait_for_dashboard_surface(timeout=60)
        result: dict[str, Any]
        if state["home_ready"]:
            result = {"ok": True, "reusedSession": True, "reason": "home-surface-ready"}
        else:
            result = self._submit_login_form()
            self.browser.wait_timeout(4)
        final_state = self.ensure_home(timeout=90)
        return {
            "login_result": {
                **(result if isinstance(result, dict) else {"raw": result}),
                "home_ready": final_state["home_ready"],
            },
            "url": final_state["url"],
            "title": final_state["title"],
        }

    def ensure_home(self, timeout: int = 90) -> dict[str, Any]:
        deadline = time.time() + timeout
        last_state: dict[str, Any] = {}
        login_attempted = False
        self.browser.open(DEFAULT_DASHBOARD_HOME_URL, timeout=90)
        while time.time() < deadline:
            state = self._wait_for_dashboard_surface(timeout=20)
            last_state = state
            if state["home_ready"]:
                return state
            if state["login_form_ready"] and not login_attempted:
                self._submit_login_form()
                login_attempted = True
                self.browser.wait_timeout(4)
                self.browser.open(DEFAULT_DASHBOARD_HOME_URL, timeout=90)
                continue
            self.browser.open(DEFAULT_DASHBOARD_HOME_URL, timeout=90)
            time.sleep(2)
        raise BrowseError(f"Timed out ensuring dashboard home: {last_state}")

    def _sync_get_json(self, url: str) -> Any:
        self.ensure_home()
        return self.browser.fetch_json(url, timeout=30)

    def read_gmitm_config(self) -> dict[str, Any]:
        result = self.browser.try_eval(
            """
            (() => {
              const match = document.cookie.match(/(?:^|; )GMITM_config=([^;]+)/);
              if (!match) return null;
              try {
                return JSON.parse(decodeURIComponent(match[1]));
              } catch (error) {
                return { _parse_error: String(error), raw: match[1] };
              }
            })()
            """,
            timeout=10,
        )
        return result if isinstance(result, dict) else {}

    def write_gmitm_config(self, config: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
        result = self.browser.eval(
            f"""
            (() => {{
              const value = encodeURIComponent({json.dumps(payload, ensure_ascii=False)});
              document.cookie = `GMITM_config=${{value}}; path=/; domain=.3ue.com`;
              return document.cookie;
            }})()
            """,
            timeout=15,
        )
        return {"cookie": result, "config": config}

    def get_tool_nodes(self, tool: str) -> list[dict[str, Any]]:
        host = TOOL_HOSTS[tool]
        data = self.browser.eval(
            f"""
            (() => {{
              try {{
                const xhr = new XMLHttpRequest();
                xhr.open("GET", {json.dumps(host + "/mitmApi/nodes")}, false);
                xhr.withCredentials = true;
                xhr.send(null);
                let body = null;
                try {{
                  body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
                }} catch {{
                  body = xhr.responseText || null;
                }}
                return {{ status: xhr.status, body }};
              }} catch (error) {{
                return {{ status: 0, error: String(error) }};
              }}
            }})()
            """,
            timeout=30,
        )
        body = data.get("body") if isinstance(data, dict) else None
        if isinstance(body, dict) and isinstance(body.get("data"), list):
            rows = []
            for idx, item in enumerate(body["data"]):
                rows.append(
                    {
                        "index": idx,
                        "note": item.get("note"),
                        "rate": item.get("rate"),
                        "raw": item,
                    }
                )
            return rows
        return []

    def get_current_tool_node_index(self, tool: str) -> int | None:
        config = self.read_gmitm_config()
        tool_config = config.get(tool)
        if not isinstance(tool_config, dict):
            return None
        node_value = tool_config.get("node")
        if node_value is None:
            return None
        try:
            return int(node_value)
        except (TypeError, ValueError):
            return None

    def set_tool_node_index(self, tool: str, node_index: int, clear_cache: bool = True) -> dict[str, Any]:
        config = self.read_gmitm_config()
        tool_config = config.get(tool)
        if not isinstance(tool_config, dict):
            tool_config = {}
        tool_config["node"] = str(node_index)
        config[tool] = tool_config
        write_result = self.write_gmitm_config(config)
        cache_result = None
        if clear_cache:
            cache_result = self.clear_tool_cache(tool)
        return {
            "tool": tool,
            "node_index": node_index,
            "write": write_result,
            "cache": cache_result,
        }

    def clear_tool_cache(self, tool: str) -> Any:
        host = TOOL_HOSTS[tool]
        return self.browser.open(f"{host}/gmitm.clean.cache.html?ref=%2F", timeout=90)

    def rotate_tool_node(self, tool: str, tried_indices: set[int] | None = None) -> dict[str, Any]:
        nodes = self.get_tool_nodes(tool)
        if not nodes:
            raise BrowseError(f"No nodes available for tool {tool}")
        current = self.get_current_tool_node_index(tool)
        tried = set(tried_indices or set())
        candidate = next((item for item in nodes if item["index"] not in tried and item["index"] != current), None)
        if candidate is None:
            candidate = next((item for item in nodes if item["index"] not in tried), None)
        if candidate is None:
            raise BrowseError(f"No untried nodes left for tool {tool}; current={current}, tried={sorted(tried)}")
        switch = self.set_tool_node_index(tool, candidate["index"], clear_cache=True)
        self.ensure_home()
        self.browser.wait_timeout(2)
        return {
            "tool": tool,
            "previous_index": current,
            "selected": candidate,
            "switch": switch,
            "available_nodes": nodes,
        }

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
        result: dict[str, Any] | Any = {"ok": False, "reason": "open-button-ref-missing"}
        refs: list[str] = []
        for _ in range(3):
            snapshot = self.browser.try_snapshot(timeout=30)
            tree = snapshot.get("tree", "") if isinstance(snapshot, dict) else ""
            refs = re.findall(r"\[(\d+-\d+)\]\s+(?:button|link): 打开", tree)
            if len(refs) > index:
                result = self.browser.click(f"@{refs[index]}", timeout=30)
                break
            click_result = self.browser.try_eval(
                f"""
                (() => {{
                  const buttons = [...document.querySelectorAll("button, a")]
                    .filter((el) => /打开/.test((el.innerText || el.textContent || "").trim()));
                  const target = buttons[{index}] || null;
                  if (!target) return {{ ok: false, reason: "open-button-dom-missing", count: buttons.length }};
                  target.click();
                  return {{ ok: true, clickedVia: "dom-text-button", count: buttons.length }};
                }})()
                """,
                timeout=10,
            )
            if isinstance(click_result, dict) and click_result.get("ok"):
                result = click_result
                break
            self.browser.wait_timeout(2)
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
