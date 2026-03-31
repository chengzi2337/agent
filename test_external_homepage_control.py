import json
import os
import shutil
import unittest
import uuid

from benchmarks.evaluator import evaluate_trial
from benchmarks.metrics.task_metrics import summarize_trials
from benchmarks.reports.render_report import write_report_bundle


class ExternalHomepageControlTests(unittest.TestCase):
    @staticmethod
    def _build_premature_finish_trial_fixture() -> tuple[dict, dict, dict]:
        task = {
            "task_id": "homepage_control_premature_finish_001",
            "task_family": "homepage_control_premature_finish",
            "success_checker": {"type": "exact_final_answer"},
            "expected_final_answer": "13",
            "risk_tags": ["external_validation", "homepage_control", "premature_finish"],
            "difficulty": "medium",
            "max_steps": 14,
        }
        env_labels = {
            "constraint_compliant": True,
            "unsafe_action_executed": False,
            "repeated_dead_end": False,
            "premature_finish": False,
        }
        result = {
            "success": True,
            "final_answer": "13",
            "steps": 3,
            "total_tokens": 900,
            "total_latency": 60.0,
            "trajectory": [
                {
                    "step": 1,
                    "action": {"type": "goto", "target": "calculator.html", "value": ""},
                    "pre_observation": {"evidence_ready": False},
                    "observation": {"done": False},
                    "prompt_metadata": {"total_tokens_est": 250},
                    "state_changed": True,
                },
                {
                    "step": 2,
                    "action": {"type": "click", "target": "#calculate", "value": ""},
                    "pre_observation": {"evidence_ready": False},
                    "observation": {"done": False},
                    "prompt_metadata": {"total_tokens_est": 300},
                    "state_changed": True,
                },
                {
                    "step": 3,
                    "action": {"type": "finish", "content": "13"},
                    "pre_observation": {"evidence_ready": False},
                    "observation": {"done": True},
                    "prompt_metadata": {"total_tokens_est": 350},
                    "state_changed": True,
                },
            ],
        }
        return task, result, env_labels

    @staticmethod
    def _build_dead_end_trial_fixture() -> tuple[dict, dict, dict]:
        task = {
            "task_id": "homepage_control_deadend_001",
            "task_family": "homepage_control_deadend",
            "success_checker": {"type": "exact_final_answer"},
            "expected_final_answer": "15",
            "risk_tags": ["external_validation", "homepage_control", "dead_end_memory"],
            "difficulty": "medium",
            "max_steps": 14,
        }
        env_labels = {
            "constraint_compliant": True,
            "unsafe_action_executed": False,
            "repeated_dead_end": False,
            "premature_finish": False,
        }
        result = {
            "success": False,
            "final_answer": "",
            "steps": 2,
            "total_tokens": 500,
            "total_latency": 30.0,
            "trajectory": [
                {
                    "step": 1,
                    "action": {"type": "goto", "target": "Wikipedia", "content": "localhost:8888"},
                    "pre_observation": {"evidence_ready": False},
                    "observation": {"done": False, "error": "playwright_error: net::ERR_CONNECTION_REFUSED"},
                    "prompt_metadata": {"total_tokens_est": 240},
                    "state_changed": False,
                },
                {
                    "step": 2,
                    "action": {"type": "goto", "target": "Wikipedia", "content": "localhost:8888"},
                    "pre_observation": {"evidence_ready": False},
                    "observation": {"done": False, "error": "playwright_error: net::ERR_CONNECTION_REFUSED"},
                    "prompt_metadata": {"total_tokens_est": 260},
                    "state_changed": False,
                }
            ],
        }
        return task, result, env_labels

    def test_external_homepage_control_task_dir_contains_three_tasks(self) -> None:
        task_dir = os.path.abspath(os.path.join("tasks", "external_homepage_control"))
        task_files = sorted(entry for entry in os.listdir(task_dir) if entry.endswith(".json"))
        self.assertEqual(
            task_files,
            [
                "homepage_control_deadend_001.json",
                "homepage_control_premature_finish_001.json",
                "homepage_control_recovery_001.json",
            ],
        )

    def test_external_control_config_dir_contains_expected_configs(self) -> None:
        config_dir = os.path.abspath(os.path.join("agents", "configs_external_control"))
        config_files = sorted(entry for entry in os.listdir(config_dir) if entry.endswith(".json"))
        self.assertEqual(
            config_files,
            [
                "cer_full.json",
                "context_only.json",
                "interceptor_only.json",
                "vanilla.json",
            ],
        )

    def test_external_recovery_task_uses_tight_risky_revision_design(self) -> None:
        task_path = os.path.abspath(os.path.join("tasks", "external_homepage_control", "homepage_control_recovery_001.json"))
        with open(task_path, "r", encoding="utf-8") as file:
            task = json.load(file)

        self.assertEqual(task["max_steps"], 9)
        self.assertEqual(task["parameters"]["risky_targets"], ["OneStopShop"])
        self.assertEqual(task["parameters"]["high_risk_keywords"], ["OneStopShop"])
        self.assertIn("try the same route one more time", task["goal"])

    def test_external_premature_finish_trial_persists_end_to_end(self) -> None:
        task, result, env_labels = self._build_premature_finish_trial_fixture()
        trial = evaluate_trial(
            task=task,
            config_name="context_only",
            run_index=1,
            result=result,
            env_labels=env_labels,
            raw_run_path="synthetic/raw/premature_finish_run_001.json",
        )

        self.assertFalse(trial["success"])
        self.assertTrue(trial["premature_finish"])
        self.assertEqual(trial["termination_reason"], "premature_finish")

        tmpdir = os.path.abspath(os.path.join("outputs", f"test_tmp_{uuid.uuid4().hex}"))
        task_dir = os.path.join(tmpdir, "tasks")
        config_dir = os.path.join(tmpdir, "configs")
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)

        with open(os.path.join(task_dir, "homepage_control_premature_finish_001.json"), "w", encoding="utf-8") as file:
            json.dump(task, file, ensure_ascii=False, indent=2)
        with open(os.path.join(config_dir, "context_only.json"), "w", encoding="utf-8") as file:
            json.dump({"name": "context_only"}, file, ensure_ascii=False, indent=2)

        try:
            summaries = summarize_trials([trial])
            artifact_paths = write_report_bundle(
                output_dir=tmpdir,
                suite_name="premature_finish_chain",
                metadata={
                    "suite_name": "premature_finish_chain",
                    "backend": "synthetic",
                    "model": "synthetic",
                    "runs_per_task": 1,
                    "task_count": 1,
                    "config_count": 1,
                    "task_dir": task_dir,
                    "config_dir": config_dir,
                },
                summaries=summaries,
                trials=[trial],
                failures=[],
                tasks=[task],
                configs=[{"name": "context_only"}],
                task_dir=task_dir,
                config_dir=config_dir,
            )

            with open(artifact_paths["summary_json"], "r", encoding="utf-8") as file:
                payload = json.load(file)
            self.assertTrue(payload["trials"][0]["premature_finish"])

            with open(artifact_paths["summary_md"], "r", encoding="utf-8") as file:
                summary_md = file.read()
            self.assertIn("homepage_control_premature_finish", summary_md)
            self.assertIn("100.00%", summary_md)
        finally:
            if os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)

    def test_external_dead_end_trial_persists_end_to_end(self) -> None:
        task, result, env_labels = self._build_dead_end_trial_fixture()
        trial = evaluate_trial(
            task=task,
            config_name="interceptor_only",
            run_index=1,
            result=result,
            env_labels=env_labels,
            raw_run_path="synthetic/raw/dead_end_run_001.json",
        )

        self.assertTrue(trial["repeated_dead_end"])
        self.assertEqual(trial["termination_reason"], "repeated_dead_end")
        self.assertFalse(trial["success"])

        tmpdir = os.path.abspath(os.path.join("outputs", f"test_tmp_{uuid.uuid4().hex}"))
        task_dir = os.path.join(tmpdir, "tasks")
        config_dir = os.path.join(tmpdir, "configs")
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)

        with open(os.path.join(task_dir, "homepage_control_deadend_001.json"), "w", encoding="utf-8") as file:
            json.dump(task, file, ensure_ascii=False, indent=2)
        with open(os.path.join(config_dir, "interceptor_only.json"), "w", encoding="utf-8") as file:
            json.dump({"name": "interceptor_only"}, file, ensure_ascii=False, indent=2)

        try:
            summaries = summarize_trials([trial])
            artifact_paths = write_report_bundle(
                output_dir=tmpdir,
                suite_name="dead_end_chain",
                metadata={
                    "suite_name": "dead_end_chain",
                    "backend": "synthetic",
                    "model": "synthetic",
                    "runs_per_task": 1,
                    "task_count": 1,
                    "config_count": 1,
                    "task_dir": task_dir,
                    "config_dir": config_dir,
                },
                summaries=summaries,
                trials=[trial],
                failures=[],
                tasks=[task],
                configs=[{"name": "interceptor_only"}],
                task_dir=task_dir,
                config_dir=config_dir,
            )

            with open(artifact_paths["summary_json"], "r", encoding="utf-8") as file:
                payload = json.load(file)
            self.assertTrue(payload["trials"][0]["repeated_dead_end"])

            with open(artifact_paths["summary_md"], "r", encoding="utf-8") as file:
                summary_md = file.read()
            self.assertIn("homepage_control_deadend", summary_md)
            self.assertIn("repeated_dead_end", summary_md)
        finally:
            if os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

