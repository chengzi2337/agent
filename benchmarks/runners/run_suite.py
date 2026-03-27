from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List

if __package__ in {None, ""}:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from benchmarks.agent_factory import build_agent
from benchmarks.config_loader import load_agent_configs
from benchmarks.env_factory import build_environment
from benchmarks.evaluator import apply_success_checker, evaluate_trial
from benchmarks.metrics.task_metrics import summarize_trials
from benchmarks.reports.render_report import write_report_bundle
from benchmarks.schemas import AgentConfigSpec, TaskSpec, TrialEvaluation
from benchmarks.task_loader import load_task_specs


DEFAULT_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_MODEL = "glm-4.6v"
DEFAULT_SECURITY_POLICY: Dict[str, Any] = {
    "allowed_domains": ["baidu.com", "reddit.com"],
    "high_risk_keywords": ["rm -rf", "drop table", "delete", "advertisement", "ad"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CER benchmark suites from task specs and config specs.")
    parser.add_argument("--backend", choices=["local", "zhipu"], default=os.getenv("CER_BENCHMARK_BACKEND", "local"))
    parser.add_argument("--task-dir", default=os.path.join("tasks", "mock"))
    parser.add_argument("--config-dir", default=os.path.join("agents", "configs"))
    parser.add_argument("--suite-name", default=os.getenv("CER_BENCHMARK_SUITE_NAME", "mock_controlled_suite"))
    parser.add_argument("--runs", type=int, default=int(os.getenv("CER_BENCHMARK_RUNS", "5")))
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--api-url", default=os.getenv("ZHIPU_API_URL", DEFAULT_API_URL))
    parser.add_argument("--api-key", default=os.getenv("ZHIPU_API_KEY", ""))
    parser.add_argument("--model", default=os.getenv("ZHIPU_MODEL", DEFAULT_MODEL))
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--report-json", default="")
    parser.add_argument("--failure-tail-steps", type=int, default=int(os.getenv("CER_BENCHMARK_FAILURE_TAIL_STEPS", "5")))
    return parser.parse_args()


def run_suite(
    suite_name: str,
    task_dir: str,
    config_dir: str,
    backend: str,
    runs: int,
    output_dir: str,
    model: str,
    api_url: str = "",
    api_key: str = "",
    max_steps_override: int = 0,
    failure_tail_steps: int = 3,
) -> Dict[str, Any]:
    tasks = load_task_specs(task_dir)
    configs = load_agent_configs(config_dir)
    all_trials: List[TrialEvaluation] = []
    failure_cases: List[Dict[str, Any]] = []

    for task in tasks:
        for config in configs:
            for run_index in range(1, runs + 1):
                env = build_environment(task)
                env.reset(task)
                effective_max_steps = int(max_steps_override or int(task.get("max_steps", 15)))
                agent = build_agent(
                    backend=backend,
                    config=config,
                    environment=env,
                    max_steps=effective_max_steps,
                    api_url=api_url,
                    api_key=api_key,
                    model=model,
                    security_policy=DEFAULT_SECURITY_POLICY,
                )
                raw_result = agent.run_task(
                    task_goal=str(task.get("goal", "")).strip(),
                    global_constraints="\n".join(task.get("global_constraints", [])),
                    use_isolation=bool(config.get("use_isolation", True)),
                )
                env_labels = dict(env.get_success_labels())
                checker_success, env_labels = apply_success_checker(task, raw_result, env_labels)
                raw_result["success"] = checker_success
                raw_run_path = _write_raw_run(output_dir, suite_name, config, task, run_index, raw_result, env_labels)
                evaluation = evaluate_trial(
                    task=task,
                    config_name=str(config.get("name", "")),
                    run_index=run_index,
                    result=raw_result,
                    env_labels=env_labels,
                    raw_run_path=raw_run_path,
                )
                all_trials.append(evaluation)
                if (not evaluation["success"]) or (not evaluation["constraint_compliant"]):
                    failure_cases.append(
                        _build_failure_case(
                            task=task,
                            config=config,
                            evaluation=evaluation,
                            raw_result=raw_result,
                            failure_tail_steps=failure_tail_steps,
                        )
                    )
                env.close()

    summaries = summarize_trials(all_trials)
    metadata = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "suite_name": suite_name,
        "suite_version": _compute_suite_version(tasks, configs),
        "git_commit_hash": _get_git_commit_hash(),
        "backend": backend,
        "model": model,
        "runs_per_task": runs,
        "task_count": len(tasks),
        "config_count": len(configs),
        "task_dir": os.path.abspath(task_dir),
        "config_dir": os.path.abspath(config_dir),
    }
    bundle_paths = write_report_bundle(
        output_dir=output_dir,
        suite_name=suite_name,
        metadata=metadata,
        summaries=summaries,
        trials=all_trials,
        failures=failure_cases,
        tasks=tasks,
        configs=configs,
        task_dir=os.path.abspath(task_dir),
        config_dir=os.path.abspath(config_dir),
    )
    return {
        "metadata": metadata,
        "summaries": summaries,
        "paths": bundle_paths,
    }


def _compute_suite_version(tasks: List[TaskSpec], configs: List[AgentConfigSpec]) -> str:
    payload = {
        "tasks": sorted(tasks, key=lambda item: str(item.get("task_id", ""))),
        "configs": sorted(configs, key=lambda item: str(item.get("name", ""))),
    }
    digest_source = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    return hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:12]


def _get_git_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main() -> None:
    args = parse_args()
    if args.runs <= 0:
        raise ValueError("--runs must be positive.")
    if args.backend == "zhipu" and not str(args.api_key).strip():
        raise ValueError("Zhipu backend requires --api-key or ZHIPU_API_KEY.")

    report = run_suite(
        suite_name=str(args.suite_name),
        task_dir=os.path.abspath(str(args.task_dir)),
        config_dir=os.path.abspath(str(args.config_dir)),
        backend=str(args.backend),
        runs=int(args.runs),
        output_dir=os.path.abspath(str(args.output_dir)),
        model=str(args.model),
        api_url=str(args.api_url),
        api_key=str(args.api_key),
        max_steps_override=int(args.max_steps),
        failure_tail_steps=int(args.failure_tail_steps),
    )
    report_json = str(args.report_json).strip()
    if report_json:
        with open(report_json, "w", encoding="utf-8") as file:
            json.dump(report, file, ensure_ascii=False, indent=2)

    print(f"# {report['metadata']['suite_name']}")
    print(f"Backend: {report['metadata']['backend']}")
    print(f"Model: {report['metadata']['model']}")
    print("| Config | Success | Compliance | Premature Finish | Dead-end Repeat | Unsafe Proposal | Unsafe Execution |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for item in report["summaries"]:
        print(
            f"| {item['config_name']} | {item['task_success_rate']:.1%} | {item['constraint_compliance_rate']:.1%} | "
            f"{item['premature_finish_rate']:.1%} | {item['dead_end_repeat_rate']:.1%} | "
            f"{item['unsafe_action_proposal_rate']:.1%} | {item['unsafe_action_execution_rate']:.1%} |"
        )
    print(f"Summary JSON: {report['paths']['summary_json']}")
    print(f"Summary MD: {report['paths']['summary_md']}")
    print(f"Failure JSONL: {report['paths']['failure_jsonl']}")


def _write_raw_run(
    output_dir: str,
    suite_name: str,
    config: AgentConfigSpec,
    task: TaskSpec,
    run_index: int,
    raw_result: Dict[str, Any],
    env_labels: Dict[str, Any],
) -> str:
    raw_dir = os.path.join(
        output_dir,
        "raw_runs",
        suite_name,
        str(config.get("name", "")),
        str(task.get("task_id", "")),
    )
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"run_{run_index:03d}.json")
    with open(raw_path, "w", encoding="utf-8") as file:
        json.dump(
            {
                "task": task,
                "config": config,
                "env_labels": env_labels,
                "result": raw_result,
            },
            file,
            ensure_ascii=False,
            indent=2,
        )
    return os.path.abspath(raw_path)


def _build_failure_case(
    task: TaskSpec,
    config: AgentConfigSpec,
    evaluation: TrialEvaluation,
    raw_result: Dict[str, Any],
    failure_tail_steps: int,
) -> Dict[str, Any]:
    trajectory = raw_result.get("trajectory", [])
    if not isinstance(trajectory, list):
        trajectory = []
    tail_steps = [item for item in trajectory if isinstance(item, dict) and "step" in item][-failure_tail_steps:]
    terminal_event = None
    if trajectory and isinstance(trajectory[-1], dict) and "step" not in trajectory[-1]:
        terminal_event = trajectory[-1]
    return {
        "task_id": task.get("task_id", ""),
        "task_family": task.get("task_family", ""),
        "config_name": config.get("name", ""),
        "run_index": evaluation["run_index"],
        "termination_reason": evaluation["termination_reason"],
        "final_answer": evaluation["final_answer"],
        "last_k_steps": tail_steps,
        "terminal_event": terminal_event,
        "state_signature_trail": [
            {
                "before": item.get("state_signature_before", ""),
                "after": item.get("state_signature_after", ""),
                "state_changed": item.get("state_changed", False),
            }
            for item in tail_steps
            if isinstance(item, dict)
        ],
        "raw_run_path": evaluation["raw_run_path"],
    }


if __name__ == "__main__":
    main()
