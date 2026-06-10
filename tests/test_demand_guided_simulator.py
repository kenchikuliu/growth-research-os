from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIMULATOR_PATH = ROOT / "skills" / "demand-guided-simulator" / "scripts" / "demand_guided_simulator.py"

spec = importlib.util.spec_from_file_location("demand_guided_simulator", SIMULATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load simulator module from {SIMULATOR_PATH}")
demand_guided_simulator = importlib.util.module_from_spec(spec)
sys.modules["demand_guided_simulator"] = demand_guided_simulator
spec.loader.exec_module(demand_guided_simulator)


def sample_workflow() -> dict:
    return {
        "mode": "demand",
        "guided_flow": {
            "entry": {
                "headline": "把 pdf to epub 从想法拆成证据",
                "contradiction": "这个词看起来能做，但它到底是噪音还是被搜索稳定承接？",
                "hidden_variable": "决定结果的不是搜索量，而是 search carry 和 page shape。",
                "primary_cta": "跟我走完分阶段诊断",
                "secondary_cta": "直接看最终建议",
                "bounded_scope": "8 步数据化诊断",
                "decision_preview": "ship_page",
            },
            "step_count": 8,
            "stages": [
                {
                    "step": 1,
                    "title": "先把问题框准",
                    "question": "用户到底要什么页面？",
                    "facts": ["query=pdf to epub"],
                    "inference": "先定页面类型。",
                    "diagnosis": "工具页更合理。",
                    "next_action": "先做工具页。",
                },
                {
                    "step": 2,
                    "title": "需求到底真不真",
                    "question": "这个需求背后有没有稳定痛点？",
                    "facts": ["不要只交关键词列表"],
                    "inference": "规则层先过一遍。",
                    "diagnosis": "需求有验证空间。",
                    "next_action": "补社区证据。",
                },
            ],
            "direct_result": {
                "band": "ship_page",
                "total_score": 66,
                "all_hard_gates_passed": True,
                "recommended_action": "ship_one_page",
            },
        },
        "decision": {
            "band": "ship_page",
            "total_score": 66,
            "all_hard_gates_passed": True,
            "recommended_action": "ship_one_page",
        },
        "report": {
            "recommended_action": "ship_one_page",
            "first_batch_of_pages": [{"slug": "pdf-to-epub"}],
        },
        "evidence": {
            "trends": {"available": True},
            "tool_capture": {
                "summary": {"core_ready_tools": ["semrush", "similarweb"]},
                "results": {
                    "semrush": {
                        "data": {
                            "top_pages": [{"url": "https://site.com/pdf-to-epub"}],
                            "top_organic_keywords": [{"keyword": "pdf to epub"}],
                        }
                    },
                    "similarweb": {
                        "data": {
                            "website_evidence": {
                                "website_performance": {"available": True},
                                "website_content": {"summary": {"rows": [{"folder": "/converter"}]}},
                                "search_overview": {
                                    "paid_landing_pages": {"rows": [{"url": "https://site.com/pricing"}]},
                                    "top_non_brand_keywords": {"rows": [{"keyword": "convert pdf to epub"}]},
                                },
                            }
                        }
                    },
                },
            },
        },
        "knowledge": {
            "gefei": {"summary": "不要只交关键词列表"},
            "chuhai": {"focus_methods": ["landing pages", "top pages"]},
        },
        "method_alignment": {
            "web_cafe_simulator": {
                "used": True,
                "workflow_match": {"bounded_step_count": 8},
            }
        },
    }


class DemandGuidedSimulatorTests(unittest.TestCase):
    def test_guided_view_exposes_stages_and_evidence(self) -> None:
        data = demand_guided_simulator.build_simulator_surface(sample_workflow(), view="guided")

        self.assertEqual(data["mode"], "demand")
        self.assertEqual(data["step_count"], 8)
        self.assertEqual(data["stage_index"][0]["title"], "先把问题框准")
        self.assertEqual(data["evidence_status"]["semrush_top_pages"], 1)
        self.assertEqual(data["evidence_status"]["similarweb_paid_landing_rows"], 1)

    def test_direct_view_keeps_method_alignment(self) -> None:
        data = demand_guided_simulator.build_simulator_surface(sample_workflow(), view="direct")

        self.assertEqual(data["direct_result"]["band"], "ship_page")
        self.assertTrue(data["method_alignment"]["web_cafe_simulator"]["used"])

    def test_step_view_selects_single_step(self) -> None:
        data = demand_guided_simulator.build_simulator_surface(sample_workflow(), view="step", step=2)

        self.assertEqual(data["current_step"]["step"], 2)
        self.assertEqual(data["current_step"]["title"], "需求到底真不真")

    def test_step_view_requires_step_argument(self) -> None:
        with self.assertRaises(ValueError):
            demand_guided_simulator.build_simulator_surface(sample_workflow(), view="step")

    def test_step_view_rejects_out_of_range_step(self) -> None:
        with self.assertRaises(ValueError):
            demand_guided_simulator.build_simulator_surface(sample_workflow(), view="step", step=9)


if __name__ == "__main__":
    unittest.main()
