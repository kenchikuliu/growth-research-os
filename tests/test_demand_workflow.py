from __future__ import annotations

import sys
import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "skills" / "demand-validation-os" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import google_trends
import guided_flow
import run_demand_workflow
import capture_bundle
import capture_api
import capture_service
import workflow_service
import page_artifacts
import render_report


class GoogleTrendsSummaryTests(unittest.TestCase):
    def test_summarize_timeline_detects_spike(self) -> None:
        rows = [{"value": value} for value in [5, 6, 8, 60, 12, 9, 8]]
        summary = google_trends.summarize_timeline(rows)
        self.assertEqual(summary["shape"], "spike")
        self.assertEqual(summary["latest_interest"], 8)

    def test_summarize_timeline_detects_rising(self) -> None:
        rows = [{"value": value} for value in [10, 12, 15, 18, 22, 26, 30]]
        summary = google_trends.summarize_timeline(rows)
        self.assertEqual(summary["shape"], "rising")
        self.assertGreater(summary["pct_change"], 0)

    def test_collect_records_provider_attempts_when_all_providers_unavailable(self) -> None:
        original_collect_official = google_trends.collect_official
        original_configured_rapidapi = google_trends.configured_rapidapi
        original_configured_dataforseo = google_trends.configured_dataforseo
        try:
            google_trends.collect_official = lambda *args, **kwargs: google_trends.build_payload(
                query="ai image generator",
                geo="US",
                hl="en-US",
                property_name="web",
                provider="google-trends",
                windows=[google_trends.build_empty_window("today 3-m", provider="google-trends", error="429")],
                notes=["official failed"],
            )
            google_trends.configured_rapidapi = lambda: False
            google_trends.configured_dataforseo = lambda: False
            payload = google_trends.collect("ai image generator")
        finally:
            google_trends.collect_official = original_collect_official
            google_trends.configured_rapidapi = original_configured_rapidapi
            google_trends.configured_dataforseo = original_configured_dataforseo

        self.assertFalse(payload["available"])
        self.assertEqual(payload["provider_attempts"][0]["provider"], "google-trends")
        self.assertEqual(payload["provider_attempts"][1]["provider"], "rapidapi-google-trends")
        self.assertFalse(payload["provider_attempts"][1]["configured"])
        self.assertEqual(payload["provider_attempts"][2]["provider"], "dataforseo-google-trends")
        self.assertFalse(payload["provider_attempts"][2]["configured"])

    def test_collect_uses_rapidapi_when_official_google_is_unavailable(self) -> None:
        original_collect_official = google_trends.collect_official
        original_configured_rapidapi = google_trends.configured_rapidapi
        original_collect_rapidapi = google_trends.collect_rapidapi
        original_configured_dataforseo = google_trends.configured_dataforseo
        try:
            google_trends.collect_official = lambda *args, **kwargs: google_trends.build_payload(
                query="ai image generator",
                geo="US",
                hl="en-US",
                property_name="web",
                provider="google-trends",
                windows=[google_trends.build_empty_window("today 3-m", provider="google-trends", error="429")],
                notes=["official failed"],
            )
            google_trends.configured_rapidapi = lambda: True
            google_trends.collect_rapidapi = lambda *args, **kwargs: google_trends.build_payload(
                query="ai image generator",
                geo="US",
                hl="en-US",
                property_name="web",
                provider="rapidapi-google-trends",
                windows=[
                    {
                        "timeframe": "today 3-m",
                        "label": "90d",
                        "interest_over_time": {
                            "rows": [{"value": 10}, {"value": 20}, {"value": 35}, {"value": 50}],
                            "summary": google_trends.summarize_timeline([{"value": 10}, {"value": 20}, {"value": 35}, {"value": 50}]),
                        },
                        "interest_by_region": [],
                        "related_queries": {"top": [], "rising": [{"query": "ai image generator free", "value": 80}]},
                        "fetch_modes": {"PRIMARY": {"mode": "requests", "provider": "rapidapi", "error": None}},
                        "available": True,
                        "notes": ["rapidapi success"],
                    }
                ],
                notes=["rapidapi success"],
            )
            google_trends.configured_dataforseo = lambda: False
            payload = google_trends.collect("ai image generator")
        finally:
            google_trends.collect_official = original_collect_official
            google_trends.configured_rapidapi = original_configured_rapidapi
            google_trends.collect_rapidapi = original_collect_rapidapi
            google_trends.configured_dataforseo = original_configured_dataforseo

        self.assertTrue(payload["available"])
        self.assertEqual(payload["source"]["provider"], "rapidapi-google-trends")
        self.assertTrue(payload["provider_attempts"][0]["configured"])
        self.assertFalse(payload["provider_attempts"][0]["available"])
        self.assertTrue(payload["provider_attempts"][1]["configured"])
        self.assertTrue(payload["provider_attempts"][1]["available"])

    def test_normalize_dataforseo_window_maps_graph_regions_and_queries(self) -> None:
        result = {
            "items": [
                {
                    "type": "google_trends_graph",
                    "data": [
                        {"date_from": "2026-01-01", "date_to": "2026-01-07", "timestamp": 1, "values": [10], "missing_data": False},
                        {"date_from": "2026-01-08", "date_to": "2026-01-14", "timestamp": 2, "values": [30], "missing_data": False},
                        {"date_from": "2026-01-15", "date_to": "2026-01-21", "timestamp": 3, "values": [40], "missing_data": False},
                        {"date_from": "2026-01-22", "date_to": "2026-01-28", "timestamp": 4, "values": [60], "missing_data": False},
                    ],
                },
                {
                    "type": "google_trends_map",
                    "data": [{"geo_name": "United States", "geo_id": "US", "values": [90]}],
                },
                {
                    "type": "google_trends_queries_list",
                    "data": {
                        "top": [{"query": "ai image generator free", "value": 100}],
                        "rising": [{"query": "ai image generator app", "value": 250}],
                    },
                },
            ]
        }
        window = google_trends.normalize_dataforseo_window(result, timeframe="today 3-m")
        self.assertTrue(window["available"])
        self.assertEqual(window["interest_over_time"]["summary"]["shape"], "rising")
        self.assertEqual(window["interest_by_region"][0]["name"], "United States")
        self.assertEqual(window["related_queries"]["rising"][0]["query"], "ai image generator app")


class DemandWorkflowHeuristicsTests(unittest.TestCase):
    def test_query_page_type_prefers_tool_for_generator_query(self) -> None:
        self.assertEqual(run_demand_workflow.query_page_type("ai image generator"), "tool")

    def test_query_page_type_detects_comparison_intent(self) -> None:
        self.assertEqual(run_demand_workflow.query_page_type("ahrefs alternative"), "comparison")

    def test_build_first_batch_pages_includes_comparison_page_blueprint(self) -> None:
        pages = run_demand_workflow.build_first_batch_pages(
            "ahrefs alternative",
            "comparison",
            ["ahrefs vs semrush"],
        )

        self.assertEqual(pages[0]["page_type"], "对比页")
        self.assertEqual(pages[0]["hero_primary_cta"], "马上注册")
        blueprint = pages[0]["page_blueprint"]
        self.assertEqual(blueprint["recommended_h2"], "ahrefs vs 你的品牌：Comparison")
        self.assertIn("价格", blueprint["comparison_table_dimensions"])
        self.assertIn("适用场景", blueprint["comparison_table_dimensions"])
        self.assertIn("为什么你是这个竞品的替代方案", blueprint["hero_questions_answered"])

    def test_render_report_template_keeps_comparison_page_fields(self) -> None:
        first_page = render_report.TEMPLATES["demand"]["first_batch_of_pages"][0]

        self.assertIn("hero_primary_cta", first_page)
        self.assertIn("page_blueprint", first_page)
        self.assertIn("comparison_table_dimensions", first_page["page_blueprint"])
        self.assertIn("recommended_h2", first_page["page_blueprint"])

    def test_page_artifacts_generate_publishable_comparison_page_json(self) -> None:
        workflow = {
            "input": {"query": "ahrefs alternative"},
            "decision": {"recommended_action": "ship_cluster"},
            "report": {
                "core_conclusion": "建议先做对比页。",
                "first_batch_of_pages": [
                    {
                        "working_title": "ahrefs alternative",
                        "page_type": "对比页",
                        "primary_intent": "替代方案比较",
                        "primary_keyword": "ahrefs alternative",
                        "hero_primary_cta": "马上注册",
                        "page_blueprint": {
                            "title_formula": "ahrefs Alternative：为什么很多用户选择你的品牌",
                            "recommended_h2": "ahrefs vs 你的品牌：Comparison",
                            "comparison_table_dimensions": ["价格", "功能", "适用场景"],
                            "fit_section_rule": "只写具体适合谁",
                            "seo_notes": ["comparison pages"],
                        },
                    }
                ],
            },
            "knowledge": {"gefei": {"summary": "不要只交关键词列表"}},
            "derived": {
                "page_signal_summary": "Semrush / Similarweb 页级证据已到位。",
                "keyword_signal_summary": "Similarweb 非品牌关键词 5 条，付费落地页 3 条。",
            },
            "evidence": {
                "trends": {"summary": {"primary_shape": "rising"}},
                "tool_capture": {
                    "results": {
                        "semrush": {"data": {"top_pages": [{}, {}], "top_organic_keywords": [{}, {}, {}]}},
                        "similarweb": {
                            "data": {
                                "website_evidence": {
                                    "website_content": {"summary": {"rows": [{}, {}]}},
                                    "search_overview": {
                                        "top_non_brand_keywords": {"rows": [{}, {}, {}, {}, {}]},
                                        "paid_landing_pages": {"rows": [{}, {}, {}]},
                                    },
                                    "home_signals": {
                                        "priority_alerts": [{"metric": "landing_pages"}, {"metric": "keywords"}]
                                    },
                                }
                            }
                        },
                    }
                },
            },
        }

        artifacts = page_artifacts.build_page_artifacts(
            workflow,
            brand_context=page_artifacts.brand_context_payload(
                brand_name="Demand Validation OS",
                brand_url="https://example.com",
                primary_cta_url="https://example.com/signup",
            ),
        )

        self.assertTrue(artifacts["available"])
        first = artifacts["pages"][0]["page_json"]
        self.assertEqual(first["hero"]["primary_cta"]["label"], "马上注册")
        self.assertEqual(first["hero"]["primary_cta"]["url"], "https://example.com/signup")
        self.assertEqual(first["comparison_section"]["heading"], "ahrefs vs 你的品牌：Comparison")
        self.assertEqual(first["direct_answers"][0]["question"], "为什么你是这个竞品的替代方案")
        self.assertTrue(first["comparison_section"]["rows"])
        self.assertIn("价格", [row["dimension"] for row in first["comparison_section"]["rows"]])

    def test_demand_raw_scores_reward_complete_evidence(self) -> None:
        trends = {
            "summary": {
                "primary_shape": "rising",
                "top_rising_queries": [{"query": "ai image generator free"}],
            }
        }
        bundle = {
            "summary": {"core_ready_tools": ["semrush", "similarweb"]},
            "results": {
                "semrush": {
                    "data": {
                        "top_pages": [
                            {"url": "https://site.com/tool/1", "title": "t1", "top_keyword": "k1"},
                            {"url": "https://site.com/tool/2", "title": "t2", "top_keyword": "k2"},
                            {"url": "https://site.com/tool/3", "title": "t3", "top_keyword": "k3"},
                        ],
                        "top_organic_keywords": [
                            {"keyword": "k1"},
                            {"keyword": "k2"},
                            {"keyword": "k3"},
                            {"keyword": "k4"},
                            {"keyword": "k5"},
                        ],
                    }
                },
                "similarweb": {
                    "data": {
                        "website_evidence": {
                            "website_performance": {"available": True},
                            "website_content": {
                                "summary": {
                                    "rows": [{"folder": "/game"}, {"folder": "/es"}, {"folder": "/new"}]
                                }
                            },
                            "search_overview": {
                                "top_non_brand_keywords": {
                                    "rows": [{"keyword": "k1"}, {"keyword": "k2"}]
                                },
                                "paid_landing_pages": {
                                    "rows": [{"url": "site.com/tool"}, {"url": "site.com/alt"}]
                                },
                            },
                        }
                    }
                },
            },
        }
        scores, _reasons, derived = run_demand_workflow.demand_raw_scores(
            query="ai image generator",
            page_type="tool",
            trends=trends,
            bundle=bundle,
        )
        self.assertGreaterEqual(scores["demand_reality"], 4)
        self.assertGreaterEqual(scores["search_carry"], 5)
        self.assertIn("Similarweb", derived["page_signal_summary"])
        self.assertIn("付费落地页 2 条", derived["keyword_signal_summary"])

    def test_attribution_raw_scores_read_similarweb_deep_rows(self) -> None:
        trends = {"available": True, "summary": {"primary_shape": "rising"}}
        bundle = {
            "summary": {"core_ready_tools": ["semrush", "similarweb"]},
            "results": {
                "semrush": {
                    "data": {
                        "top_pages": [
                            {"url": "https://site.com/tool/1", "title": "t1", "top_keyword": "k1"},
                            {"url": "https://site.com/tool/2", "title": "t2", "top_keyword": "k2"},
                            {"url": "https://site.com/tool/3", "title": "t3", "top_keyword": "k3"},
                        ],
                        "top_organic_keywords": [
                            {"keyword": "k1"},
                            {"keyword": "k2"},
                        ],
                    }
                },
                "similarweb": {
                    "data": {
                        "website_evidence": {
                            "website_performance": {"available": True},
                            "website_content": {
                                "summary": {
                                    "rows": [{"folder": "/game"}, {"folder": "/es"}, {"folder": "/new"}]
                                }
                            },
                            "search_overview": {
                                "top_non_brand_keywords": {"rows": [{"keyword": "free games"}]},
                                "paid_landing_pages": {"rows": [{"url": "site.com/game/1"}]},
                            },
                        }
                    }
                },
            },
        }

        scores, reasons, derived = run_demand_workflow.attribution_raw_scores(
            query="crazygames.com",
            trends=trends,
            bundle=bundle,
        )

        self.assertGreaterEqual(scores["keyword_change_confidence"], 4)
        self.assertGreaterEqual(scores["chain_closure"], 4)
        self.assertIn("付费落地页 1 条", derived["keyword_signal_summary"])
        self.assertTrue(any("Similarweb paid landing rows: 1" in reason for reason in reasons["chain_closure"]))


class CaptureBundleQualityTests(unittest.TestCase):
    def test_similarweb_quality_rewards_deep_page_level_evidence(self) -> None:
        data = {
            "website_evidence": {
                "website_performance": {"available": True},
                "website_content": {"summary": {"rows": [{"folder": "/game"}]}},
                "search_overview": {
                    "top_non_brand_keywords": {"rows": [{"keyword": "free games"}]},
                    "paid_landing_pages": {"rows": [{"url": "site.com/game/1"}]},
                },
            }
        }

        quality = capture_bundle.assess_capture_quality("similarweb", data)

        self.assertEqual(quality["status"], "ok")
        self.assertTrue(quality["core_ready"])
        self.assertEqual(quality["score"], 4)
        self.assertIn("paid-landing-pages-ready", quality["reasons"])

    def test_capture_api_exposes_single_browser_single_page_policy(self) -> None:
        original_run_capture_with_retries = capture_api.run_capture_with_retries
        try:
            def fake_run_capture_with_retries(**kwargs):
                tool = kwargs["tool"]
                return (
                    {"tool": tool, "ok": True},
                    [
                        {
                            "tool": tool,
                            "session": f"dvos-{tool}-a1",
                            "status": "ok",
                            "quality": {"core_ready": True, "score": 3, "reasons": ["core-report-ready"]},
                        }
                    ],
                    {
                        "tool": tool,
                        "session": f"dvos-{tool}-a1",
                        "status": "ok",
                        "quality": {"core_ready": True, "score": 3, "reasons": ["core-report-ready"]},
                    },
                )

            capture_api.run_capture_with_retries = fake_run_capture_with_retries
            plan = capture_api.run_capture_plan(
                query="crazygames.com",
                username="u",
                password="p",
                tools=["semrush", "similarweb"],
                session_prefix="dvos-capture",
                keep_session=False,
                max_node_rotations=2,
                continue_on_error=False,
                request_id="req-1",
            )
        finally:
            capture_api.run_capture_with_retries = original_run_capture_with_retries

        policy = plan["execution_policy"]
        self.assertEqual(policy["device_scope"], "single_device")
        self.assertEqual(policy["browser_scope"], "single_browser")
        self.assertEqual(policy["page_scope"], "single_active_page")
        self.assertEqual(policy["run_mode"], "serial")
        self.assertEqual(policy["tab_strategy"], "collapse_non_active_tabs_after_tool_open")
        self.assertEqual(plan["summary"]["core_ready_tools"], ["semrush", "similarweb"])
        self.assertTrue(plan["summary"]["all_succeeded"])

    def test_capture_api_adds_normalized_cross_tool_schema(self) -> None:
        original_run_capture_with_retries = capture_api.run_capture_with_retries
        try:
            def fake_run_capture_with_retries(**kwargs):
                tool = kwargs["tool"]
                if tool == "semrush":
                    data = {
                        "domain_overview": {
                            "domain": "crazygames.com",
                            "database": "us",
                            "organic_traffic": 93600000,
                            "paid_traffic": 576100,
                            "global_rank": 400,
                        },
                        "top_pages": [
                            {
                                "url": "https://www.crazygames.com/",
                                "title": "CrazyGames",
                                "top_keyword": "crazy games",
                                "traffic": 3272000,
                                "traffic_percent": 27.82,
                                "volume": 4090000,
                                "position": 1,
                            }
                        ],
                        "top_organic_keywords": [
                            {
                                "keyword": "crazy games",
                                "position": 1,
                                "position_difference": 0,
                                "volume": 4090000,
                                "traffic": 3272000,
                                "traffic_percent": 27.82,
                                "keyword_difficulty": 85,
                                "url": "https://www.crazygames.com/",
                            }
                        ],
                        "organic_competitors": [
                            {
                                "domain": "poki.com",
                                "common_keywords": 68911,
                                "competition_level": 0.54,
                                "organic_positions": 489811,
                                "organic_traffic": 11635769,
                                "traffic": 11635769,
                            }
                        ],
                        "top_topics": [
                            {
                                "topic": "Online Multiplayer Games",
                                "keywords_count": 25026,
                                "top_page_url": "https://www.crazygames.com/",
                                "top_page_keyword": "crazy games",
                            }
                        ],
                        "markets_current": [
                            {
                                "database": "us",
                                "rank": 400,
                                "organic_traffic": 93600000,
                                "organic_traffic_branded": 52000000,
                                "organic_traffic_non_branded": 41600000,
                                "paid_traffic": 576100,
                            }
                        ],
                        "backlink_overview": {"referring_domains": 32976},
                    }
                else:
                    data = {
                        "website_evidence": {
                            "report_navigation_used": "hash_route_assign",
                            "similar_sites": [{"domain": "poki.com", "visits": "120M"}],
                            "website_performance": {
                                "available": True,
                                "total_visits": {
                                    "date_range": "Mar 2026 - May 2026",
                                    "geography": "全球",
                                    "visits": "315.9M",
                                    "change_pct": "8.56%",
                                },
                                "ranks": {"global_rank": "#386"},
                                "top_countries": {
                                    "rows": [{"country": "United States", "share": "24.5%", "change": "2.1%"}]
                                },
                                "traffic_channels": {
                                    "rows": [{"channel": "直接", "share": "48.42%"}]
                                },
                                "organic_search": {"share_of_traffic": "42.97%"},
                                "paid_search": {"share_of_traffic": "1.11%"},
                            },
                            "website_content_top_pages": {
                                "summary": {
                                    "rows": [
                                        {
                                            "rank": 1,
                                            "url": "crazygames.com/game/geometry-dash-online",
                                            "share": "3.94%",
                                            "month_over_month_change": "0%",
                                        }
                                    ]
                                }
                            },
                            "keyword_research": {
                                "quick_search_keywords": ["crazygames"],
                                "top_non_brand_keywords": {
                                    "rows": [
                                        {
                                            "keyword": "juegos",
                                            "clicks": "1.2M",
                                            "share": "3.22%",
                                            "year_over_year_change": "52.66%",
                                            "organic_share": "98.89%",
                                            "paid_share": "1.11%",
                                        }
                                    ]
                                },
                            },
                            "search_overview": {
                                "summary": {
                                    "brand_vs_non_brand": {
                                        "branded": "61.06%",
                                        "non_branded": "38.94%",
                                    }
                                }
                            },
                            "landing_pages_research": {
                                "folder_rows": [
                                    {"rank": 1, "folder": "crazygames.com/game", "share": "41.96%", "month_over_month_change": "0.41 pp"}
                                ],
                                "top_pages": {
                                    "summary": {
                                        "rows": [
                                            {
                                                "rank": 1,
                                                "url": "crazygames.com/game/geometry-dash-online",
                                                "share": "3.94%",
                                                "month_over_month_change": "0%",
                                            }
                                        ]
                                    }
                                },
                                "paid_landing_pages": {
                                    "rows": [
                                        {
                                            "url": "crazygames.com/game/geometry-dash-online",
                                            "clicks": "18K",
                                            "share": "3.94%",
                                            "month_over_month_change": "0%",
                                            "top_keyword": {"keyword": "geometry dash", "new_keywords": 12},
                                        }
                                    ]
                                },
                            },
                            "home_signals": {"priority_alerts": [{"metric": "landing_pages"}, {"metric": "keywords"}]},
                        }
                    }
                meta = {
                    "tool": tool,
                    "session": f"dvos-{tool}-a1",
                    "status": "ok",
                    "quality": {"core_ready": True, "score": 4, "reasons": ["core-report-ready"]},
                }
                return data, [meta], meta

            capture_api.run_capture_with_retries = fake_run_capture_with_retries
            plan = capture_api.run_capture_plan(
                query="crazygames.com",
                username="u",
                password="p",
                tools=["semrush", "similarweb"],
                session_prefix="dvos-capture",
            )
        finally:
            capture_api.run_capture_with_retries = original_run_capture_with_retries

        normalized = plan["normalized"]
        self.assertEqual(normalized["query"]["value"], "crazygames.com")
        self.assertEqual(normalized["tools_ready"], ["semrush", "similarweb"])
        self.assertEqual(normalized["coverage"]["status"], "ok")
        self.assertEqual(normalized["traffic_summary"]["monthly_visits_estimate"], 315900000)
        self.assertEqual(normalized["traffic_summary"]["organic_traffic_estimate"], 93600000)
        self.assertEqual(normalized["traffic_summary"]["global_rank"], 386)
        self.assertTrue(any(row["source_tool"] == "semrush" for row in normalized["top_pages"]))
        self.assertTrue(any(row["source_tool"] == "similarweb" for row in normalized["top_pages"]))
        self.assertTrue(any(row["source_tool"] == "similarweb" for row in normalized["landing_pages"]))
        self.assertTrue(any(row["source_tool"] == "semrush" for row in normalized["top_keywords"]))
        self.assertTrue(any(row["source_tool"] == "similarweb" for row in normalized["top_keywords"]))
        self.assertTrue(any(row["source_tool"] == "semrush" for row in normalized["competitors"]))
        self.assertTrue(any(row["source_tool"] == "similarweb" for row in normalized["competitors"]))
        self.assertEqual(normalized["tool_signals"]["similarweb"]["seed_keywords"], ["crazygames"])
        self.assertEqual(normalized["tool_signals"]["semrush"]["referring_domains"], 32976)


class CaptureServiceTests(unittest.TestCase):
    def test_capture_service_health_returns_single_page_policy(self) -> None:
        server = capture_service.build_server("127.0.0.1", 0)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["policy"]["browser_scope"], "single_browser")
        self.assertEqual(payload["policy"]["page_scope"], "single_active_page")

    def test_capture_service_capture_returns_normalized_payload(self) -> None:
        original_run_capture_plan = capture_service.capture_api.run_capture_plan
        try:
            def fake_run_capture_plan(**kwargs):
                return {
                    "api": {"name": "demand-validation-os.capture_api", "version": "2026-06-11"},
                    "request": {
                        "id": kwargs.get("request_id") or "req-1",
                        "query": {"type": "domain", "value": kwargs["query"]},
                        "tools": ["semrush"],
                    },
                    "execution_policy": capture_service.capture_api.build_execution_policy(
                        tools=["semrush"],
                        session_prefix=kwargs.get("session_prefix") or "svc",
                        keep_session=False,
                        max_node_rotations=2,
                        continue_on_error=False,
                    ),
                    "results": {
                        "semrush": {
                            "best_attempt": {
                                "status": "ok",
                                "quality": {"core_ready": True, "score": 3, "reasons": ["core-report-ready"]},
                            },
                            "data": {
                                "domain_overview": {"organic_traffic": 1000, "paid_traffic": 50},
                                "top_pages": [{"url": "https://example.com", "title": "Example"}],
                                "top_organic_keywords": [{"keyword": "example"}],
                            },
                        }
                    },
                    "summary": {
                        "requested_tools": ["semrush"],
                        "completed_tools": ["semrush"],
                        "core_ready_tools": ["semrush"],
                        "partial_tools": [],
                        "failed_tools": [],
                        "all_succeeded": True,
                    },
                    "normalized": {
                        "query": {"type": "domain", "value": kwargs["query"]},
                        "tools_ready": ["semrush"],
                        "traffic_summary": {"organic_traffic_estimate": 1000},
                    },
                }

            capture_service.capture_api.run_capture_plan = fake_run_capture_plan
            server = capture_service.build_server("127.0.0.1", 0)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                req = Request(
                    f"http://127.0.0.1:{port}/capture",
                    data=json.dumps(
                        {
                            "query": "crazygames.com",
                            "tools": ["semrush"],
                            "username": "u",
                            "password": "p",
                            "request_id": "svc-1",
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        finally:
            capture_service.capture_api.run_capture_plan = original_run_capture_plan

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["request_id"], "svc-1")
        self.assertEqual(payload["data"]["normalized"]["tools_ready"], ["semrush"])
        self.assertEqual(payload["data"]["execution_policy"]["page_scope"], "single_active_page")

    def test_capture_service_rejects_parallel_request_when_busy(self) -> None:
        server = capture_service.build_server("127.0.0.1", 0)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        acquired = capture_service.SERVICE_LOCK.acquire(blocking=False)
        self.assertTrue(acquired)
        try:
            req = Request(
                f"http://127.0.0.1:{port}/capture",
                data=json.dumps(
                    {
                        "query": "crazygames.com",
                        "tools": ["semrush"],
                        "username": "u",
                        "password": "p",
                        "request_id": "svc-busy",
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(HTTPError) as ctx:
                urlopen(req, timeout=5)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
        finally:
            capture_service.SERVICE_LOCK.release()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(ctx.exception.code, 409)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "capture_busy")


class GuidedFlowTests(unittest.TestCase):
    def test_guided_flow_uses_web_cafe_style_entry(self) -> None:
        workflow = {
            "mode": "demand",
            "input": {"query": "ai image generator"},
            "decision": {"band": "ship_cluster", "total_score": 74},
            "report": {"recommended_action": "ship_cluster", "first_batch_of_pages": [{}]},
            "knowledge": {
                "gefei": {"query": {"summary": "summary"}},
                "chuhai": {"focus_methods": ["m1"], "method_highlights": ["m2", "m3"]},
            },
            "evidence": {
                "trends": {"summary": {"primary_shape": "rising", "top_rising_queries": [{"query": "x"}]}},
                "tool_capture": {"summary": {"core_ready_tools": ["semrush", "similarweb"]}},
            },
            "scores": {"raw_scores": {"clusterability": 4, "monetization": 4, "execution_fit": 3}},
            "inferences": {"query_intent": "工具页", "page_type": "工具页"},
            "derived": {
                "page_signal_summary": "ps",
                "top_page_examples": "tp",
                "cluster_summary": "cs",
                "monetization_summary": "ms",
            },
        }
        guided = guided_flow.build_guided_flow(workflow)
        self.assertEqual(guided["entry"]["primary_cta"], "跟我走完分阶段诊断")
        self.assertEqual(guided["step_count"], 8)
        self.assertEqual(guided["stages"][0]["title"], "先把问题框准")

    def test_guided_flow_reads_gefei_summary_and_handles_degraded_trends(self) -> None:
        workflow = {
            "mode": "demand",
            "input": {"query": "pdf to epub"},
            "decision": {"band": "watch", "total_score": 48},
            "report": {"recommended_action": "watch", "search_proof": "proof", "page_type_recommendation": "工具页"},
            "knowledge": {
                "gefei": {"summary": "不要只交关键词列表"},
                "chuhai": {"focus_methods": ["landing pages"], "method_highlights": ["x", "y"]},
            },
            "evidence": {
                "trends": {"available": False, "summary": {"primary_shape": "missing", "top_rising_queries": []}},
                "tool_capture": {"summary": {"core_ready_tools": ["semrush"]}},
            },
            "scores": {"raw_scores": {"clusterability": 2, "monetization": 3, "execution_fit": 3}},
            "inferences": {"query_intent": "工具页", "page_type": "工具页"},
            "derived": {
                "page_signal_summary": "ps",
                "top_page_examples_text": "tp",
                "cluster_summary": "cs",
                "monetization_summary": "ms",
            },
        }
        guided = guided_flow.build_guided_flow(workflow)
        search_stage_facts = guided["stages"][2]["facts"]
        self.assertTrue(any("Trends available: False" in fact for fact in search_stage_facts))
        self.assertTrue(any("Semrush ready" in fact for fact in search_stage_facts))
        demand_stage_facts = guided["stages"][1]["facts"]
        self.assertTrue(any("不要只交关键词列表" in fact for fact in demand_stage_facts))
        self.assertTrue(any("landing pages" in fact for fact in demand_stage_facts))


class MethodAlignmentTests(unittest.TestCase):
    def test_method_alignment_marks_all_three_layers(self) -> None:
        knowledge = {
            "gefei": {"summary": "不要只交关键词列表", "search_output": "similarweb"},
            "chuhai": {"focus_methods": ["landing pages", "top pages"], "method_highlights": ["着落页", "主要页面"]},
        }
        bundle = {"summary": {"core_ready_tools": ["semrush", "similarweb"]}}
        trends = {"available": False}
        guided = {
            "entry": {
                "contradiction": "c",
                "hidden_variable": "hv",
                "primary_cta": "p",
                "secondary_cta": "s",
            },
            "step_count": 8,
            "direct_result": {"band": "watch"},
        }
        alignment = run_demand_workflow.build_method_alignment(
            mode="demand",
            query="pdf to epub",
            page_type="工具页",
            knowledge=knowledge,
            trends=trends,
            bundle=bundle,
            guided=guided,
        )
        self.assertTrue(alignment["gefei"]["used"])
        self.assertTrue(alignment["chuhai"]["used"])
        self.assertTrue(alignment["web_cafe_simulator"]["used"])
        self.assertTrue(alignment["gefei"]["signals_used"]["has_search_output"])
        self.assertEqual(alignment["web_cafe_simulator"]["workflow_match"]["bounded_step_count"], 8)
        self.assertEqual(alignment["web_cafe_simulator"]["simulator_mapping"]["page_type"], "工具页")


class BuildWorkflowOrchestrationTests(unittest.TestCase):
    def test_build_workflow_runs_full_one_click_chain(self) -> None:
        original_knowledge_payload = run_demand_workflow.knowledge_payload
        original_collect = google_trends.collect
        original_capture_bundle_payload = run_demand_workflow.capture_bundle_payload
        original_demand_raw_scores = run_demand_workflow.demand_raw_scores
        original_score_payload = run_demand_workflow.score_payload
        original_demand_report = run_demand_workflow.demand_report
        original_build_guided_flow = guided_flow.build_guided_flow
        original_build_method_alignment = run_demand_workflow.build_method_alignment
        original_build_page_artifacts_payload = run_demand_workflow.build_page_artifacts_payload

        calls: list[str] = []
        fake_knowledge = {
            "gefei": {"summary": "不要只交关键词列表", "search_output": "similarweb"},
            "chuhai": {"focus_methods": ["landing pages"], "method_highlights": ["着落页", "主要页面"]},
        }
        fake_trends = {
            "available": True,
            "summary": {
                "primary_shape": "rising",
                "top_rising_queries": [{"query": "pdf to epub free"}],
            },
        }
        fake_bundle = {
            "summary": {"core_ready_tools": ["semrush", "similarweb"]},
            "results": {
                "semrush": {"data": {"top_pages": [], "top_organic_keywords": []}},
                "similarweb": {"data": {"website_evidence": {"website_performance": {"available": True}}}},
            },
        }
        fake_raw_scores = {
            "demand_reality": 4,
            "search_carry": 4,
            "trend_stability": 4,
            "serp_entry": 3,
            "page_intent_fit": 4,
            "clusterability": 4,
            "monetization": 3,
            "execution_fit": 3,
        }
        fake_reasoning = {"demand_reality": ["community and page evidence available"]}
        fake_derived = {
            "cluster_summary": "这是一个可扩展的页面集群机会。",
            "page_signal_summary": "Semrush / Similarweb 页级证据都已到位。",
            "keyword_signal_summary": "关键词和落地页证据都已到位。",
            "monetization_summary": "先做工具页更容易交付结果。",
            "top_page_examples_text": "example page",
        }
        fake_score_result = {
            "band": "ship_cluster",
            "total_score": 74,
            "all_hard_gates_passed": True,
        }
        fake_report = {
            "recommended_action": "ship_cluster",
            "first_batch_of_pages": [{"slug": "pdf-to-epub"}],
        }
        fake_guided = {
            "entry": {
                "contradiction": "这个词看起来能做，但到底是不是被搜索承接？",
                "hidden_variable": "search carry",
                "primary_cta": "跟我走完分阶段诊断",
                "secondary_cta": "直接看最终建议",
            },
            "step_count": 8,
            "direct_result": {"band": "ship_cluster"},
        }
        fake_alignment = {
            "gefei": {"used": True},
            "chuhai": {"used": True},
            "web_cafe_simulator": {"used": True},
        }
        fake_artifacts = {
            "available": True,
            "brand_context": {"brand_name": "BrandX"},
            "page_count": 1,
            "pages": [{"slug": "pdf-to-epub-alternative"}],
        }

        try:
            def fake_knowledge_payload(mode: str, query: str) -> dict:
                calls.append("knowledge")
                self.assertEqual(mode, "demand")
                self.assertEqual(query, "pdf to epub")
                return fake_knowledge

            def fake_collect(query: str, geo: str = "US", *args, **kwargs) -> dict:
                calls.append("trends")
                self.assertEqual(query, "pdf to epub")
                self.assertEqual(geo, "US")
                return fake_trends

            def fake_capture_bundle_payload(**kwargs) -> dict:
                calls.append("bundle")
                self.assertEqual(kwargs["domain"], "pdftoepub.app")
                return fake_bundle

            def fake_demand_raw_scores(*, query: str, page_type: str, trends: dict, bundle: dict):
                calls.append("raw_scores")
                self.assertEqual(query, "pdf to epub")
                self.assertEqual(page_type, "content")
                self.assertIs(trends, fake_trends)
                self.assertIs(bundle, fake_bundle)
                return fake_raw_scores, fake_reasoning, fake_derived

            def fake_score_payload(mode: str, raw_scores: dict) -> dict:
                calls.append("scorecard")
                self.assertEqual(mode, "demand")
                self.assertEqual(raw_scores, fake_raw_scores)
                return fake_score_result

            def fake_demand_report(**kwargs) -> dict:
                calls.append("report")
                self.assertEqual(kwargs["query"], "pdf to epub")
                self.assertEqual(kwargs["page_type"], "content")
                self.assertEqual(kwargs["score_result"], fake_score_result)
                self.assertIs(kwargs["trends"], fake_trends)
                self.assertEqual(kwargs["derived"], fake_derived)
                return fake_report

            def fake_build_guided_flow(workflow: dict) -> dict:
                calls.append("guided_flow")
                self.assertEqual(workflow["knowledge"], fake_knowledge)
                self.assertEqual(workflow["report"], fake_report)
                self.assertEqual(workflow["scores"]["raw_scores"], fake_raw_scores)
                return fake_guided

            def fake_build_method_alignment(**kwargs) -> dict:
                calls.append("method_alignment")
                self.assertEqual(kwargs["knowledge"], fake_knowledge)
                self.assertIs(kwargs["trends"], fake_trends)
                self.assertIs(kwargs["bundle"], fake_bundle)
                self.assertEqual(kwargs["guided"], fake_guided)
                return fake_alignment

            def fake_build_page_artifacts_payload(workflow: dict, **kwargs) -> dict:
                calls.append("artifacts")
                self.assertEqual(workflow["report"], fake_report)
                self.assertEqual(kwargs["brand_name"], "")
                return fake_artifacts

            run_demand_workflow.knowledge_payload = fake_knowledge_payload
            google_trends.collect = fake_collect
            run_demand_workflow.capture_bundle_payload = fake_capture_bundle_payload
            run_demand_workflow.demand_raw_scores = fake_demand_raw_scores
            run_demand_workflow.score_payload = fake_score_payload
            run_demand_workflow.demand_report = fake_demand_report
            guided_flow.build_guided_flow = fake_build_guided_flow
            run_demand_workflow.build_method_alignment = fake_build_method_alignment
            run_demand_workflow.build_page_artifacts_payload = fake_build_page_artifacts_payload

            workflow = run_demand_workflow.build_workflow(
                mode="demand",
                query="pdf to epub",
                domain="pdftoepub.app",
                geo="US",
                username="u",
                password="p",
                max_node_rotations=2,
            )
        finally:
            run_demand_workflow.knowledge_payload = original_knowledge_payload
            google_trends.collect = original_collect
            run_demand_workflow.capture_bundle_payload = original_capture_bundle_payload
            run_demand_workflow.demand_raw_scores = original_demand_raw_scores
            run_demand_workflow.score_payload = original_score_payload
            run_demand_workflow.demand_report = original_demand_report
            guided_flow.build_guided_flow = original_build_guided_flow
            run_demand_workflow.build_method_alignment = original_build_method_alignment
            run_demand_workflow.build_page_artifacts_payload = original_build_page_artifacts_payload

        self.assertEqual(
            calls,
            ["knowledge", "trends", "bundle", "raw_scores", "scorecard", "report", "guided_flow", "method_alignment", "artifacts"],
        )
        self.assertEqual(workflow["guided_flow"], fake_guided)
        self.assertEqual(workflow["method_alignment"], fake_alignment)
        self.assertEqual(workflow["artifacts"]["page_artifacts"], fake_artifacts)
        self.assertEqual(workflow["decision"]["band"], "ship_cluster")
        self.assertEqual(workflow["report"], fake_report)


class TrendsDegradeTests(unittest.TestCase):
    def test_degraded_trends_payload_marks_unavailable(self) -> None:
        payload = run_demand_workflow.degraded_trends_payload("ai image generator", "US", "429")
        self.assertFalse(payload["available"])
        self.assertEqual(payload["summary"]["primary_shape"], "missing")
        self.assertEqual(len(payload["windows"]), 4)


class WorkflowNormalizedIntegrationTests(unittest.TestCase):
    def test_capture_bundle_payload_accepts_prebuilt_bundle_payload(self) -> None:
        bundle = {
            "request": {"query": {"type": "domain", "value": "crazygames.com"}},
            "results": {"semrush": {"data": {}}, "similarweb": {"data": {}}},
            "summary": {"core_ready_tools": ["semrush"]},
            "normalized": {"tools_ready": ["semrush"]},
        }
        payload = run_demand_workflow.capture_bundle_payload(
            domain="crazygames.com",
            username="u",
            password="p",
            max_node_rotations=2,
            bundle_payload=bundle,
        )
        self.assertEqual(payload["normalized"]["tools_ready"], ["semrush"])

    def test_build_workflow_accepts_bundle_payload_and_keeps_normalized_layer(self) -> None:
        original_knowledge_payload = run_demand_workflow.knowledge_payload
        original_collect = google_trends.collect
        try:
            run_demand_workflow.knowledge_payload = lambda mode, query: {
                "gefei": {"summary": "不要只交关键词列表", "search_output": "similarweb"},
                "chuhai": {"focus_methods": ["landing pages"], "method_highlights": ["着落页", "主要页面"]},
            }
            google_trends.collect = lambda query, geo="US": {
                "available": True,
                "summary": {"primary_shape": "rising", "top_rising_queries": [{"query": "pdf to epub free"}]},
            }
            bundle = {
                "request": {"query": {"type": "domain", "value": "pdftoepub.app"}},
                "results": {
                    "semrush": {
                        "data": {
                            "top_pages": [{"url": "https://pdftoepub.app/tool", "title": "PDF to EPUB", "top_keyword": "pdf to epub"}],
                            "top_organic_keywords": [{"keyword": "pdf to epub"}],
                        }
                    },
                    "similarweb": {"data": {"website_evidence": {"website_performance": {"available": True}}}},
                },
                "summary": {"core_ready_tools": ["semrush", "similarweb"]},
                "normalized": {
                    "tools_ready": ["semrush", "similarweb"],
                    "top_pages": [
                        {
                            "url": "https://pdftoepub.app/tool",
                            "title": "PDF to EPUB",
                            "page_kind": "organic_top_page",
                            "top_keyword": "pdf to epub",
                            "source_tool": "semrush",
                        }
                    ],
                    "top_keywords": [
                        {
                            "keyword": "pdf to epub",
                            "keyword_kind": "organic",
                            "source_tool": "semrush",
                        }
                    ],
                    "landing_pages": [],
                    "page_clusters": [],
                    "traffic_summary": {"monthly_visits_estimate": 100000},
                    "tool_signals": {"similarweb": {"website_performance_ready": True}, "semrush": {}},
                },
            }
            workflow = run_demand_workflow.build_workflow(
                mode="demand",
                query="pdf to epub",
                domain="pdftoepub.app",
                geo="US",
                username="u",
                password="p",
                max_node_rotations=2,
                bundle_payload=bundle,
            )
        finally:
            run_demand_workflow.knowledge_payload = original_knowledge_payload
            google_trends.collect = original_collect

        self.assertEqual(workflow["evidence"]["tool_capture"]["normalized"]["tools_ready"], ["semrush", "similarweb"])
        self.assertTrue(workflow["artifacts"]["page_artifacts"]["available"])


class NormalizedArtifactTests(unittest.TestCase):
    def test_page_artifacts_evidence_counts_prefer_normalized_layer(self) -> None:
        workflow = {
            "evidence": {
                "tool_capture": {
                    "normalized": {
                        "top_pages": [
                            {"source_tool": "semrush"},
                            {"source_tool": "semrush"},
                            {"source_tool": "similarweb"},
                        ],
                        "top_keywords": [
                            {"source_tool": "semrush"},
                            {"source_tool": "similarweb"},
                            {"source_tool": "similarweb"},
                        ],
                        "landing_pages": [
                            {"source_tool": "similarweb", "landing_type": "paid_landing_page"},
                            {"source_tool": "similarweb", "landing_type": "popular_page"},
                        ],
                        "page_clusters": [
                            {"source_tool": "similarweb", "cluster_type": "folder"},
                            {"source_tool": "similarweb", "cluster_type": "folder"},
                        ],
                        "tool_signals": {
                            "similarweb": {"keyword_count": 2, "landing_page_count": 1},
                            "semrush": {},
                        },
                    }
                }
            }
        }
        counts = page_artifacts.evidence_counts(workflow)
        self.assertEqual(counts["semrush_top_pages"], 2)
        self.assertEqual(counts["similarweb_non_brand_keywords"], 2)
        self.assertEqual(counts["similarweb_paid_landing_pages"], 1)
        self.assertEqual(counts["similarweb_folder_rows"], 2)


class WorkflowServiceTests(unittest.TestCase):
    def test_workflow_service_returns_scale_output_and_page_artifacts(self) -> None:
        original_build_workflow = workflow_service.run_demand_workflow.build_workflow
        try:
            workflow_service.run_demand_workflow.build_workflow = lambda **kwargs: {
                "mode": "demand",
                "input": {"query": kwargs["query"], "domain": kwargs["domain"]},
                "decision": {
                    "band": "ship_cluster",
                    "recommended_action": "ship_cluster",
                    "total_score": 74,
                    "all_hard_gates_passed": True,
                },
                "report": {
                    "core_conclusion": "建议继续做。",
                    "recommended_action": "ship_cluster",
                    "page_type_recommendation": "优先按对比页承接。",
                    "first_batch_of_pages": [{"working_title": "ahrefs alternative"}],
                },
                "evidence": {
                    "tool_capture": {
                        "normalized": {
                            "tools_ready": ["semrush", "similarweb"],
                            "coverage": {"status": "ok"},
                            "traffic_summary": {"monthly_visits_estimate": 100000},
                            "top_pages": [{}, {}],
                            "top_keywords": [{}, {}, {}],
                            "landing_pages": [{}],
                            "page_clusters": [{}],
                        }
                    }
                },
                "artifacts": {
                    "page_artifacts": {
                        "available": True,
                        "page_count": 1,
                        "pages": [{"slug": "ahrefs-alternative"}],
                    }
                },
            }
            server = workflow_service.build_server("127.0.0.1", 0)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                req = Request(
                    f"http://127.0.0.1:{port}/workflow/page-artifacts",
                    data=json.dumps(
                        {
                            "mode": "demand",
                            "query": "ahrefs alternative",
                            "bundle_payload": {
                                "results": {},
                                "summary": {},
                                "normalized": {},
                            },
                            "request_id": "wf-1",
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        finally:
            workflow_service.run_demand_workflow.build_workflow = original_build_workflow

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["request_id"], "wf-1")
        self.assertEqual(payload["data"]["workflow_summary"]["decision"]["recommended_action"], "ship_cluster")
        self.assertTrue(payload["data"]["page_artifacts"]["available"])
        self.assertEqual(payload["data"]["workflow_summary"]["normalized_snapshot"]["top_keyword_count"], 3)
