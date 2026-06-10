#!/usr/bin/env python3
"""Deterministic tests for 3ue usage-limit detection and node rotation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "skills" / "demand-validation-os" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import browser_capture
import capture_semrush
import capture_similarweb


class UsageLimitDetectionTests(unittest.TestCase):
    def test_detect_usage_limit_text_matches_real_wall_copy(self) -> None:
        text = """
        Daily usage limit reached
        Daily usage limit reached
        To continue, either purchase a package or wait until your limit resets tomo
        """
        detected = browser_capture.detect_usage_limit_text(text)
        self.assertIsNotNone(detected)
        assert detected is not None
        self.assertIn("daily usage limit reached", detected["matched_patterns"])
        self.assertIn(
            "to continue, either purchase a package or wait until your limit resets",
            detected["matched_patterns"],
        )


class RotateToolNodeTests(unittest.TestCase):
    def test_rotate_tool_node_picks_next_untried_node(self) -> None:
        executor = browser_capture.ThreeUEExecutor("u", "p", session="test")
        executor.browser = SimpleNamespace(wait_timeout=lambda _seconds: None)
        executor.get_tool_nodes = mock.Mock(
            return_value=[
                {"index": 0, "note": "n0", "rate": 1.0, "raw": {}},
                {"index": 1, "note": "n1", "rate": 1.0, "raw": {}},
                {"index": 2, "note": "n2", "rate": 1.0, "raw": {}},
            ]
        )
        executor.get_current_tool_node_index = mock.Mock(return_value=0)
        executor.set_tool_node_index = mock.Mock(return_value={"tool": "semrush", "node_index": 1})
        executor.ensure_home = mock.Mock(return_value={"home_ready": True})

        result = executor.rotate_tool_node("semrush", tried_indices={2})

        self.assertEqual(result["selected"]["index"], 1)
        executor.set_tool_node_index.assert_called_once_with("semrush", 1, clear_cache=True)
        executor.ensure_home.assert_called_once()


class OpenSemrushOverviewRotationTests(unittest.TestCase):
    def test_open_semrush_overview_rotates_after_usage_limit_and_retries(self) -> None:
        class FakeBrowser:
            def __init__(self) -> None:
                self.open_calls: list[str] = []
                self.network_clear_calls = 0

            def open(self, url: str) -> None:
                self.open_calls.append(url)

            def wait_timeout(self, _seconds: float) -> None:
                return None

            def try_current_url(self) -> str:
                return "https://sem.3ue.com/analytics/overview/?q=crazygames.com&searchType=domain"

            def try_current_title(self) -> str:
                return "crazygames.com：域名概览"

            def network_clear(self) -> str:
                self.network_clear_calls += 1
                return f"network-{self.network_clear_calls}"

        class FakeExecutor:
            def __init__(self) -> None:
                self.browser = FakeBrowser()
                self.current_node = 0
                self.rotate_calls: list[tuple[str, set[int] | None]] = []
                self.ensure_home_calls = 0

            def ensure_home(self) -> dict[str, bool]:
                self.ensure_home_calls += 1
                return {"home_ready": True}

            def get_current_tool_node_index(self, _tool: str) -> int:
                return self.current_node

            def rotate_tool_node(self, tool: str, tried_indices: set[int] | None = None) -> dict[str, object]:
                self.rotate_calls.append((tool, tried_indices))
                previous = self.current_node
                self.current_node = 1
                return {
                    "tool": tool,
                    "previous_index": previous,
                    "selected": {"index": 1, "note": "node-1"},
                    "available_nodes": [{"index": 0}, {"index": 1}],
                    "switch": {"tool": tool, "node_index": 1},
                }

        rpc_entries = [
            {
                "dir": "req-1",
                "request": {"url": "https://sem.3ue.com/dpa/rpc"},
                "response": {},
                "request_body": None,
                "parsed_request_body": None,
                "parsed_body": [{"id": 9, "result": {"authorityScore": 90}}],
            }
        ]
        usage_limit = {
            "url": "https://sem.3ue.com/limit",
            "title": "Daily usage limit reached",
            "body": "Daily usage limit reached",
            "matched_patterns": ["daily usage limit reached"],
            "excerpt": "Daily usage limit reached",
        }

        executor = FakeExecutor()
        with (
            mock.patch.object(capture_semrush, "extract_usage_limit_state", side_effect=[usage_limit, None]),
            mock.patch.object(
                capture_semrush,
                "load_network_entries",
                side_effect=lambda network_dir: rpc_entries if network_dir == "network-2" else [],
            ),
        ):
            result = capture_semrush.open_semrush_overview(
                executor,
                "crazygames.com",
                network_dir="network-0",
                max_node_rotations=2,
            )

        (
            page_url,
            page_title,
            _network_dir,
            _entries,
            rpc_results,
            attempts_used,
            node_switches,
            usage_limit_events,
        ) = result
        self.assertIn("crazygames.com", page_url)
        self.assertEqual(page_title, "crazygames.com：域名概览")
        self.assertEqual(attempts_used, 2)
        self.assertEqual(len(rpc_results), 1)
        self.assertEqual(len(node_switches), 1)
        self.assertEqual(node_switches[0]["selected"]["index"], 1)
        self.assertEqual(len(usage_limit_events), 1)
        self.assertEqual(usage_limit_events[0]["node_index"], 0)
        self.assertEqual(executor.rotate_calls, [("semrush", set())])


class SimilarwebCollectRotationTests(unittest.TestCase):
    def test_collect_rotates_on_usage_limit_then_returns_report(self) -> None:
        class FakeBrowser:
            def __init__(self) -> None:
                self.network_clear_calls = 0
                self.current_url_value = ""
                self.current_title_value = ""

            def network_on(self) -> str:
                return "network-on"

            def network_clear(self) -> str:
                self.network_clear_calls += 1
                return f"network-{self.network_clear_calls}"

            def wait_timeout(self, _seconds: float) -> None:
                return None

            def press(self, _key: str) -> None:
                return None

            def fetch_json(self, url: str, timeout: int = 30) -> object:
                del timeout
                if url == "/api/identities":
                    return [{"UserId": 1, "AccountId": 2, "AccountName": "acct"}]
                if url.startswith("/api/startupSettings"):
                    return {"settings": {"components": {}}}
                if url.startswith("/autocomplete/websites"):
                    return [{"name": "crazygames.com", "blockStatus": [1]}]
                if url.startswith("/autocomplete/keywords"):
                    return []
                if url.startswith("/api/WebsiteOverview/getsimilarsites"):
                    return []
                return None

            def try_current_url(self, timeout: int = 15) -> str:
                del timeout
                return self.current_url_value

            def try_current_title(self, timeout: int = 15) -> str:
                del timeout
                return self.current_title_value

            def current_url(self, timeout: int = 15) -> str:
                del timeout
                return self.current_url_value

            def current_title(self, timeout: int = 15) -> str:
                del timeout
                return self.current_title_value

        class FakeExecutor:
            last_instance: "FakeExecutor | None" = None

            def __init__(self, username: str, password: str, session: str) -> None:
                del username, password, session
                FakeExecutor.last_instance = self
                self.browser = FakeBrowser()
                self.current_node = 0
                self.open_tool_calls = 0
                self.rotations: list[dict[str, object]] = []

            def reset_session(self) -> None:
                return None

            def login(self) -> dict[str, object]:
                return {
                    "login_result": {"ok": True, "home_ready": True},
                    "url": "https://dash.3ue.com/zh-Hans/#/page/m/home",
                    "title": "用户中心 - 首页",
                }

            def ensure_home(self, timeout: int = 90) -> dict[str, object]:
                del timeout
                return {"home_ready": True}

            def open_tool(self, tool: str) -> dict[str, object]:
                self.open_tool_calls += 1
                self.browser.current_url_value = "https://sim.3ue.com/"
                self.browser.current_title_value = "Similarweb PRO"
                return {
                    "result": {"clicked": True},
                    "pages_before": [{"index": 0, "url": "https://dash.3ue.com/zh-Hans/#/page/m/home"}],
                    "pages": [
                        {"index": 0, "url": "https://dash.3ue.com/zh-Hans/#/page/m/home"},
                        {"index": 1, "url": "https://sim.3ue.com/"},
                    ],
                    "active_index": 1,
                    "active": {"index": 1, "url": "https://sim.3ue.com/"},
                }

            def get_current_tool_node_index(self, _tool: str) -> int:
                return self.current_node

            def rotate_tool_node(self, tool: str, tried_indices: set[int] | None = None) -> dict[str, object]:
                previous = self.current_node
                self.current_node = 1
                switch = {
                    "tool": tool,
                    "previous_index": previous,
                    "selected": {"index": 1, "note": "node-1"},
                    "available_nodes": [{"index": 0}, {"index": 1}],
                    "switch": {"tool": tool, "node_index": 1},
                }
                self.rotations.append(switch)
                return switch

            def get_subscription_context(self) -> dict[str, object]:
                return {"subscription": {"c": 0, "data": []}, "auditing": {"c": 0, "data": []}}

            def stop(self) -> None:
                return None

        report_route = (
            "https://sim.3ue.com/#/digitalsuite/websiteanalysis/overview/"
            "website-performance/*/999/3m?webSource=Total&key=crazygames.com"
        )

        def fake_capture_usage_limit_event(_browser: object, stage: str, node_index: int | None) -> dict[str, object] | None:
            if stage == "tool_open" and node_index == 0:
                return {
                    "url": "https://sim.3ue.com/limit",
                    "title": "Daily usage limit reached",
                    "body": "Daily usage limit reached",
                    "matched_patterns": ["daily usage limit reached"],
                    "excerpt": "Daily usage limit reached",
                    "tool": "similarweb",
                    "stage": stage,
                    "node_index": node_index,
                }
            return None

        def fake_wait_for_shell(browser: FakeBrowser, timeout: int = 60) -> dict[str, str]:
            del timeout
            browser.current_url_value = "https://sim.3ue.com/#/digitalsuite/home"
            browser.current_title_value = "数字套装"
            return {"href": browser.current_url_value, "title": browser.current_title_value}

        def fake_navigate(browser: FakeBrowser, query: str) -> tuple[bool, str]:
            self.assertEqual(query, "crazygames.com")
            browser.current_url_value = report_route
            browser.current_title_value = "网站表现"
            return True, "direct_route_open_after_entry"

        def fake_report_snapshot(_browser: FakeBrowser) -> dict[str, object]:
            return {
                "url": report_route,
                "title": "网站表现",
                "query_domain": "crazygames.com",
                "total_visits_text": "",
                "device_distribution_text": "",
                "rank_rows": [],
                "channels_text": "",
                "social_text": "",
                "top_referring_websites_text": "",
                "top_referring_industries_text": "",
                "top_outgoing_links_text": "",
                "top_ad_destinations_text": "",
                "top_publishers_text": "",
                "page_frame_text": "",
                "report_links": [],
            }

        with (
            mock.patch.object(capture_similarweb, "ThreeUEExecutor", FakeExecutor),
            mock.patch.object(capture_similarweb, "capture_usage_limit_event", side_effect=fake_capture_usage_limit_event),
            mock.patch.object(capture_similarweb, "wait_for_similarweb_shell_ready", side_effect=fake_wait_for_shell),
            mock.patch.object(
                capture_similarweb,
                "extract_home_signals",
                return_value={"route": "https://sim.3ue.com/#/activation/home", "title": "Activation", "priority_alerts": []},
            ),
            mock.patch.object(capture_similarweb, "fill_quick_search", return_value=None),
            mock.patch.object(
                capture_similarweb,
                "extract_quick_search_state",
                return_value=(
                    {"ok": True, "placeholder": "搜索任何网站、关键词或报告", "className": "input"},
                    {"modal_open": True, "websites": ["crazygames.com"], "keywords": []},
                    [],
                ),
            ),
            mock.patch.object(capture_similarweb, "navigate_to_website_performance", side_effect=fake_navigate),
            mock.patch.object(capture_similarweb, "wait_for_website_performance_ready", return_value={"ok": True}),
            mock.patch.object(capture_similarweb, "extract_report_snapshot", side_effect=fake_report_snapshot),
            mock.patch.object(capture_similarweb, "load_network_entries", return_value=[]),
        ):
            data = capture_similarweb.collect(
                "crazygames.com",
                "落花",
                "2026.06.10",
                "test-sim",
                keep_session=False,
                max_node_rotations=2,
            )

        executor = FakeExecutor.last_instance
        self.assertIsNotNone(executor)
        assert executor is not None
        self.assertEqual(executor.open_tool_calls, 2)
        self.assertEqual(len(executor.rotations), 1)
        self.assertEqual(data["raw_artifacts"]["node_switches"][0]["selected"]["index"], 1)
        self.assertEqual(len(data["raw_artifacts"]["usage_limit_events"]), 1)
        self.assertEqual(data["raw_artifacts"]["usage_limit_events"][0]["stage"], "tool_open")
        self.assertTrue(data["website_evidence"]["website_performance"]["available"])
        self.assertEqual(
            data["website_evidence"]["report_navigation_used"],
            "direct_route_open_after_entry",
        )


if __name__ == "__main__":
    unittest.main()
