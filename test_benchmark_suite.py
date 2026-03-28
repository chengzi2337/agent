import json
import os
import shutil
import unittest
import uuid

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
            self.assertIn("constraint_retention_rate", payload["summaries"][0])
            config_names = {item["config_name"] for item in payload["summaries"]}
            self.assertIn("vanilla", config_names)
            self.assertIn("cer_full", config_names)

            with open(report["paths"]["manifest_json"], "r", encoding="utf-8") as file:
                manifest = json.load(file)
            self.assertGreater(len(manifest["task_snapshot_files"]), 0)
            self.assertGreater(len(manifest["config_snapshot_files"]), 0)
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
