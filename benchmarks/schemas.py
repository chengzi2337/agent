from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict


EnvironmentType = Literal["mock", "playwright"]


class SuccessCheckerSpec(TypedDict, total=False):
    type: str
    route: str
    keywords: List[str]


class TaskSpec(TypedDict, total=False):
    task_id: str
    task_family: str
    goal: str
    global_constraints: List[str]
    environment_type: EnvironmentType
    environment_name: str
    start_state: Dict[str, Any]
    success_checker: SuccessCheckerSpec
    risk_tags: List[str]
    max_steps: int
    difficulty: str
    expected_final_answer: str
    notes: str
    parameters: Dict[str, Any]


class AgentConfigSpec(TypedDict, total=False):
    name: str
    description: str
    use_isolation: bool
    repeat_constraints_each_step: bool
    history_mode: str
    action_history_limit: int
    enable_dead_end_memory: bool
    enable_finish_gate: bool
    enable_static_interceptor: bool


class TrialEvaluation(TypedDict):
    task_id: str
    task_family: str
    config_name: str
    run_index: int
    success: bool
    constraint_compliant: bool
    premature_finish: bool
    repeated_dead_end: bool
    unsafe_action_proposed: bool
    unsafe_action_executed: bool
    steps: int
    avg_latency_per_step: float
    total_tokens: int
    total_latency: float
    avg_steps_to_success: float
    state_change_efficiency: float
    finish_gate_block_count: int
    interceptor_block_count: int
    parser_failure: bool
    empty_response: bool
    max_step_exhausted: bool
    termination_reason: str
    final_answer: str
    risk_tags: List[str]
    raw_run_path: str


class ConfigSummary(TypedDict):
    config_name: str
    task_success_rate: float
    constraint_compliance_rate: float
    premature_finish_rate: float
    dead_end_repeat_rate: float
    unsafe_action_proposal_rate: float
    unsafe_action_execution_rate: float
    avg_steps_to_success: float
    avg_total_tokens: float
    avg_latency_per_step: float
    state_change_efficiency: float
    finish_gate_block_count: float
    interceptor_block_count: float
    empty_response_rate: float
    parser_failure_rate: float
    max_step_exhaustion_rate: float
    runs: int
