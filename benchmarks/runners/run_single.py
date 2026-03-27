from __future__ import annotations

import argparse
import os
import shutil
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from benchmarks.runners.run_suite import run_suite


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single-task CER benchmark suite.")
    parser.add_argument("--task-dir", default=os.path.join("tasks", "mock"))
    parser.add_argument("--config-dir", default=os.path.join("agents", "configs"))
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--backend", choices=["local", "zhipu"], default="local")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--output-dir", default="outputs")
    args = parser.parse_args()

    task_dir = os.path.abspath(str(args.task_dir))
    task_id = str(args.task_id)
    filtered_dir = os.path.join(task_dir, "_single")
    os.makedirs(filtered_dir, exist_ok=True)
    for entry in os.listdir(filtered_dir):
        os.remove(os.path.join(filtered_dir, entry))
    for entry in os.listdir(task_dir):
        if not entry.endswith(".json"):
            continue
        if not entry.startswith(task_id):
            continue
        shutil.copyfile(os.path.join(task_dir, entry), os.path.join(filtered_dir, entry))

    run_suite(
        suite_name=f"single_{task_id}",
        task_dir=filtered_dir,
        config_dir=os.path.abspath(str(args.config_dir)),
        backend=str(args.backend),
        runs=int(args.runs),
        output_dir=os.path.abspath(str(args.output_dir)),
        model="glm-4.6v",
    )


if __name__ == "__main__":
    main()
