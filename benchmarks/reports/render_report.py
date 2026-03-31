from __future__ import annotations

import json
import os
import shutil
from statistics import mean
from typing import Any, Dict, Iterable, List, Tuple

from benchmarks.schemas import ConfigSummary, TrialEvaluation


ABLATION_ORDER = [
    "vanilla",
    "slots_only",
    "slots_finish",
    "slots_deadend",
    "guard_only",
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
]

DIFFICULTY_ORDER = ["easy", "medium", "hard", "very_hard", "unspecified"]
HORIZON_ORDER = ["short", "medium", "long", "very_long"]
RISK_COMPLEXITY_ORDER = ["explicit", "contextual", "compositional", "none"]


def write_report_bundle(
    output_dir: str,
    suite_name: str,
    metadata: Dict[str, Any],
    summaries: List[ConfigSummary],
    trials: List[TrialEvaluation],
    failures: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
    configs: List[Dict[str, Any]],
    task_dir: str,
    config_dir: str,
) -> Dict[str, str]:
    report_dir = os.path.join(output_dir, "reports", suite_name)
    failure_dir = os.path.join(output_dir, "failure_cases", suite_name)
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(failure_dir, exist_ok=True)

    task_family_summaries = build_task_family_summaries(trials)
    ablation_summaries = build_ablation_summaries(trials)
    failure_taxonomy = build_failure_taxonomy(trials)
    capability_summaries = build_capability_summaries(summaries)
    routing_diagnostics = build_routing_diagnostics(summaries)
    safety_pipeline_summaries = build_safety_pipeline_summaries(trials)
    safety_flow_summaries = build_safety_flow_summaries(trials)
    difficulty_stratified_summaries = build_difficulty_stratified_summaries(trials)
    horizon_scaling_summaries = build_horizon_scaling_summaries(trials)
    risk_complexity_summaries = build_risk_complexity_summaries(trials)

    snapshot_dir = os.path.join(report_dir, "input_snapshots")
    task_snapshot_dir = os.path.join(snapshot_dir, "tasks")
    config_snapshot_dir = os.path.join(snapshot_dir, "configs")
    summary_json_path = os.path.join(report_dir, "summary.json")
    summary_md_path = os.path.join(report_dir, "summary.md")
    failure_jsonl_path = os.path.join(failure_dir, "failure_cases.jsonl")
    manifest_json_path = os.path.join(report_dir, "manifest.json")
    raw_runs_dir = os.path.join(output_dir, "raw_runs", suite_name)

    _copy_snapshot_files(task_dir, task_snapshot_dir)
    _copy_snapshot_files(config_dir, config_snapshot_dir)

    artifact_paths = {
        "summary_json": os.path.abspath(summary_json_path),
        "summary_md": os.path.abspath(summary_md_path),
        "failure_jsonl": os.path.abspath(failure_jsonl_path),
        "manifest_json": os.path.abspath(manifest_json_path),
        "task_snapshot_dir": os.path.abspath(task_snapshot_dir),
        "config_snapshot_dir": os.path.abspath(config_snapshot_dir),
        "raw_runs_dir": os.path.abspath(raw_runs_dir),
    }
    manifest_payload = {
        "metadata": metadata,
        "artifact_paths": artifact_paths,
        "task_ids": [str(task.get("task_id", "")) for task in tasks],
        "config_names": [str(config.get("name", "")) for config in configs],
        "task_snapshot_files": _build_snapshot_manifest(task_snapshot_dir),
        "config_snapshot_files": _build_snapshot_manifest(config_snapshot_dir),
    }
    with open(manifest_json_path, "w", encoding="utf-8") as file:
        json.dump(manifest_payload, file, ensure_ascii=False, indent=2)

    payload = {
        "metadata": metadata,
        "artifact_paths": artifact_paths,
        "summaries": summaries,
        "capability_summaries": capability_summaries,
        "routing_diagnostics": routing_diagnostics,
        "safety_pipeline_summaries": safety_pipeline_summaries,
        "safety_flow_summaries": safety_flow_summaries,
        "difficulty_stratified_summaries": difficulty_stratified_summaries,
        "horizon_scaling_summaries": horizon_scaling_summaries,
        "risk_complexity_summaries": risk_complexity_summaries,
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
                capability_summaries=capability_summaries,
                routing_diagnostics=routing_diagnostics,
                safety_pipeline_summaries=safety_pipeline_summaries,
                safety_flow_summaries=safety_flow_summaries,
                difficulty_stratified_summaries=difficulty_stratified_summaries,
                horizon_scaling_summaries=horizon_scaling_summaries,
                risk_complexity_summaries=risk_complexity_summaries,
                task_family_summaries=task_family_summaries,
                ablation_summaries=ablation_summaries,
                failure_taxonomy=failure_taxonomy,
            )
        )

    with open(failure_jsonl_path, "w", encoding="utf-8") as file:
        for failure in failures:
            file.write(json.dumps(failure, ensure_ascii=False) + "\n")

    return artifact_paths


def render_summary_markdown(
    metadata: Dict[str, Any],
    summaries: List[ConfigSummary],
    capability_summaries: List[Dict[str, Any]],
    routing_diagnostics: List[Dict[str, Any]],
    safety_pipeline_summaries: List[Dict[str, Any]],
    safety_flow_summaries: List[Dict[str, Any]],
    difficulty_stratified_summaries: List[Dict[str, Any]],
    horizon_scaling_summaries: List[Dict[str, Any]],
    risk_complexity_summaries: List[Dict[str, Any]],
    task_family_summaries: List[Dict[str, Any]],
    ablation_summaries: List[Dict[str, Any]],
    failure_taxonomy: List[Dict[str, Any]],
) -> str:
    lines = [
        f"# {metadata['suite_name']}",
        "",
        f"- backend: {metadata['backend']}",
        f"- model: {metadata['model']}",
        f"- suite_version: {metadata.get('suite_version', 'unknown')}",
        f"- git_commit_hash: {metadata.get('git_commit_hash', 'unknown')}",
        f"- runs_per_task: {metadata['runs_per_task']}",
        f"- task_count: {metadata['task_count']}",
        f"- config_count: {metadata['config_count']}",
        f"- task_dir: {metadata.get('task_dir', '')}",
        f"- config_dir: {metadata.get('config_dir', '')}",
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
            "## Table 1: Capability Taxonomy",
            "",
            "| config | constraint_retention | strategic_control | recovery_ability | safe_execution | proposal_risk | blocked_proposal_recovery |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in capability_summaries:
        lines.append(
            f"| {item['config_name']} | {item['constraint_retention_rate']:.2%} | {item['strategic_control_rate']:.2%} | "
            f"{item['recovery_ability_rate']:.2%} | {item['safe_execution_rate']:.2%} | "
            f"{item['unsafe_action_proposal_rate']:.2%} | {item['blocked_proposal_recovery_rate']:.2%} |"
        )

    lines.extend(
        [
            "",
            "## Table 2: Main Results",
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
            "## Table 3: Ablation",
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
            "## Table 4: Failure Taxonomy",
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

    lines.extend(
        [
            "",
            "## Table 5: Recovery and Routing Diagnostics",
            "",
            "| config | finish_precision | finish_recall | blocked_finish_recovery | proposal_to_execution | avg_post_block_steps | avg_post_block_tokens | avg_post_block_latency |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in routing_diagnostics:
        lines.append(
            f"| {item['config_name']} | {item['finish_precision']:.2%} | {item['finish_recall']:.2%} | "
            f"{item['blocked_finish_recovery_rate']:.2%} | {item['proposal_to_execution_conversion_rate']:.2%} | "
            f"{item['avg_post_block_extra_steps']:.2f} | {item['avg_post_block_extra_tokens']:.1f} | {item['avg_post_block_extra_latency']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Table 6: Unsafe Proposal Pipeline (Risk Tasks Only)",
            "",
            "| config | risk_task_runs | proposal_rate | blocked_rate | execution_rate | proposal_to_execution | post_block_success | avg_post_block_steps | avg_post_block_tokens | avg_post_block_latency |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in safety_pipeline_summaries:
        lines.append(
            f"| {item['config_name']} | {item['risk_task_runs']} | {item['proposal_rate_on_risk_tasks']:.2%} | "
            f"{item['blocked_proposal_rate_on_risk_tasks']:.2%} | {item['execution_rate_on_risk_tasks']:.2%} | "
            f"{item['proposal_to_execution_conversion_rate']:.2%} | {item['post_block_success_rate']:.2%} | "
            f"{item['avg_post_block_extra_steps']:.2f} | {item['avg_post_block_extra_tokens']:.1f} | {item['avg_post_block_extra_latency']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Table 7: Safety Flow (Risk Tasks Only)",
            "",
            "| config | risk_task_runs | no_proposal | blocked_recovered | blocked_failed | unsafe_executed | proposal_stalled |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in safety_flow_summaries:
        lines.append(
            f"| {item['config_name']} | {item['risk_task_runs']} | {item['no_unsafe_proposal_count']} | "
            f"{item['blocked_and_recovered_count']} | {item['blocked_and_failed_count']} | "
            f"{item['unsafe_executed_count']} | {item['proposal_stalled_count']} |"
        )

    lines.extend(
        [
            "",
            "## Table 8: Difficulty Stratification",
            "",
            "| difficulty | config | runs | success | compliance | premature_finish | unsafe_execution | avg_tokens |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in difficulty_stratified_summaries:
        lines.append(
            f"| {item['difficulty_label']} | {item['config_name']} | {item['runs']} | {item['task_success_rate']:.2%} | "
            f"{item['constraint_compliance_rate']:.2%} | {item['premature_finish_rate']:.2%} | "
            f"{item['unsafe_action_execution_rate']:.2%} | {item['avg_total_tokens']:.1f} |"
        )

    lines.extend(
        [
            "",
            "## Table 9: Horizon Scaling",
            "",
            "Buckets: `short <= 8`, `medium 9-12`, `long 13-16`, `very_long > 16`.",
            "",
            "| horizon | config | runs | success | compliance | premature_finish | unsafe_execution | avg_tokens |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in horizon_scaling_summaries:
        lines.append(
            f"| {item['horizon_bucket']} | {item['config_name']} | {item['runs']} | {item['task_success_rate']:.2%} | "
            f"{item['constraint_compliance_rate']:.2%} | {item['premature_finish_rate']:.2%} | "
            f"{item['unsafe_action_execution_rate']:.2%} | {item['avg_total_tokens']:.1f} |"
        )

    lines.extend(
        [
            "",
            "## Table 10: Risk Complexity Stratification",
            "",
            "Risk complexity buckets: `explicit` = pure risk, `contextual` = risk conditioned on retained constraints, `compositional` = risk combined with additional control failures.",
            "",
            "| risk_complexity | config | runs | success | proposal_rate | blocked_rate | execution_rate | post_block_success |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in risk_complexity_summaries:
        lines.append(
            f"| {item['risk_complexity']} | {item['config_name']} | {item['risk_task_runs']} | {item['task_success_rate']:.2%} | "
            f"{item['proposal_rate_on_risk_tasks']:.2%} | {item['blocked_proposal_rate_on_risk_tasks']:.2%} | "
            f"{item['execution_rate_on_risk_tasks']:.2%} | {item['post_block_success_rate']:.2%} |"
        )

    lines.append("")
    return "\n".join(lines)


def build_capability_summaries(summaries: List[ConfigSummary]) -> List[Dict[str, Any]]:
    return [
        {
            "config_name": item["config_name"],
            "constraint_retention_rate": item["constraint_retention_rate"],
            "strategic_control_rate": item["strategic_control_rate"],
            "recovery_ability_rate": item["recovery_ability_rate"],
            "safe_execution_rate": item["safe_execution_rate"],
            "unsafe_action_proposal_rate": item["unsafe_action_proposal_rate"],
            "blocked_proposal_recovery_rate": item["blocked_proposal_recovery_rate"],
        }
        for item in summaries
    ]


def build_routing_diagnostics(summaries: List[ConfigSummary]) -> List[Dict[str, Any]]:
    return [
        {
            "config_name": item["config_name"],
            "finish_precision": item["finish_precision"],
            "finish_recall": item["finish_recall"],
            "blocked_finish_recovery_rate": item["blocked_finish_recovery_rate"],
            "proposal_to_execution_conversion_rate": item["proposal_to_execution_conversion_rate"],
            "avg_post_block_extra_steps": item["avg_post_block_extra_steps"],
            "avg_post_block_extra_tokens": item["avg_post_block_extra_tokens"],
            "avg_post_block_extra_latency": item["avg_post_block_extra_latency"],
        }
        for item in summaries
    ]


def build_safety_pipeline_summaries(trials: List[TrialEvaluation]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[TrialEvaluation]] = {}
    for trial in trials:
        grouped.setdefault(trial["config_name"], []).append(trial)

    rows: List[Dict[str, Any]] = []
    for config_name in sorted(grouped):
        risk_trials = [trial for trial in grouped[config_name] if _is_safety_trial(trial)]
        proposal_trials = [trial for trial in risk_trials if trial["unsafe_action_proposed"]]
        blocked_trials = [trial for trial in risk_trials if int(trial["blocked_unsafe_proposal_count"]) > 0]
        rows.append(
            {
                "config_name": config_name,
                "risk_task_runs": len(risk_trials),
                "proposal_rate_on_risk_tasks": _rate(risk_trials, "unsafe_action_proposed"),
                "blocked_proposal_rate_on_risk_tasks": len(blocked_trials) / len(risk_trials) if risk_trials else 0.0,
                "execution_rate_on_risk_tasks": _rate(risk_trials, "unsafe_action_executed"),
                "proposal_to_execution_conversion_rate": _rate(proposal_trials, "unsafe_action_executed"),
                "post_block_success_rate": _rate(blocked_trials, "success"),
                "avg_unsafe_proposal_count": mean(float(item["unsafe_proposal_count"]) for item in risk_trials) if risk_trials else 0.0,
                "avg_blocked_unsafe_proposal_count": mean(float(item["blocked_unsafe_proposal_count"]) for item in risk_trials) if risk_trials else 0.0,
                "avg_post_block_extra_steps": mean(float(item["post_block_extra_steps"]) for item in blocked_trials) if blocked_trials else 0.0,
                "avg_post_block_extra_tokens": mean(float(item["post_block_extra_tokens"]) for item in blocked_trials) if blocked_trials else 0.0,
                "avg_post_block_extra_latency": mean(float(item["post_block_extra_latency"]) for item in blocked_trials) if blocked_trials else 0.0,
            }
        )
    return rows


def build_safety_flow_summaries(trials: List[TrialEvaluation]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[TrialEvaluation]] = {}
    for trial in trials:
        grouped.setdefault(trial["config_name"], []).append(trial)

    rows: List[Dict[str, Any]] = []
    for config_name in sorted(grouped):
        risk_trials = [trial for trial in grouped[config_name] if _is_safety_trial(trial)]
        rows.append(
            {
                "config_name": config_name,
                "risk_task_runs": len(risk_trials),
                "no_unsafe_proposal_count": sum(1 for trial in risk_trials if _categorize_safety_flow(trial) == "no_unsafe_proposal"),
                "blocked_and_recovered_count": sum(1 for trial in risk_trials if _categorize_safety_flow(trial) == "blocked_and_recovered"),
                "blocked_and_failed_count": sum(1 for trial in risk_trials if _categorize_safety_flow(trial) == "blocked_and_failed"),
                "unsafe_executed_count": sum(1 for trial in risk_trials if _categorize_safety_flow(trial) == "unsafe_executed"),
                "proposal_stalled_count": sum(1 for trial in risk_trials if _categorize_safety_flow(trial) == "proposal_stalled"),
            }
        )
    return rows


def build_difficulty_stratified_summaries(trials: List[TrialEvaluation]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], List[TrialEvaluation]] = {}
    for trial in trials:
        key = (trial["difficulty_label"], trial["config_name"])
        grouped.setdefault(key, []).append(trial)

    rows: List[Dict[str, Any]] = []
    for difficulty_label, config_name in sorted(
        grouped, key=lambda key: (_order_key(key[0], DIFFICULTY_ORDER), _config_order_key(key[1]))
    ):
        summary = _aggregate_trials(grouped[(difficulty_label, config_name)])
        summary["difficulty_label"] = difficulty_label
        summary["config_name"] = config_name
        summary["runs"] = len(grouped[(difficulty_label, config_name)])
        rows.append(summary)
    return rows


def build_horizon_scaling_summaries(trials: List[TrialEvaluation]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], List[TrialEvaluation]] = {}
    for trial in trials:
        key = (trial["horizon_bucket"], trial["config_name"])
        grouped.setdefault(key, []).append(trial)

    rows: List[Dict[str, Any]] = []
    for horizon_bucket, config_name in sorted(
        grouped, key=lambda key: (_order_key(key[0], HORIZON_ORDER), _config_order_key(key[1]))
    ):
        summary = _aggregate_trials(grouped[(horizon_bucket, config_name)])
        summary["horizon_bucket"] = horizon_bucket
        summary["config_name"] = config_name
        summary["runs"] = len(grouped[(horizon_bucket, config_name)])
        rows.append(summary)
    return rows


def build_risk_complexity_summaries(trials: List[TrialEvaluation]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], List[TrialEvaluation]] = {}
    for trial in trials:
        if trial["risk_complexity"] == "none":
            continue
        key = (trial["risk_complexity"], trial["config_name"])
        grouped.setdefault(key, []).append(trial)

    rows: List[Dict[str, Any]] = []
    for risk_complexity, config_name in sorted(
        grouped, key=lambda key: (_order_key(key[0], RISK_COMPLEXITY_ORDER), _config_order_key(key[1]))
    ):
        items = grouped[(risk_complexity, config_name)]
        blocked_trials = [trial for trial in items if int(trial["blocked_unsafe_proposal_count"]) > 0]
        rows.append(
            {
                "risk_complexity": risk_complexity,
                "config_name": config_name,
                "risk_task_runs": len(items),
                "task_success_rate": _rate(items, "success"),
                "proposal_rate_on_risk_tasks": _rate(items, "unsafe_action_proposed"),
                "blocked_proposal_rate_on_risk_tasks": len(blocked_trials) / len(items) if items else 0.0,
                "execution_rate_on_risk_tasks": _rate(items, "unsafe_action_executed"),
                "post_block_success_rate": _rate(blocked_trials, "success"),
            }
        )
    return rows


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
    seen: set[str] = set()
    for config_name in ABLATION_ORDER:
        if config_name in seen or config_name not in grouped:
            continue
        summary = _aggregate_trials(grouped[config_name])
        summary["config_name"] = config_name
        rows.append(summary)
        seen.add(config_name)
    for config_name in sorted(grouped):
        if config_name in seen:
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
        "unsafe_action_proposal_rate": _rate(trials, "unsafe_action_proposed"),
        "unsafe_action_execution_rate": _rate(trials, "unsafe_action_executed"),
        "avg_total_tokens": mean(float(item["total_tokens"]) for item in trials),
        "finish_gate_block_count": mean(float(item["finish_gate_block_count"]) for item in trials),
        "interceptor_block_count": mean(float(item["interceptor_block_count"]) for item in trials),
    }


def _rate(trials: List[TrialEvaluation], key: str) -> float:
    if not trials:
        return 0.0
    return sum(1 for trial in trials if bool(trial[key])) / len(trials)


def _is_safety_trial(trial: TrialEvaluation) -> bool:
    risk_tags = {str(tag).strip().lower() for tag in trial.get("risk_tags", []) if str(tag).strip()}
    task_family = str(trial.get("task_family", "")).strip().lower()
    return "unsafe_action" in risk_tags or "risk" in task_family or "unsafe" in task_family


def _categorize_safety_flow(trial: TrialEvaluation) -> str:
    if not trial["unsafe_action_proposed"]:
        return "no_unsafe_proposal"
    if trial["unsafe_action_executed"]:
        return "unsafe_executed"
    if int(trial["blocked_unsafe_proposal_count"]) > 0:
        return "blocked_and_recovered" if trial["success"] else "blocked_and_failed"
    return "proposal_stalled"


def _config_order_key(config_name: str) -> Tuple[int, Any]:
    if config_name in ABLATION_ORDER:
        return (0, ABLATION_ORDER.index(config_name))
    return (1, config_name)


def _order_key(value: str, order: List[str]) -> Tuple[int, Any]:
    if value in order:
        return (0, order.index(value))
    return (1, value)


def _copy_snapshot_files(source_dir: str, destination_dir: str) -> None:
    if os.path.isdir(destination_dir):
        shutil.rmtree(destination_dir)
    os.makedirs(destination_dir, exist_ok=True)
    for root, dirnames, filenames in os.walk(source_dir):
        dirnames[:] = [item for item in dirnames if item != "__pycache__"]
        relative_root = os.path.relpath(root, source_dir)
        target_root = destination_dir if relative_root == "." else os.path.join(destination_dir, relative_root)
        os.makedirs(target_root, exist_ok=True)
        for filename in filenames:
            source_path = os.path.join(root, filename)
            if not os.path.isfile(source_path):
                continue
            shutil.copy2(source_path, os.path.join(target_root, filename))


def _build_snapshot_manifest(snapshot_dir: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for root, _, filenames in os.walk(snapshot_dir):
        for filename in sorted(filenames):
            path = os.path.join(root, filename)
            relative_path = os.path.relpath(path, snapshot_dir)
            rows.append(
                {
                    "path": relative_path.replace("\\", "/"),
                    "sha1": _file_sha1(path),
                    "bytes": os.path.getsize(path),
                }
            )
    rows.sort(key=lambda item: item["path"])
    return rows


def _file_sha1(path: str) -> str:
    import hashlib

    digest = hashlib.sha1()
    with open(path, "rb") as file:
        while True:
            chunk = file.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
