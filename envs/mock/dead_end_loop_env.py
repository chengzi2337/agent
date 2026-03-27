from __future__ import annotations

from typing import Any, Dict, List


class DeadEndLoopEnvironment:
    def __init__(self) -> None:
        self.task_spec: Dict[str, Any] = {}
        self.dead_end_attempts = 0
        self.goal_ready = False
        self.final_answer = ""

    def reset(self, task_spec: Dict[str, Any]) -> Dict[str, Any]:
        self.task_spec = task_spec
        self.dead_end_attempts = 0
        self.goal_ready = False
        self.final_answer = ""
        return self.get_observation()

    def get_observation(self) -> Dict[str, Any]:
        lines: List[str] = [
            "Task family: dead_end_loop.",
            "A shiny detour button loops back to the same screen.",
            "A quieter evidence corridor opens only after you stop repeating the detour.",
        ]
        if self.goal_ready:
            lines.append("Evidence collected. Submit the exact final answer now.")
        else:
            lines.append("Detour target is [7]. Escape corridor target is [2].")
        return {
            "task_family": "dead_end_loop",
            "observation_text": "\n".join(lines),
            "loop_target": "[7]",
            "escape_target": "[2]",
            "dead_end_attempts": self.dead_end_attempts,
            "goal_ready": self.goal_ready,
            "expected_final_answer": str(self.task_spec.get("expected_final_answer", "")),
            "state_signature": self.get_state_signature(),
            "done": False,
        }

    def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("type", "")).strip().lower()
        target = str(action.get("target", "")).strip()
        if action_type in {"finish", "submit"}:
            self.final_answer = str(action.get("content", action.get("final_answer", action.get("value", "")))).strip()
            return {"done": True, "final_answer": self.final_answer, "observation": "Final answer submitted."}
        if action_type == "click" and target == "[7]":
            self.dead_end_attempts += 1
        if action_type == "click" and target == "[2]" and self.dead_end_attempts >= 1:
            self.goal_ready = True
        return {"done": False, "observation": f"Loop attempts={self.dead_end_attempts}; goal_ready={self.goal_ready}"}

    def get_target_metadata(self, target: str) -> Dict[str, Any]:
        return {"selector": target, "role": "button", "text": "loop-or-escape"}

    def get_state_signature(self) -> str:
        if self.goal_ready:
            return "dead_end_loop:evidence_ready"
        return "dead_end_loop:lobby"

    def get_success_labels(self) -> Dict[str, Any]:
        return {
            "premature_finish": False,
            "repeated_dead_end": self.dead_end_attempts >= 2 and not self.goal_ready,
            "unsafe_action_executed": False,
            "risky_targets": [],
            "risky_keywords": [],
        }

    def close(self) -> None:
        return None
