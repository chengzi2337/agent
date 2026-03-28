from __future__ import annotations

import argparse
import json
import os
from statistics import mean
from typing import Any, Dict, List, Sequence, Tuple


def _format_rate(value: float) -> str:
    return f"{value:.2%}"


def _mean_str(values: Sequence[float]) -> str:
    if not values:
        return "-"
    return f"{mean(values):.1f}"


def _group_trials(trials: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for trial in trials:
        if not isinstance(trial, dict):
            continue
        task_id = str(trial.get("task_id", "")).strip()
        config_name = str(trial.get("config_name", "")).strip()
        if not task_id or not config_name:
            continue
        grouped.setdefault((task_id, config_name), []).append(trial)
    return grouped


def render_external_smoke_markdown(payload: Dict[str, Any]) -> str:
    trials = payload.get("trials", [])
    if not isinstance(trials, list):
        raise ValueError("summary payload is missing a trials list")

    grouped = _group_trials(trials)
    task_ids = sorted({task_id for task_id, _ in grouped})
    config_names = sorted({config_name for _, config_name in grouped})

    lines = [
        "# External Homepage Smoke",
        "",
        "## Table A: Homepage Smoke Results",
        "",
        "| task_id | config | success | blocked_rate | execution_rate | post_block_success | steps | tokens |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for task_id in task_ids:
        for config_name in config_names:
            group = grouped.get((task_id, config_name), [])
            if not group:
                continue
            blocked_runs = [
                item
                for item in group
                if int(item.get("blocked_unsafe_proposal_count", 0) or 0) > 0
                or int(item.get("interceptor_block_count", 0) or 0) > 0
            ]
            blocked_success = [item for item in blocked_runs if bool(item.get("success", False))]
            post_block_success = _format_rate(len(blocked_success) / len(blocked_runs)) if blocked_runs else "-"
            lines.append(
                "| "
                + " | ".join(
                    [
                        task_id,
                        config_name,
                        _format_rate(mean(1.0 if bool(item.get("success", False)) else 0.0 for item in group)),
                        _format_rate(mean(1.0 if item in blocked_runs else 0.0 for item in group)),
                        _format_rate(
                            mean(1.0 if bool(item.get("unsafe_action_executed", False)) else 0.0 for item in group)
                        ),
                        post_block_success,
                        _mean_str([float(item.get("steps", 0) or 0) for item in group]),
                        _mean_str([float(item.get("total_tokens", 0) or 0) for item in group]),
                    ]
                )
                + " |"
            )

    recovery_trials = [
        item
        for item in trials
        if isinstance(item, dict)
        and "recovery_smoke" in {str(tag).strip().lower() for tag in item.get("risk_tags", []) if str(tag).strip()}
    ]
    recovery_grouped = _group_trials(recovery_trials)
    recovery_configs = sorted({config_name for _, config_name in recovery_grouped})

    lines.extend(
        [
            "",
            "## Table B: Recovery Slice",
            "",
            "| config | blocked_count | recovered_success | avg_extra_steps_after_block | avg_extra_tokens_after_block |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    for config_name in recovery_configs:
        rows: List[Dict[str, Any]] = []
        for (task_id, grouped_config), items in recovery_grouped.items():
            if grouped_config != config_name:
                continue
            rows.extend(items)

        blocked_rows = [
            item
            for item in rows
            if int(item.get("blocked_unsafe_proposal_count", 0) or 0) > 0
            or int(item.get("interceptor_block_count", 0) or 0) > 0
        ]
        recovered_success = sum(1 for item in blocked_rows if bool(item.get("success", False)))
        lines.append(
            "| "
            + " | ".join(
                [
                    config_name,
                    str(len(blocked_rows)),
                    str(recovered_success),
                    _mean_str([float(item.get("post_block_extra_steps", 0) or 0) for item in blocked_rows]),
                    _mean_str([float(item.get("post_block_extra_tokens", 0) or 0) for item in blocked_rows]),
                ]
            )
            + " |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render focused markdown tables for the external homepage smoke slice.")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    with open(args.summary_json, "r", encoding="utf-8") as file:
        payload = json.load(file)

    rendered = render_external_smoke_markdown(payload)
    output_md = str(args.output_md).strip()
    if not output_md:
        output_md = os.path.join(os.path.dirname(os.path.abspath(args.summary_json)), "external_smoke_tables.md")

    with open(output_md, "w", encoding="utf-8") as file:
        file.write(rendered)

    print(output_md)


if __name__ == "__main__":
    main()
