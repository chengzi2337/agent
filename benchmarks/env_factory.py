from __future__ import annotations

from benchmarks.schemas import TaskSpec
from envs.base_env import BaseEnv
from envs.mock.composite_hazard_env import CompositeHazardEnvironment
from envs.mock.constraint_drowning_env import ConstraintDrowningEnvironment
from envs.mock.dead_end_loop_env import DeadEndLoopEnvironment
from envs.mock.premature_finish_env import PrematureFinishEnvironment
from envs.mock.unsafe_action_env import UnsafeActionEnvironment
from envs.web.playwright_env import BenchmarkPlaywrightEnvironment


def build_environment(task: TaskSpec) -> BaseEnv:
    environment_type = str(task.get("environment_type", "mock")).strip().lower()
    environment_name = str(task.get("environment_name", "")).strip().lower()

    if environment_type == "playwright":
        return BenchmarkPlaywrightEnvironment()

    if environment_name == "constraint_drowning":
        return ConstraintDrowningEnvironment()
    if environment_name == "premature_finish":
        return PrematureFinishEnvironment()
    if environment_name == "dead_end_loop":
        return DeadEndLoopEnvironment()
    if environment_name == "unsafe_action":
        return UnsafeActionEnvironment()
    if environment_name == "composite_hazard":
        return CompositeHazardEnvironment()

    raise ValueError(f"Unsupported environment '{environment_name}' for task '{task.get('task_id', '')}'.")
