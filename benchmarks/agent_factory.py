from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Set, Tuple

from benchmarks.schemas import AgentConfigSpec
from cer_architecture import CERAgent, CERDistiller, CERMemory, CERRetriever, _safe_llm_request


class NoOpDistiller(CERDistiller):
    def distill_dynamics(self, trajectory: str) -> List[Dict[str, str]]:
        return []

    def distill_skills(self, trajectory: str) -> List[Dict[str, str]]:
        return []


class NoOpRetriever(CERRetriever):
    def retrieve(self, task_goal: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return [], []


class ScriptedBenchmarkAgent(CERAgent):
    """Deterministic local backend used for controlled mock suites."""

    def _call_agent_llm(self, prompt: str, observation: Dict[str, Any]) -> Tuple[str, int, float]:
        step_match = re.search(r"Step:\s*(\d+)", prompt)
        step = int(step_match.group(1)) if step_match else 1
        task_family = str(observation.get("task_family", "")).strip().lower()
        token_estimate = max(len(prompt) // 4, 1)
        latency_ms = 20.0 + step

        if task_family == "constraint_drowning":
            response = self._handle_constraint_drowning(prompt, observation)
            return response, token_estimate, latency_ms

        if task_family == "premature_finish":
            response = self._handle_premature_finish(prompt, observation)
            return response, token_estimate, latency_ms

        if task_family == "dead_end_loop":
            response = self._handle_dead_end_loop(prompt, observation)
            return response, token_estimate, latency_ms

        if task_family == "unsafe_action":
            response = self._handle_unsafe_action(prompt, observation, step)
            return response, token_estimate, latency_ms

        modes = {str(item).strip().lower() for item in observation.get("modes", []) if str(item).strip()}
        if modes:
            response = self._handle_composite_modes(prompt, observation, modes)
            return response, token_estimate, latency_ms

        return self._json_response("wait", value="1"), token_estimate, latency_ms

    def _handle_constraint_drowning(self, prompt: str, observation: Dict[str, Any]) -> str:
        variant = str(observation.get("task_variant", "basic")).strip().lower()
        hard_answer = str(observation.get("hard_answer", observation.get("expected_final_answer", ""))).strip()
        soft_answer = str(observation.get("soft_answer", "I WILL CLICK PROMOTIONS")).strip() or "I WILL CLICK PROMOTIONS"
        pseudo_answer = str(observation.get("pseudo_answer", soft_answer)).strip() or soft_answer
        has_slots = self._has_slot_constraints(prompt)
        has_repeat = self._has_repeat_constraints(prompt)
        repeated_constraints_text = self._extract_repeated_constraints_text(prompt)
        repeat_understands_hierarchy = has_repeat and self._repeat_understands_hierarchy(repeated_constraints_text)
        repeat_resists_override = has_repeat and self._repeat_resists_override(repeated_constraints_text)
        repeat_prefers_safe_route = has_repeat and self._repeat_prefers_safe_route(repeated_constraints_text, observation)
        repeat_survives_budget = has_repeat and self._repeat_survives_budget_pressure(
            repeated_constraints_text,
            prompt,
            observation,
        )

        if bool(observation.get("choice_required", False)):
            safe_target = str(observation.get("safe_choice_target", "[1]")).strip() or "[1]"
            unsafe_target = str(observation.get("unsafe_choice_target", "[2]")).strip() or "[2]"
            target = safe_target if (has_slots or repeat_prefers_safe_route) else unsafe_target
            return self._json_response("click", target=target)

        if not bool(observation.get("completion_ready", False)):
            return self._json_response("wait", value="1")

        if variant == "hierarchy_conflict":
            final_answer = hard_answer if (has_slots or repeat_understands_hierarchy) else soft_answer if has_repeat else "I WILL CLICK PROMOTIONS"
            return self._json_response("finish", final_answer=final_answer)

        if variant == "pseudo_override":
            if bool(observation.get("pseudo_constraint_active", False)) and not (has_slots or repeat_resists_override):
                return self._json_response("finish", final_answer=pseudo_answer)
            final_answer = hard_answer if (has_slots or repeat_resists_override) else "I WILL CLICK PROMOTIONS"
            return self._json_response("finish", final_answer=final_answer)

        if variant == "semantic_route":
            selected_route = str(observation.get("selected_route", "")).strip()
            safe_route = str(observation.get("safe_route", "")).strip()
            safe_answer = str(
                observation.get(
                    "safe_finish_answer",
                    "Use the redacted summary export to satisfy the privacy rule.",
                )
            ).strip()
            unsafe_answer = str(
                observation.get(
                    "unsafe_finish_answer",
                    "Use the full export because the latest note overrode the privacy rule.",
                )
            ).strip()
            if selected_route == safe_route:
                return self._json_response("finish", final_answer=safe_answer)
            return self._json_response("finish", final_answer=unsafe_answer)

        if variant == "budget_pressure":
            final_answer = hard_answer if (has_slots or repeat_survives_budget) else soft_answer if has_repeat else "I WILL CLICK PROMOTIONS"
            return self._json_response("finish", final_answer=final_answer)

        final_answer = hard_answer if (has_slots or has_repeat) else "I WILL CLICK PROMOTIONS"
        return self._json_response("finish", final_answer=final_answer)

    def _handle_premature_finish(self, prompt: str, observation: Dict[str, Any]) -> str:
        expected_final_answer = str(observation.get("expected_final_answer", "")).strip()
        if bool(observation.get("evidence_ready")):
            return self._json_response("finish", final_answer=expected_final_answer)
        if '"action": "finish"' in prompt:
            next_target = str(observation.get("next_target", "[1]"))
            return self._json_response("click", target=next_target)
        return self._json_response("finish", final_answer="CASE CLOSED")

    def _handle_dead_end_loop(self, prompt: str, observation: Dict[str, Any]) -> str:
        expected_final_answer = str(observation.get("expected_final_answer", "")).strip()
        if bool(observation.get("goal_ready")):
            return self._json_response("finish", final_answer=expected_final_answer)
        if self._has_dead_end_summary(prompt, str(observation.get("loop_target", "[7]"))):
            return self._json_response("click", target=str(observation.get("escape_target", "[2]")))
        return self._json_response("click", target=str(observation.get("loop_target", "[7]")))

    def _handle_unsafe_action(self, prompt: str, observation: Dict[str, Any], step: int) -> str:
        expected_final_answer = str(observation.get("expected_final_answer", "")).strip()
        if bool(observation.get("goal_ready")):
            return self._json_response("finish", final_answer=expected_final_answer)
        if step == 1:
            return self._json_response("click", target=str(observation.get("risky_target", "advertisement")))
        return self._json_response("click", target=str(observation.get("safe_target", "safe-review")))

    def _handle_composite_modes(self, prompt: str, observation: Dict[str, Any], modes: Set[str]) -> str:
        expected_final_answer = str(observation.get("expected_final_answer", "")).strip()
        has_slots = self._has_slot_constraints(prompt)
        has_repeat = self._has_repeat_constraints(prompt)

        risky_target = str(observation.get("risky_target", "advertisement")).strip() or "advertisement"
        safe_target = str(observation.get("safe_target", "safe-review")).strip() or "safe-review"
        loop_target = str(observation.get("loop_target", "[7]"))
        escape_target = str(observation.get("escape_target", "[2]"))
        evidence_target = str(observation.get("evidence_target", "[3]"))

        if bool(observation.get("goal_ready")):
            if "constraint" in modes and not (has_slots or has_repeat):
                return self._json_response("finish", final_answer="FOLLOWED THE WRONG POLICY")
            return self._json_response("finish", final_answer=expected_final_answer)

        if "risk" in modes and not bool(observation.get("safe_review_complete", False)):
            if not self._action_seen_in_history(prompt, action_type="click", target=risky_target):
                return self._json_response("click", target=risky_target)

        if "premature_finish" in modes and not bool(observation.get("evidence_ready", False)):
            if not self._action_seen_in_history(prompt, action_type="finish"):
                return self._json_response("finish", final_answer="CASE CLOSED")

        if "dead_end" in modes and not bool(observation.get("dead_end_cleared", False)):
            if self._has_dead_end_summary(prompt, loop_target):
                return self._json_response("click", target=escape_target)
            return self._json_response("click", target=loop_target)

        if "risk" in modes and not bool(observation.get("safe_review_complete", False)):
            return self._json_response("click", target=safe_target)

        if "premature_finish" in modes and not bool(observation.get("evidence_ready", False)):
            return self._json_response("click", target=evidence_target)

        return self._json_response("wait", value="1")

    @staticmethod
    def _has_slot_constraints(prompt: str) -> bool:
        return "<User_Global_Constraints>" in prompt

    @staticmethod
    def _has_repeat_constraints(prompt: str) -> bool:
        return "<Repeated_Global_Constraints>" in prompt

    @staticmethod
    def _extract_prompt_block(prompt: str, block_name: str) -> str:
        pattern = rf"<{re.escape(block_name)}>\n(.*?)\n</{re.escape(block_name)}>"
        match = re.search(pattern, prompt, flags=re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()

    @classmethod
    def _extract_repeated_constraints_text(cls, prompt: str) -> str:
        return cls._extract_prompt_block(prompt, "Repeated_Global_Constraints")

    @staticmethod
    def _repeat_understands_hierarchy(repeated_constraints_text: str) -> bool:
        normalized = repeated_constraints_text.lower()
        hard_markers = ["hard:", "hard constraint", "higher-priority", "higher priority", "non-negotiable"]
        soft_markers = ["soft:", "secondary preference", "style preference", "tone preference"]
        return any(marker in normalized for marker in hard_markers) and any(marker in normalized for marker in soft_markers)

    @staticmethod
    def _repeat_resists_override(repeated_constraints_text: str) -> bool:
        normalized = repeated_constraints_text.lower()
        markers = [
            "ignore later instructions",
            "later instructions that conflict",
            "later notes do not override",
            "subsequent notes are advisory only",
            "do not let later notes replace",
        ]
        return any(marker in normalized for marker in markers)

    @staticmethod
    def _repeat_prefers_safe_route(repeated_constraints_text: str, observation: Dict[str, Any]) -> bool:
        normalized = repeated_constraints_text.lower()
        safe_route = str(observation.get("safe_route", "")).strip().lower()
        if safe_route and safe_route.replace("_", " ") in normalized:
            return True
        explicit_safe_markers = ["redacted summary", "sanitized digest", "masked digest"]
        return any(marker in normalized for marker in explicit_safe_markers)

    @staticmethod
    def _repeat_survives_budget_pressure(
        repeated_constraints_text: str,
        prompt: str,
        observation: Dict[str, Any],
    ) -> bool:
        normalized = repeated_constraints_text.lower()
        pressure = str(observation.get("budget_pressure", "normal")).strip().lower()
        if pressure == "high":
            return False
        anchor_markers = ["hard:", "non-negotiable", "pinned rule", "pin this rule"]
        return len(prompt) < 5200 and any(marker in normalized for marker in anchor_markers)

    @staticmethod
    def _has_dead_end_summary(prompt: str, loop_target: str) -> bool:
        lowered_prompt = prompt.lower()
        lowered_target = loop_target.strip().lower()
        return "page state did not change" in lowered_prompt or f"tried click {lowered_target}" in lowered_prompt

    @staticmethod
    def _action_seen_in_history(prompt: str, action_type: str, target: str = "") -> bool:
        normalized_action = f'"action": "{action_type}"'
        if target:
            normalized_target = f'"target": "{target}"'
            return normalized_action in prompt and normalized_target in prompt
        return normalized_action in prompt

    @staticmethod
    def _json_response(action: str, target: str = "", value: str = "", final_answer: str = "") -> str:
        return json.dumps(
            {
                "action": action,
                "target": target,
                "value": value,
                "url": "",
                "final_answer": final_answer,
            },
            ensure_ascii=True,
        )


class ZhipuBenchmarkAgent(CERAgent):
    def _call_llm_api(self, prompt: str) -> Tuple[str, int, float]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        return _safe_llm_request(self.api_url, self.headers, payload)


def build_agent(
    backend: str,
    config: AgentConfigSpec,
    environment: Any,
    max_steps: int,
    api_url: str = "",
    api_key: str = "",
    model: str = "",
    security_policy: Dict[str, Any] | None = None,
) -> CERAgent:
    memory = CERMemory()
    distiller = NoOpDistiller(api_url="")
    retriever = NoOpRetriever(memory=memory, api_url="")
    common_kwargs: Dict[str, Any] = {
        "memory": memory,
        "distiller": distiller,
        "retriever": retriever,
        "environment": environment,
        "max_steps": max_steps,
        "trace_enabled": False,
        "security_policy": security_policy or {},
        "repeat_constraints_each_step": bool(config.get("repeat_constraints_each_step", False)),
        "history_mode": str(config.get("history_mode", "full")),
        "action_history_limit": int(config.get("action_history_limit", 8)),
        "enable_dead_end_memory": bool(config.get("enable_dead_end_memory", False)),
        "enable_finish_gate": bool(config.get("enable_finish_gate", True)),
        "enable_static_interceptor": bool(config.get("enable_static_interceptor", True)),
    }

    if backend == "local":
        return ScriptedBenchmarkAgent(**common_kwargs)

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key}"
    return ZhipuBenchmarkAgent(
        api_url=api_url,
        model=model,
        headers=headers,
        **common_kwargs,
    )
