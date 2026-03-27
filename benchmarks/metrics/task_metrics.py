from __future__ import annotations

from statistics import mean
from typing import Dict, List

from benchmarks.schemas import ConfigSummary, TrialEvaluation


def summarize_trials(trials: List[TrialEvaluation]) -> List[ConfigSummary]:
    grouped: Dict[str, List[TrialEvaluation]] = {}
    for trial in trials:
        grouped.setdefault(trial["config_name"], []).append(trial)

    summaries: List[ConfigSummary] = []
    for config_name in sorted(grouped):
        items = grouped[config_name]
        summaries.append(
            {
                "config_name": config_name,
                "task_success_rate": _rate(items, "success"),
                "constraint_compliance_rate": _rate(items, "constraint_compliant"),
                "premature_finish_rate": _rate(items, "premature_finish"),
                "dead_end_repeat_rate": _rate(items, "repeated_dead_end"),
                "unsafe_action_proposal_rate": _rate(items, "unsafe_action_proposed"),
                "unsafe_action_execution_rate": _rate(items, "unsafe_action_executed"),
                "avg_steps_to_success": mean(item["avg_steps_to_success"] for item in items),
                "avg_total_tokens": mean(float(item["total_tokens"]) for item in items),
                "avg_latency_per_step": mean(item["avg_latency_per_step"] for item in items),
                "state_change_efficiency": mean(item["state_change_efficiency"] for item in items),
                "finish_gate_block_count": mean(float(item["finish_gate_block_count"]) for item in items),
                "interceptor_block_count": mean(float(item["interceptor_block_count"]) for item in items),
                "empty_response_rate": _rate(items, "empty_response"),
                "parser_failure_rate": _rate(items, "parser_failure"),
                "max_step_exhaustion_rate": _rate(items, "max_step_exhausted"),
                "runs": len(items),
            }
        )
    return summaries


def _rate(items: List[TrialEvaluation], key: str) -> float:
    if not items:
        return 0.0
    return sum(1 for item in items if bool(item[key])) / len(items)
