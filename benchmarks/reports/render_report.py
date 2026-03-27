from __future__ import annotations

import json
import os
from statistics import mean
from typing import Any, Dict, Iterable, List, Tuple

from benchmarks.schemas import ConfigSummary, TrialEvaluation


ABLATION_ORDER = ["vanilla", "slots_only", "slots_finish", "slots_deadend", "cer_full"]


def write_report_bundle(
    output_dir: str,
    suite_name: str,
    metadata: Dict[str, Any],
    summaries: List[ConfigSummary],
    trials: List[TrialEvaluation],
    failures: List[Dict[str, Any]],
) -> Dict[str, str]:
    report_dir = os.path.join(output_dir, "reports", suite_name)
    failure_dir = os.path.join(output_dir, "failure_cases", suite_name)
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(failure_dir, exist_ok=True)

    task_family_summaries = build_task_family_summaries(trials)
    ablation_summaries = build_ablation_summaries(trials)
    failure_taxonomy = build_failure_taxonomy(trials)

    summary_json_path = os.path.join(report_dir, "summary.json")
    summary_md_path = os.path.join(report_dir, "summary.md")
    failure_jsonl_path = os.path.join(failure_dir, "failure_cases.jsonl")

    payload = {
        "metadata": metadata,
        "summaries": summaries,
        "task_family_summaries": task_family_summaries,
        "ablation_summaries": ablation_summaries,
        "failure_taxonomy": failure_taxonomy,
        "trials": trials,
    }
    with open(summary_json_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    with open(summary_md_path, "w", encoding="utf-8") as file:
        file.write(
            render_summary_markdown(
                metadata=metadata,
                summaries=summaries,
                task_family_summaries=task_family_summaries,
                ablation_summaries=ablation_summaries,
                failure_taxonomy=failure_taxonomy,
            )
        )

    with open(failure_jsonl_path, "w", encoding="utf-8") as file:
        for failure in failures:
            file.write(json.dumps(failure, ensure_ascii=False) + "\n")

    return {
        "summary_json": os.path.abspath(summary_json_path),
        "summary_md": os.path.abspath(summary_md_path),
        "failure_jsonl": os.path.abspath(failure_jsonl_path),
    }


def render_summary_markdown(
    metadata: Dict[str, Any],
    summaries: List[ConfigSummary],
    task_family_summaries: List[Dict[str, Any]],
    ablation_summaries: List[Dict[str, Any]],
    failure_taxonomy: List[Dict[str, Any]],
) -> str:
    lines = [
        f"# {metadata['suite_name']}",
        "",
        f"- backend: {metadata['backend']}",
        f"- model: {metadata['model']}",
        f"- runs_per_task: {metadata['runs_per_task']}",
        f"- task_count: {metadata['task_count']}",
        f"- config_count: {metadata['config_count']}",
        "",
        "## Overall Summary",
        "",
        "| config | success | compliance | premature_finish | dead_end_repeat | unsafe_proposal | unsafe_execution | avg_tokens | avg_latency_step_ms |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in summaries:
        lines.append(
            f"| {item['config_name']} | {item['task_success_rate']:.2%} | {item['constraint_compliance_rate']:.2%} | "
            f"{item['premature_finish_rate']:.2%} | {item['dead_end_repeat_rate']:.2%} | "
            f"{item['unsafe_action_proposal_rate']:.2%} | {item['unsafe_action_execution_rate']:.2%} | "
            f"{item['avg_total_tokens']:.1f} | {item['avg_latency_per_step']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Table 1: Main Results",
            "",
            "| task_family | config | success | compliance | premature_finish | dead_end_repeat | unsafe_execution | avg_tokens |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in task_family_summaries:
        lines.append(
            f"| {item['task_family']} | {item['config_name']} | {item['task_success_rate']:.2%} | "
            f"{item['constraint_compliance_rate']:.2%} | {item['premature_finish_rate']:.2%} | "
            f"{item['dead_end_repeat_rate']:.2%} | {item['unsafe_action_execution_rate']:.2%} | "
            f"{item['avg_total_tokens']:.1f} |"
        )

    lines.extend(
        [
            "",
            "## Table 2: Ablation",
            "",
            "| config | success | compliance | premature_finish | dead_end_repeat | unsafe_execution | avg_tokens | finish_gate_blocks | interceptor_blocks |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in ablation_summaries:
        lines.append(
            f"| {item['config_name']} | {item['task_success_rate']:.2%} | {item['constraint_compliance_rate']:.2%} | "
            f"{item['premature_finish_rate']:.2%} | {item['dead_end_repeat_rate']:.2%} | "
            f"{item['unsafe_action_execution_rate']:.2%} | {item['avg_total_tokens']:.1f} | "
            f"{item['finish_gate_block_count']:.2f} | {item['interceptor_block_count']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Table 3: Failure Taxonomy",
            "",
            "| config | total_failures | constraint_violation | premature_finish | repeated_dead_end | unsafe_execution | other |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in failure_taxonomy:
        lines.append(
            f"| {item['config_name']} | {item['total_failures']} | {item['constraint_violation']} | "
            f"{item['premature_finish']} | {item['repeated_dead_end']} | {item['unsafe_execution']} | {item['other']} |"
        )

    lines.append("")
    return "\n".join(lines)


def build_task_family_summaries(trials: List[TrialEvaluation]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], List[TrialEvaluation]] = {}
    for trial in trials:
        key = (trial["task_family"], trial["config_name"])
        grouped.setdefault(key, []).append(trial)

    rows: List[Dict[str, Any]] = []
    for task_family, config_name in sorted(grouped):
        summary = _aggregate_trials(grouped[(task_family, config_name)])
        summary["task_family"] = task_family
        summary["config_name"] = config_name
        rows.append(summary)
    return rows


def build_ablation_summaries(trials: List[TrialEvaluation]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[TrialEvaluation]] = {}
    for trial in trials:
        grouped.setdefault(trial["config_name"], []).append(trial)

    rows: List[Dict[str, Any]] = []
    for config_name in ABLATION_ORDER:
        if config_name not in grouped:
            continue
        summary = _aggregate_trials(grouped[config_name])
        summary["config_name"] = config_name
        rows.append(summary)
    return rows


def build_failure_taxonomy(trials: List[TrialEvaluation]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[TrialEvaluation]] = {}
    for trial in trials:
        grouped.setdefault(trial["config_name"], []).append(trial)

    rows: List[Dict[str, Any]] = []
    for config_name in sorted(grouped):
        failures = [trial for trial in grouped[config_name] if not trial["success"]]
        total_failures = len(failures)
        rows.append(
            {
                "config_name": config_name,
                "total_failures": total_failures,
                "constraint_violation": _count_reason(failures, "constraint_violation"),
                "premature_finish": _count_reason(failures, "premature_finish"),
                "repeated_dead_end": _count_reason(failures, "repeated_dead_end"),
                "unsafe_execution": _count_reason(failures, "unsafe_execution"),
                "other": total_failures
                - _count_reason(failures, "constraint_violation")
                - _count_reason(failures, "premature_finish")
                - _count_reason(failures, "repeated_dead_end")
                - _count_reason(failures, "unsafe_execution"),
            }
        )
    return rows


def _count_reason(trials: Iterable[TrialEvaluation], reason: str) -> int:
    return sum(1 for trial in trials if trial["termination_reason"] == reason)


def _aggregate_trials(trials: List[TrialEvaluation]) -> Dict[str, Any]:
    return {
        "task_success_rate": _rate(trials, "success"),
        "constraint_compliance_rate": _rate(trials, "constraint_compliant"),
        "premature_finish_rate": _rate(trials, "premature_finish"),
        "dead_end_repeat_rate": _rate(trials, "repeated_dead_end"),
        "unsafe_action_execution_rate": _rate(trials, "unsafe_action_executed"),
        "avg_total_tokens": mean(float(item["total_tokens"]) for item in trials),
        "finish_gate_block_count": mean(float(item["finish_gate_block_count"]) for item in trials),
        "interceptor_block_count": mean(float(item["interceptor_block_count"]) for item in trials),
    }


def _rate(trials: List[TrialEvaluation], key: str) -> float:
    if not trials:
        return 0.0
    return sum(1 for trial in trials if bool(trial[key])) / len(trials)
