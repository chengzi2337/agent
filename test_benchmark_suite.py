import json
import os
import unittest
import uuid

from benchmarks.runners.run_suite import run_suite


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

            with open(report["paths"]["summary_json"], "r", encoding="utf-8") as file:
                payload = json.load(file)
            self.assertGreater(len(payload["summaries"]), 0)
            config_names = {item["config_name"] for item in payload["summaries"]}
            self.assertIn("vanilla", config_names)
            self.assertIn("cer_full", config_names)
        finally:
            if os.path.isdir(tmpdir):
                import shutil

                shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
