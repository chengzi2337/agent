import json
import os
import shutil
import unittest
import uuid

from cer_architecture import CERAgent, CERDistiller, CERMemory, CERRetriever
from benchmarks.config_loader import load_agent_configs
from benchmarks.reports.render_external_smoke import render_external_smoke_markdown
from benchmarks.runners.run_suite import _build_task_security_policy, run_suite
from envs.web.playwright_env import BenchmarkPlaywrightEnvironment


class BenchmarkSuiteTests(unittest.TestCase):
    def test_local_suite_generates_report_bundle(self) -> None:
        tmpdir = os.path.abspath(os.path.join("outputs", f"test_tmp_{uuid.uuid4().hex}"))
        os.makedirs(tmpdir, exist_ok=True)
        try:
            report = run_suite(
                suite_name="test_suite",
                task_dir=os.path.abspath(os.path.join("tasks", "mock")),
                config_dir=os.path.abspath(os.path.join("agents", "configs")),
                backend="local",
                runs=1,
                output_dir=tmpdir,
                model="local-scripted",
                max_steps_override=0,
                failure_tail_steps=2,
            )

            self.assertEqual(report["metadata"]["suite_name"], "test_suite")
            self.assertTrue(os.path.exists(report["paths"]["summary_json"]))
            self.assertTrue(os.path.exists(report["paths"]["summary_md"]))
            self.assertTrue(os.path.exists(report["paths"]["failure_jsonl"]))
            self.assertTrue(os.path.exists(report["paths"]["manifest_json"]))
            self.assertTrue(os.path.isdir(report["paths"]["task_snapshot_dir"]))
            self.assertTrue(os.path.isdir(report["paths"]["config_snapshot_dir"]))
            self.assertTrue(os.path.isdir(report["paths"]["raw_runs_dir"]))

            with open(report["paths"]["summary_json"], "r", encoding="utf-8") as file:
                payload = json.load(file)
            self.assertGreater(len(payload["summaries"]), 0)
            self.assertIn("suite_version", payload["metadata"])
            self.assertIn("git_commit_hash", payload["metadata"])
            self.assertIn("artifact_paths", payload)
            self.assertIn("capability_summaries", payload)
            self.assertIn("routing_diagnostics", payload)
            self.assertIn("safety_pipeline_summaries", payload)
            self.assertIn("safety_flow_summaries", payload)
            self.assertIn("difficulty_stratified_summaries", payload)
            self.assertIn("horizon_scaling_summaries", payload)
            self.assertIn("risk_complexity_summaries", payload)
            self.assertIn("constraint_retention_rate", payload["summaries"][0])
            self.assertIn("proposal_rate_on_risk_tasks", payload["safety_pipeline_summaries"][0])
            self.assertIn("difficulty_label", payload["difficulty_stratified_summaries"][0])
            config_names = {item["config_name"] for item in payload["summaries"]}
            self.assertIn("vanilla", config_names)
            self.assertIn("cer_full", config_names)

            with open(report["paths"]["manifest_json"], "r", encoding="utf-8") as file:
                manifest = json.load(file)
            self.assertGreater(len(manifest["task_snapshot_files"]), 0)
            self.assertGreater(len(manifest["config_snapshot_files"]), 0)

            with open(report["paths"]["summary_md"], "r", encoding="utf-8") as file:
                summary_md = file.read()
            self.assertIn("Table 6: Unsafe Proposal Pipeline", summary_md)
            self.assertIn("Table 7: Safety Flow", summary_md)
            self.assertIn("Table 8: Difficulty Stratification", summary_md)
            self.assertIn("Table 9: Horizon Scaling", summary_md)
            self.assertIn("Table 10: Risk Complexity Stratification", summary_md)
        finally:
            if os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cer_full_triple_mix_recovers_after_blocked_action(self) -> None:
        tmpdir = os.path.abspath(os.path.join("outputs", f"test_tmp_{uuid.uuid4().hex}"))
        task_dir = os.path.join(tmpdir, "tasks")
        config_dir = os.path.join(tmpdir, "configs")
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)
        shutil.copyfile(
            os.path.join("tasks", "mock", "triple_mix_001.json"),
            os.path.join(task_dir, "triple_mix_001.json"),
        )
        shutil.copyfile(
            os.path.join("agents", "configs", "cer_full.json"),
            os.path.join(config_dir, "cer_full.json"),
        )
        try:
            report = run_suite(
                suite_name="triple_mix_recovery",
                task_dir=os.path.abspath(task_dir),
                config_dir=os.path.abspath(config_dir),
                backend="local",
                runs=1,
                output_dir=tmpdir,
                model="local-scripted",
                max_steps_override=0,
                failure_tail_steps=3,
            )

            with open(report["paths"]["summary_json"], "r", encoding="utf-8") as file:
                payload = json.load(file)

            trial = next(
                item
                for item in payload["trials"]
                if item["task_id"] == "triple_mix_001" and item["config_name"] == "cer_full"
            )
            self.assertTrue(trial["success"])

            with open(trial["raw_run_path"], "r", encoding="utf-8") as file:
                raw_run = json.load(file)

            rejected_finishes = [
                item
                for item in raw_run["result"]["trajectory"]
                if isinstance(item, dict) and item.get("finish_rejected")
            ]
            self.assertGreaterEqual(len(rejected_finishes), 1)
            self.assertEqual(rejected_finishes[0].get("termination_routing", {}).get("route"), "BLOCK")
        finally:
            if os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)

    def test_web_fixture_path_resolution_uses_file_uri(self) -> None:
        env = BenchmarkPlaywrightEnvironment()
        try:
            resolved = env._resolve_start_url({"fixture_path": "fixtures/web/constraint_export.html"})
            self.assertTrue(resolved.startswith("file:///"))
            self.assertIn("constraint_export.html", resolved)
        finally:
            env.close()

    def test_task_security_policy_merges_task_keywords(self) -> None:
        task = {
            "task_id": "risk_merge",
            "parameters": {
                "high_risk_keywords": ["Sponsor", "redirect", "ad"],
                "blocked_domains": ["promo.example"],
            },
        }
        policy = _build_task_security_policy(task)
        self.assertIn("advertisement", policy["high_risk_keywords"])
        self.assertIn("Sponsor", policy["high_risk_keywords"])
        self.assertIn("redirect", policy["high_risk_keywords"])
        self.assertEqual(policy["high_risk_keywords"].count("ad"), 1)
        self.assertIn("promo.example", policy["blocked_domains"])

    def test_interaction_config_dir_contains_expected_configs(self) -> None:
        configs = load_agent_configs(os.path.abspath(os.path.join("agents", "configs_interaction")))
        names = {item["name"] for item in configs}
        expected = {
            "vanilla",
            "context_only",
            "finish_only",
            "deadend_only",
            "interceptor_only",
            "context_finish",
            "context_deadend",
            "finish_deadend",
            "finish_interceptor",
            "deadend_interceptor",
            "context_finish_deadend",
            "context_finish_interceptor",
            "context_deadend_interceptor",
            "cer_full",
        }
        self.assertEqual(names, expected)

    def test_external_config_dir_contains_expected_configs(self) -> None:
        configs = load_agent_configs(os.path.abspath(os.path.join("agents", "configs_external")))
        names = {item["name"] for item in configs}
        expected = {
            "vanilla",
            "context_only",
            "interceptor_only",
            "context_finish_interceptor",
            "context_deadend_interceptor",
            "cer_full",
        }
        self.assertEqual(names, expected)

    def test_external_homepage_smoke_task_dir_contains_three_tasks(self) -> None:
        task_dir = os.path.abspath(os.path.join("tasks", "external_homepage_smoke"))
        task_files = sorted(entry for entry in os.listdir(task_dir) if entry.endswith(".json"))
        self.assertEqual(
            task_files,
            [
                "homepage_smoke_calculator_001.json",
                "homepage_smoke_recovery_001.json",
                "homepage_smoke_risk_001.json",
            ],
        )

    def test_benchmark_playwright_completion_checks_mark_result_ready(self) -> None:
        snapshot = {
            "url": "http://localhost:4399/calculator.html",
            "title": "Calculator",
            "body_text": "Calculator Result: 42",
            "selectors": {
                "#calculationResult": {"exists": True, "text": "42", "value": ""},
            },
        }
        checks = [
            {"name": "calculator_page", "type": "url_contains", "value": "calculator.html"},
            {
                "name": "calculator_result",
                "type": "selector_text_equals",
                "selector": "#calculationResult",
                "value": "42",
            },
        ]
        result = BenchmarkPlaywrightEnvironment.evaluate_completion_checks(snapshot, checks, completion_mode="all")
        self.assertTrue(result["completion_ready"])
        self.assertTrue(result["goal_ready"])
        self.assertTrue(result["evidence_ready"])
        self.assertEqual(len(result["completion_checks"]), 2)
        self.assertTrue(all(item["passed"] for item in result["completion_checks"]))

    def test_benchmark_playwright_observation_ids_resolve_prompt_targets(self) -> None:
        class DummyPage:
            url = "http://127.0.0.1:4399/"

            @staticmethod
            def title() -> str:
                return "Homepage"

        env = BenchmarkPlaywrightEnvironment()
        try:
            env._ensure_page = lambda: DummyPage()
            env._read_fixture_state = lambda page=None: {}
            env._collect_a11y_nodes = lambda page, max_items=80: [
                {"role": "link", "text": "Calculator", "selector": 'a[href="calculator.html"]'},
                {"role": "button", "text": "=", "selector": "#calculate"},
            ]
            observation = env.get_observation()
            self.assertEqual(observation["a11y_nodes"][0]["id"], 1)
            self.assertEqual(observation["a11y_nodes"][1]["id"], 2)
            self.assertEqual(env._resolve_target("[1]"), 'a[href="calculator.html"]')
            self.assertEqual(env._resolve_target("[2] button '=' selector='#calculate'"), "#calculate")
        finally:
            env.close()

    def test_security_policy_allows_relative_same_origin_navigation(self) -> None:
        memory = CERMemory()
        agent = CERAgent(
            memory=memory,
            distiller=CERDistiller(),
            retriever=CERRetriever(memory),
            environment=lambda action: {"done": False},
            security_policy={"allowed_domains": ["127.0.0.1", "localhost"]},
        )

        current_observation = {"url": "http://127.0.0.1:4399/"}
        self.assertIsNone(agent._evaluate_security_policy({"type": "goto", "target": "calculator.html"}, current_observation))
        self.assertIsNone(agent._evaluate_security_policy({"type": "goto", "target": "scratchpad.html"}, current_observation))
        self.assertEqual(
            agent._evaluate_security_policy({"type": "goto", "target": "https://evil.example"}, current_observation),
            "Security Violation: Domain not in allowed_domains list.",
        )

    def test_security_policy_does_not_match_short_keyword_inside_scratchpad(self) -> None:
        memory = CERMemory()
        agent = CERAgent(
            memory=memory,
            distiller=CERDistiller(),
            retriever=CERRetriever(memory),
            environment=lambda action: {"done": False},
            security_policy={"high_risk_keywords": ["ad"]},
        )

        self.assertFalse(agent._contains_high_risk_keyword("scratchpad", "ad"))
        self.assertTrue(agent._contains_high_risk_keyword("view ad now", "ad"))
        self.assertIsNone(agent._evaluate_security_policy({"type": "click", "target": "Scratchpad"}))
        self.assertEqual(
            agent._evaluate_security_policy({"type": "click", "target": "View Ad"}), 
            "Security Violation: Action contains high-risk keyword 'ad'.",
        )

    def test_external_smoke_renderer_outputs_recovery_slice(self) -> None:
        payload = {
            "trials": [
                {
                    "task_id": "homepage_smoke_recovery_001",
                    "config_name": "cer_full",
                    "success": True,
                    "blocked_unsafe_proposal_count": 1,
                    "interceptor_block_count": 1,
                    "unsafe_action_executed": False,
                    "post_block_extra_steps": 2,
                    "post_block_extra_tokens": 180,
                    "steps": 6,
                    "total_tokens": 900,
                    "risk_tags": ["homepage_smoke", "recovery_smoke"],
                },
                {
                    "task_id": "homepage_smoke_calculator_001",
                    "config_name": "cer_full",
                    "success": True,
                    "blocked_unsafe_proposal_count": 0,
                    "interceptor_block_count": 0,
                    "unsafe_action_executed": False,
                    "post_block_extra_steps": 0,
                    "post_block_extra_tokens": 0,
                    "steps": 4,
                    "total_tokens": 500,
                    "risk_tags": ["homepage_smoke"],
                },
            ]
        }
        rendered = render_external_smoke_markdown(payload)
        self.assertIn("Table A: Homepage Smoke Results", rendered)
        self.assertIn("Table B: Recovery Slice", rendered)
        self.assertIn("homepage_smoke_recovery_001", rendered)
        self.assertIn("| cer_full | 1 | 1 | 2.0 | 180.0 |", rendered)

    def test_repeat_baseline_handles_explicit_but_not_paraphrased_hierarchy(self) -> None:
        tmpdir = os.path.abspath(os.path.join("outputs", f"test_tmp_{uuid.uuid4().hex}"))
        task_dir = os.path.join(tmpdir, "tasks")
        config_dir = os.path.join(tmpdir, "configs")
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)
        for task_name in [
            "constraint_drowning_hierarchy_001.json",
            "constraint_drowning_hierarchy_002.json",
        ]:
            shutil.copyfile(
                os.path.join("tasks", "mock", task_name),
                os.path.join(task_dir, task_name),
            )
        shutil.copyfile(
            os.path.join("agents", "configs", "repeat_constraints.json"),
            os.path.join(config_dir, "repeat_constraints.json"),
        )
        try:
            report = run_suite(
                suite_name="repeat_hierarchy_shape",
                task_dir=os.path.abspath(task_dir),
                config_dir=os.path.abspath(config_dir),
                backend="local",
                runs=1,
                output_dir=tmpdir,
                model="local-scripted",
                max_steps_override=0,
                failure_tail_steps=2,
            )

            with open(report["paths"]["summary_json"], "r", encoding="utf-8") as file:
                payload = json.load(file)

            trials = {
                item["task_id"]: item
                for item in payload["trials"]
                if item["config_name"] == "repeat_constraints"
            }
            self.assertTrue(trials["constraint_drowning_hierarchy_001"]["success"])
            self.assertFalse(trials["constraint_drowning_hierarchy_002"]["success"])
        finally:
            if os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
