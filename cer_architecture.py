from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, TypedDict, cast
from urllib.parse import unquote

import requests


class DynamicEntry(TypedDict):
    """A persisted dynamic page memory item."""

    id: int
    url: str
    name: str
    description: str
    usages: str


class SkillEntry(TypedDict):
    """A persisted skill memory item."""

    id: int
    name: str
    steps: str


class DynamicPayload(TypedDict):
    """A distilled dynamic item before writing into memory."""

    url: str
    name: str
    description: str
    usages: str


class SkillPayload(TypedDict):
    """A distilled skill item before writing into memory."""

    name: str
    steps: str


class AgentAction(TypedDict, total=False):
    """Structured action parsed from LLM output."""

    type: str
    target: str
    value: str
    content: str
    raw: str


class EnvironmentLike(Protocol):
    """Protocol of an environment adapter used by CERAgent."""

    def execute_action(self, action: AgentAction) -> Dict[str, Any]:
        """Execute one action and return an observation dictionary."""


class CERMemory:
    """In-memory state machine for storing CER dynamics and skills.

    This class is the local memory buffer described in the paper. It stores
    two memory channels: dynamics and skills, with incrementing integer IDs.
    """

    def __init__(self) -> None:
        self._dynamics: List[DynamicEntry] = []
        self._skills: List[SkillEntry] = []
        self._next_dynamic_id: int = 1
        self._next_skill_id: int = 1

    def add_dynamic(self, url: str, name: str, description: str, usages: str) -> DynamicEntry:
        """Add one dynamic item into memory and return the persisted record."""

        validated_url = self._validate_non_empty_text("url", url)
        validated_name = self._validate_non_empty_text("name", name)
        validated_description = self._validate_non_empty_text("description", description)
        validated_usages = self._validate_non_empty_text("usages", usages)

        entry: DynamicEntry = {
            "id": self._next_dynamic_id,
            "url": validated_url,
            "name": validated_name,
            "description": validated_description,
            "usages": validated_usages,
        }
        self._dynamics.append(entry)
        self._next_dynamic_id += 1
        return deepcopy(entry)

    def add_skill(self, name: str, steps: str) -> SkillEntry:
        """Add one skill item into memory and return the persisted record."""

        validated_name = self._validate_non_empty_text("name", name)
        validated_steps = self._validate_non_empty_text("steps", steps)

        entry: SkillEntry = {
            "id": self._next_skill_id,
            "name": validated_name,
            "steps": validated_steps,
        }
        self._skills.append(entry)
        self._next_skill_id += 1
        return deepcopy(entry)

    def get_all_dynamics(self) -> List[DynamicEntry]:
        """Return a deep copy of all dynamics."""

        return deepcopy(self._dynamics)

    def get_all_skills(self) -> List[SkillEntry]:
        """Return a deep copy of all skills."""

        return deepcopy(self._skills)

    def get_dynamics_by_ids(self, ids: List[int]) -> List[DynamicEntry]:
        """Return dynamics selected by IDs, preserving input order and uniqueness."""

        id_to_item = {item["id"]: item for item in self._dynamics}
        ordered_items: List[DynamicEntry] = []
        seen: set[int] = set()
        for item_id in ids:
            if item_id in id_to_item and item_id not in seen:
                ordered_items.append(deepcopy(id_to_item[item_id]))
                seen.add(item_id)
        return ordered_items

    def get_skills_by_ids(self, ids: List[int]) -> List[SkillEntry]:
        """Return skills selected by IDs, preserving input order and uniqueness."""

        id_to_item = {item["id"]: item for item in self._skills}
        ordered_items: List[SkillEntry] = []
        seen: set[int] = set()
        for item_id in ids:
            if item_id in id_to_item and item_id not in seen:
                ordered_items.append(deepcopy(id_to_item[item_id]))
                seen.add(item_id)
        return ordered_items

    def save_to_disk(self, filepath: str = "cer_memory.json") -> None:
        """Persist memory state to local JSON file."""

        state = {
            "dynamics": self._dynamics,
            "skills": self._skills,
            "next_dynamic_id": self._next_dynamic_id,
            "next_skill_id": self._next_skill_id,
        }

        try:
            with open(filepath, "w", encoding="utf-8") as file:
                json.dump(state, file, ensure_ascii=False, indent=2)
        except (OSError, TypeError, ValueError) as exc:
            print(f"[WARN] Failed to save CER memory to '{filepath}': {exc}")

    def load_from_disk(self, filepath: str = "cer_memory.json") -> None:
        """Load memory state from local JSON file with defensive fallback."""

        try:
            with open(filepath, "r", encoding="utf-8") as file:
                raw_state = json.load(file)
        except FileNotFoundError:
            print(f"[WARN] Memory file '{filepath}' not found. Starting with empty memory.")
            return
        except json.JSONDecodeError as exc:
            print(f"[WARN] Memory file '{filepath}' is not valid JSON: {exc}")
            return
        except OSError as exc:
            print(f"[WARN] Failed to read memory file '{filepath}': {exc}")
            return

        if not isinstance(raw_state, dict):
            print(f"[WARN] Memory file '{filepath}' has invalid root type. Expected object.")
            return

        try:
            dynamics_raw = raw_state.get("dynamics", [])
            skills_raw = raw_state.get("skills", [])
            next_dynamic_id_raw = raw_state.get("next_dynamic_id", 1)
            next_skill_id_raw = raw_state.get("next_skill_id", 1)

            if not isinstance(dynamics_raw, list) or not isinstance(skills_raw, list):
                raise ValueError("'dynamics' and 'skills' must be lists.")

            validated_dynamics: List[DynamicEntry] = []
            for item in dynamics_raw:
                if not isinstance(item, dict):
                    raise ValueError("Each dynamic item must be an object.")

                dynamic_id = item.get("id")
                url = item.get("url")
                name = item.get("name")
                description = item.get("description")
                usages = item.get("usages")

                if not isinstance(dynamic_id, int) or dynamic_id <= 0:
                    raise ValueError("Dynamic 'id' must be a positive integer.")
                if not all(isinstance(value, str) for value in [url, name, description, usages]):
                    raise ValueError("Dynamic fields 'url/name/description/usages' must be strings.")

                validated_dynamics.append(
                    {
                        "id": dynamic_id,
                        "url": url.strip(),
                        "name": name.strip(),
                        "description": description.strip(),
                        "usages": usages.strip(),
                    }
                )

            validated_skills: List[SkillEntry] = []
            for item in skills_raw:
                if not isinstance(item, dict):
                    raise ValueError("Each skill item must be an object.")

                skill_id = item.get("id")
                name = item.get("name")
                steps = item.get("steps")

                if not isinstance(skill_id, int) or skill_id <= 0:
                    raise ValueError("Skill 'id' must be a positive integer.")
                if not isinstance(name, str) or not isinstance(steps, str):
                    raise ValueError("Skill fields 'name/steps' must be strings.")

                validated_skills.append(
                    {
                        "id": skill_id,
                        "name": name.strip(),
                        "steps": steps.strip(),
                    }
                )

            if not isinstance(next_dynamic_id_raw, int) or not isinstance(next_skill_id_raw, int):
                raise ValueError("'next_dynamic_id' and 'next_skill_id' must be integers.")

            max_dynamic_id = max((item["id"] for item in validated_dynamics), default=0)
            max_skill_id = max((item["id"] for item in validated_skills), default=0)

            next_dynamic_id = max(next_dynamic_id_raw, max_dynamic_id + 1, 1)
            next_skill_id = max(next_skill_id_raw, max_skill_id + 1, 1)
        except (TypeError, ValueError) as exc:
            print(f"[WARN] Memory file '{filepath}' schema validation failed: {exc}")
            return

        self._dynamics = validated_dynamics
        self._skills = validated_skills
        self._next_dynamic_id = next_dynamic_id
        self._next_skill_id = next_skill_id

    def snapshot(self) -> Dict[str, Any]:
        """Create a full memory snapshot for rollback."""

        return {
            "dynamics": deepcopy(self._dynamics),
            "skills": deepcopy(self._skills),
            "next_dynamic_id": self._next_dynamic_id,
            "next_skill_id": self._next_skill_id,
        }

    def restore(self, state: Dict[str, Any]) -> None:
        """Restore memory from a previous snapshot."""

        dynamics = state.get("dynamics")
        skills = state.get("skills")
        next_dynamic_id = state.get("next_dynamic_id")
        next_skill_id = state.get("next_skill_id")

        if not isinstance(dynamics, list) or not isinstance(skills, list):
            raise ValueError("Invalid snapshot: dynamics/skills must be lists.")
        if not isinstance(next_dynamic_id, int) or not isinstance(next_skill_id, int):
            raise ValueError("Invalid snapshot: next IDs must be integers.")

        self._dynamics = deepcopy(cast(List[DynamicEntry], dynamics))
        self._skills = deepcopy(cast(List[SkillEntry], skills))
        self._next_dynamic_id = next_dynamic_id
        self._next_skill_id = next_skill_id

    @staticmethod
    def _validate_non_empty_text(field_name: str, value: str) -> str:
        """Validate mandatory string fields."""

        if not isinstance(value, str):
            raise TypeError(f"Field '{field_name}' must be a string.")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"Field '{field_name}' cannot be empty.")
        return cleaned


class CERDistiller:
    """Experience distiller that extracts dynamics/skills from trajectory.

    The distiller sends a trajectory prompt to an LLM and then uses robust
    regex parsing to extract structured memory records from XML-like output.
    """

    def __init__(
        self,
        api_url: str = "",
        model: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.api_url = api_url
        self.model = model
        self.headers = headers or {"Content-Type": "application/json"}

    def distill_dynamics(self, trajectory: str) -> List[DynamicPayload]:
        """Call LLM and parse dynamic page experiences from response."""

        if not trajectory.strip():
            return []

        prompt = self._build_dynamics_prompt(trajectory)
        llm_response = self._call_llm_api(prompt)
        return self.parse_dynamics(llm_response)

    def distill_skills(self, trajectory: str) -> List[SkillPayload]:
        """Call LLM and parse operational skills from response."""

        if not trajectory.strip():
            return []

        prompt = self._build_skills_prompt(trajectory)
        llm_response = self._call_llm_api(prompt)
        return self.parse_skills(llm_response)

    def parse_dynamics(self, llm_response: str) -> List[DynamicPayload]:
        """Parse Dynamics records from XML-like text.

        Expected pattern per record:
        <URL>...</URL>
        <think>...</think>
        <page-summary>
          Name: ...
          Description: ...
          Usages: ...
        </page-summary>

        The parser intentionally ignores the <think> section.
        """

        if not llm_response.strip():
            return []

        try:
            blocks = re.findall(
                r"<URL>\s*(.*?)\s*</URL>.*?<page-summary>\s*(.*?)\s*</page-summary>",
                llm_response,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not blocks:
                return []

            results: List[DynamicPayload] = []
            for url_block, summary_block in blocks:
                url = _normalize_space(url_block)
                name_match = re.search(
                    r"Name:\s*(.*?)(?=\n\s*Description:|\Z)",
                    summary_block,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                description_match = re.search(
                    r"Description:\s*(.*?)(?=\n\s*Usages:|\Z)",
                    summary_block,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                usages_match = re.search(
                    r"Usages:\s*(.*?)(?=\Z)",
                    summary_block,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                if not name_match or not description_match or not usages_match:
                    continue

                name = _normalize_space(name_match.group(1))
                description = _normalize_space(description_match.group(1))
                usages = _normalize_space(usages_match.group(1))

                if not url or not name or not description or not usages:
                    continue

                results.append(
                    {
                        "url": url,
                        "name": name,
                        "description": description,
                        "usages": usages,
                    }
                )
            return results
        except Exception:
            return []

    def parse_skills(self, llm_response: str) -> List[SkillPayload]:
        """Parse skill records from XML-like text.

        Expected pattern per record:
        <skill>skill name</skill>
        <steps>step 1 ... step 2 ...</steps>
        """

        if not llm_response.strip():
            return []

        try:
            blocks = re.findall(
                r"<skill>\s*(.*?)\s*</skill>\s*<steps>\s*(.*?)\s*</steps>",
                llm_response,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not blocks:
                return []

            results: List[SkillPayload] = []
            for name_block, steps_block in blocks:
                name = _normalize_space(name_block)
                steps = _normalize_multiline(steps_block)
                if not name or not steps:
                    continue
                results.append({"name": name, "steps": steps})
            return results
        except Exception:
            return []

    def _build_dynamics_prompt(self, trajectory: str) -> str:
        return (
            "Extract Dynamics from trajectory. Output each record in the exact format:\n"
            "<URL>...</URL>\n"
            "<think>...</think>\n"
            "<page-summary>Name: ...\nDescription: ...\nUsages: ...</page-summary>\n\n"
            f"Trajectory:\n{trajectory}"
        )

    def _build_skills_prompt(self, trajectory: str) -> str:
        return (
            "Extract reusable skills from trajectory. Output each record in the exact format:\n"
            "<skill>skill name</skill>\n"
            "<steps>step 1 ... step 2 ...</steps>\n\n"
            f"Trajectory:\n{trajectory}"
        )

    def _call_llm_api(self, prompt: str) -> str:
        """Unified LLM call shell.

        You can fill api_url/model/payload details according to your provider.
        """

        payload: Dict[str, Any] = {"prompt": prompt}
        if self.model:
            payload["model"] = self.model
        return _safe_llm_request(self.api_url, self.headers, payload)


class CERRetriever:
    """Retriever for selecting top-k dynamics and skills via LLM ranking."""

    def __init__(
        self,
        memory: CERMemory,
        api_url: str = "",
        model: str = "",
        headers: Optional[Dict[str, str]] = None,
        k_d: int = 5,
        k_s: int = 5,
    ) -> None:
        if k_d <= 0 or k_s <= 0:
            raise ValueError("k_d and k_s must be positive integers.")

        self.memory = memory
        self.api_url = api_url
        self.model = model
        self.headers = headers or {"Content-Type": "application/json"}
        self.k_d = k_d
        self.k_s = k_s

    def retrieve(self, task_goal: str) -> Tuple[List[DynamicEntry], List[SkillEntry]]:
        """Retrieve top-k dynamics and top-k skills for the incoming task."""

        dynamics = self.retrieve_dynamics(task_goal)
        skills = self.retrieve_skills(task_goal)
        return dynamics, skills

    def retrieve_dynamics(self, task_goal: str) -> List[DynamicEntry]:
        """Retrieve top-k dynamic pages selected by LLM."""

        candidates = self.memory.get_all_dynamics()
        if not candidates:
            return []

        prompt = self._build_dynamic_retrieval_prompt(task_goal, candidates)
        llm_response = self._call_llm_api(prompt)
        selected_ids = self.parse_selected_ids(llm_response)

        if not selected_ids:
            return candidates[: self.k_d]

        selected_items = self.memory.get_dynamics_by_ids(selected_ids)
        if not selected_items:
            return candidates[: self.k_d]
        return selected_items[: self.k_d]

    def retrieve_skills(self, task_goal: str) -> List[SkillEntry]:
        """Retrieve top-k skills selected by LLM."""

        candidates = self.memory.get_all_skills()
        if not candidates:
            return []

        prompt = self._build_skill_retrieval_prompt(task_goal, candidates)
        llm_response = self._call_llm_api(prompt)
        selected_ids = self.parse_selected_ids(llm_response)

        if not selected_ids:
            return candidates[: self.k_s]

        selected_items = self.memory.get_skills_by_ids(selected_ids)
        if not selected_items:
            return candidates[: self.k_s]
        return selected_items[: self.k_s]

    def parse_selected_ids(self, llm_response: str) -> List[int]:
        """Parse selected memory IDs from XML-like selected tags.

        Supported examples:
        <selected-pages>
        id: 1; name: Forums page
        id: 2; name: Profile page
        </selected-pages>

        <selected-skills>
        id: 1; name: Navigate to forums
        </selected-skills>
        """

        if not llm_response.strip():
            return []

        try:
            selected_sections = re.findall(
                r"<selected-(?:pages|skills)>\s*(.*?)\s*</selected-(?:pages|skills)>",
                llm_response,
                flags=re.IGNORECASE | re.DOTALL,
            )

            search_spaces = selected_sections if selected_sections else [llm_response]
            ids: List[int] = []
            for section in search_spaces:
                matches = re.findall(r"\bid\s*[:=]\s*(\d+)\b", section, flags=re.IGNORECASE)
                for match in matches:
                    parsed = int(match)
                    if parsed not in ids:
                        ids.append(parsed)
            return ids
        except Exception:
            return []

    def _build_dynamic_retrieval_prompt(self, task_goal: str, candidates: List[DynamicEntry]) -> str:
        candidate_lines = [
            (
                f"id: {item['id']} | name: {item['name']} | url: {item['url']} | "
                f"description: {item['description']} | usages: {item['usages']}"
            )
            for item in candidates
        ]
        candidate_text = "\n".join(candidate_lines)
        return (
            f"Task goal: {task_goal}\n"
            f"Select up to {self.k_d} most relevant pages by ID only.\n"
            "Output must be wrapped in <selected-pages>...</selected-pages>.\n"
            "Use lines formatted as: id: N; name: ...\n\n"
            f"Candidates:\n{candidate_text}"
        )

    def _build_skill_retrieval_prompt(self, task_goal: str, candidates: List[SkillEntry]) -> str:
        candidate_lines = [
            f"id: {item['id']} | name: {item['name']} | steps: {item['steps']}" for item in candidates
        ]
        candidate_text = "\n".join(candidate_lines)
        return (
            f"Task goal: {task_goal}\n"
            f"Select up to {self.k_s} most relevant skills by ID only.\n"
            "Output must be wrapped in <selected-skills>...</selected-skills>.\n"
            "Use lines formatted as: id: N; name: ...\n\n"
            f"Candidates:\n{candidate_text}"
        )

    def _call_llm_api(self, prompt: str) -> str:
        """Unified LLM call shell.

        You can fill api_url/model/payload details according to your provider.
        """

        payload: Dict[str, Any] = {"prompt": prompt}
        if self.model:
            payload["model"] = self.model
        return _safe_llm_request(self.api_url, self.headers, payload)


class CERAgent:
    """Main scheduler that runs retrieval, acting loop, and distillation pipeline."""

    def __init__(
        self,
        memory: CERMemory,
        distiller: CERDistiller,
        retriever: CERRetriever,
        environment: EnvironmentLike | Callable[[AgentAction], Dict[str, Any]],
        api_url: str = "",
        model: str = "",
        headers: Optional[Dict[str, str]] = None,
        base_context: str = "You are a task-solving web agent.",
        max_steps: int = 15,
        trace_enabled: bool = False,
        llm_empty_retry: int = 1,
        prompt_observation_line_limit: int = 30,
        prompt_observation_char_limit: int = 4000,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive.")
        if llm_empty_retry < 0:
            raise ValueError("llm_empty_retry must be >= 0.")
        if prompt_observation_line_limit <= 0:
            raise ValueError("prompt_observation_line_limit must be positive.")
        if prompt_observation_char_limit <= 0:
            raise ValueError("prompt_observation_char_limit must be positive.")

        self.memory = memory
        self.distiller = distiller
        self.retriever = retriever
        self.environment = environment
        self.api_url = api_url
        self.model = model
        self.headers = headers or {"Content-Type": "application/json"}
        self.base_context = base_context.strip() or "You are a task-solving web agent."
        self.max_steps = max_steps
        self.trace_enabled = trace_enabled
        self.llm_empty_retry = llm_empty_retry
        self.prompt_observation_line_limit = prompt_observation_line_limit
        self.prompt_observation_char_limit = prompt_observation_char_limit

    def run_task(self, task_goal: str) -> Dict[str, Any]:
        """Run one complete CER task pipeline.

        Pipeline:
        1) Retrieve top-k memories.
        2) Convert structured memories to natural language E_NL.
        3) Compose final context C' = g(C, E_NL).
        4) Execute iterative act loop until task completion.
        5) Distill trajectory and persist new dynamics/skills into memory.
        """

        normalized_goal = task_goal.strip()
        if not normalized_goal:
            raise ValueError("task_goal cannot be empty.")

        selected_dynamics, selected_skills = self.retriever.retrieve(normalized_goal)
        memory_text = self._format_experience_as_nl(selected_dynamics, selected_skills)
        composed_context = self._compose_context(normalized_goal, memory_text)

        trajectory: List[Dict[str, Any]] = []
        final_answer = ""
        success = False

        step = 0
        while True:
            if step >= self.max_steps:
                trajectory.append(
                    {
                        "event": "max_steps_reached",
                        "detail": f"Stopped because max_steps={self.max_steps}.",
                    }
                )
                break

            step += 1
            current_observation = self._get_environment_observation()
            observation_text = str(current_observation.get("observation_text", "")).strip()
            prompt = self._build_agent_prompt(composed_context, trajectory, step, observation_text)
            llm_output = ""
            llm_retries = 0
            llm_error = "unknown"

            while True:
                llm_output = self._call_llm_api(prompt)
                if llm_output:
                    break

                last_error = get_last_llm_error().strip()
                if last_error:
                    llm_error = last_error

                if llm_retries >= self.llm_empty_retry:
                    break

                llm_retries += 1
                if self.trace_enabled:
                    print(
                        f"[TRACE] step={step} empty_llm_response retry={llm_retries} "
                        f"last_error='{llm_error}'"
                    )

            if not llm_output:
                done_by_observation, inferred_answer, inferred_reason = self._infer_completion_from_observation(
                    normalized_goal,
                    current_observation,
                )

                empty_event: Dict[str, Any] = {
                    "step": step,
                    "error": "empty_llm_response",
                    "llm_error": llm_error,
                    "llm_retries": llm_retries,
                    "pre_observation": current_observation,
                }

                if done_by_observation:
                    success = True
                    final_answer = inferred_answer
                    empty_event["completion_inferred"] = True
                    empty_event["completion_reason"] = inferred_reason

                trajectory.append(empty_event)
                break

            action = self._parse_action(llm_output)
            if action.get("type") == "finish":
                success = True
                final_answer = action.get("content", "")
                if self.trace_enabled:
                    print(
                        f"[TRACE] step={step} action=finish "
                        f"pre_obs={self._observation_preview(current_observation)}"
                    )
                trajectory.append(
                    {
                        "step": step,
                        "llm_output": llm_output,
                        "action": action,
                        "pre_observation": current_observation,
                        "observation": "Task marked completed by model.",
                    }
                )
                break

            env_result = self._execute_action(action)
            post_observation = self._get_environment_observation()
            if self.trace_enabled:
                self._print_action_observation_trace(step, action, current_observation, post_observation, env_result)

            step_event: Dict[str, Any] = {
                "step": step,
                "llm_output": llm_output,
                "action": action,
                "pre_observation": current_observation,
                "post_observation": post_observation,
                "observation": env_result,
            }
            trajectory.append(step_event)

            if bool(env_result.get("done")):
                success = True
                final_answer = str(env_result.get("final_answer", ""))
                break

            done_by_observation, inferred_answer, inferred_reason = self._infer_completion_from_observation(
                normalized_goal,
                post_observation,
            )
            if done_by_observation:
                success = True
                final_answer = inferred_answer
                step_event["completion_inferred"] = True
                step_event["completion_reason"] = inferred_reason
                break

        persisted_dynamic_ids: List[int] = []
        persisted_skill_ids: List[int] = []

        memory_snapshot = self.memory.snapshot()
        trajectory_text = self._trajectory_to_text(normalized_goal, trajectory, success, final_answer)
        try:
            distilled_dynamics = self.distiller.distill_dynamics(trajectory_text)
            distilled_skills = self.distiller.distill_skills(trajectory_text)

            for item in distilled_dynamics:
                saved = self.memory.add_dynamic(
                    url=item["url"],
                    name=item["name"],
                    description=item["description"],
                    usages=item["usages"],
                )
                persisted_dynamic_ids.append(saved["id"])

            for item in distilled_skills:
                saved = self.memory.add_skill(name=item["name"], steps=item["steps"])
                persisted_skill_ids.append(saved["id"])
        except Exception as exc:
            # Roll back memory state if persistence fails.
            self.memory.restore(memory_snapshot)
            trajectory.append({"event": "memory_rollback", "error": str(exc)})
            persisted_dynamic_ids = []
            persisted_skill_ids = []

        return {
            "task_goal": normalized_goal,
            "success": success,
            "final_answer": final_answer,
            "steps": step,
            "selected_dynamic_ids": [item["id"] for item in selected_dynamics],
            "selected_skill_ids": [item["id"] for item in selected_skills],
            "persisted_dynamic_ids": persisted_dynamic_ids,
            "persisted_skill_ids": persisted_skill_ids,
            "trajectory": trajectory,
        }

    def _format_experience_as_nl(
        self,
        dynamics: List[DynamicEntry],
        skills: List[SkillEntry],
    ) -> str:
        """Map structured experience E to natural language E_NL."""

        lines: List[str] = []
        if dynamics:
            lines.append("[Relevant Dynamics]")
            for item in dynamics:
                lines.append(
                    f"- Page #{item['id']} '{item['name']}' at {item['url']}. "
                    f"Description: {item['description']}. Usages: {item['usages']}."
                )

        if skills:
            lines.append("[Relevant Skills]")
            for item in skills:
                lines.append(f"- Skill #{item['id']} '{item['name']}': {item['steps']}")

        return "\n".join(lines).strip()

    def _compose_context(self, task_goal: str, experience_text: str) -> str:
        """Compose C' = g(C, E_NL)."""

        experience_section = experience_text if experience_text else "No retrieved experience."
        return (
            f"{self.base_context}\n\n"
            f"Task Goal:\n{task_goal}\n\n"
            f"External Experience Memory:\n{experience_section}"
        )

    def _build_agent_prompt(
        self,
        composed_context: str,
        trajectory: List[Dict[str, Any]],
        step: int,
        observation_text: str,
    ) -> str:
        """Build iterative prompt for action generation."""

        recent_trajectory = trajectory[-5:]
        trajectory_text = json.dumps(recent_trajectory, ensure_ascii=True)
        observation_block = self._format_observation_for_prompt(observation_text)
        return (
            f"Step: {step}\n"
            f"{composed_context}\n\n"
            "Current Observation:\n"
            f"{observation_block}\n\n"
            "Policy (must follow):\n"
            "- Decide the next single action ONLY based on Task Goal + Current Observation.\n"
            "- Prefer Observation IDs from the list (e.g. [12]) for <target>.\n"
            "- Use raw CSS selector only if no suitable Observation ID exists.\n"
            "- For navigation, output <action>goto</action><url>https://...</url>.\n"
            "- For text input, output <action>type</action><target>[id]</target><value>...</value>.\n"
            "- For keyboard submit, output <action>press</action><target>[id]</target><value>Enter</value>.\n"
            "- When task is complete, output <final-answer>...</final-answer>.\n\n"
            "Recent Trajectory (JSON):\n"
            f"{trajectory_text}\n\n"
            "Respond with exactly one action block or one final-answer block.\n"
        )

    def _format_observation_for_prompt(self, observation_text: str) -> str:
        """Truncate oversized observation text to keep prompts stable."""

        cleaned = observation_text.strip()
        if not cleaned:
            return "No environment observation available."

        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if not lines:
            return "No environment observation available."

        selected_lines = lines[: self.prompt_observation_line_limit]
        clipped_text = "\n".join(selected_lines)

        char_truncated = False
        if len(clipped_text) > self.prompt_observation_char_limit:
            clipped_text = clipped_text[: self.prompt_observation_char_limit].rstrip()
            char_truncated = True

        omitted_count = len(lines) - len(selected_lines)
        if omitted_count > 0:
            clipped_text = f"{clipped_text}\n... (+{omitted_count} more lines omitted)"
        if char_truncated:
            clipped_text = f"{clipped_text}\n... (truncated for prompt size)"
        return clipped_text

    def _infer_completion_from_observation(
        self,
        task_goal: str,
        observation: Dict[str, Any],
    ) -> Tuple[bool, str, str]:
        """Infer completion for search tasks from URL/title/observation text."""

        query = self._extract_search_query(task_goal)
        if not query:
            return False, "", "no_search_query_detected"

        url = str(observation.get("url", "")).strip()
        title = str(observation.get("title", "")).strip()
        observation_text = str(observation.get("observation_text", "")).strip()
        if not url and not title and not observation_text:
            return False, "", "empty_observation"

        query_norm = query.lower()
        url_norm = unquote(url).lower()
        title_norm = title.lower()
        observation_norm = observation_text.lower()

        search_markers = (
            "wd=",
            "q=",
            "query=",
            "search",
            "/s?",
            "baidu.com/s",
            "bing.com/search",
            "google.com/search",
        )
        has_search_marker = any(marker in url_norm for marker in search_markers)

        query_in_url = query_norm in url_norm
        query_in_title = query_norm in title_norm
        query_in_text = query_norm in observation_norm

        done = False
        reason = "query_not_detected"
        if has_search_marker and (query_in_url or query_in_title):
            done = True
            reason = "query_detected_in_search_url_or_title"
        elif query_in_url and query_in_text:
            done = True
            reason = "query_detected_in_url_and_observation"

        if not done:
            return False, "", reason

        final_answer = f"Search task completed for query: {query}"
        return True, final_answer, reason

    @staticmethod
    def _extract_search_query(task_goal: str) -> str:
        """Extract probable search query from natural language task goals."""

        goal = task_goal.strip()
        if not goal:
            return ""

        patterns = [
            r"(?:search\s+for|search|look\s+up)\s+[\"'“”]?([^\n\r\.,;]+)",
            r"(?:搜索|查找)\s*[\"'“”]?([^\n\r，。,;；]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, goal, flags=re.IGNORECASE)
            if not match:
                continue

            candidate = _normalize_space(match.group(1)).strip(" \"'“”")
            for delimiter in [" 然后", " 并且", " and then", " then", " and "]:
                if delimiter in candidate:
                    candidate = candidate.split(delimiter)[0].strip()
            if candidate:
                return candidate

        return ""

    def _parse_action(self, llm_output: str) -> AgentAction:
        """Parse a structured action from LLM output."""

        final_match = re.search(r"<final-answer>\s*(.*?)\s*</final-answer>", llm_output, flags=re.IGNORECASE | re.DOTALL)
        if final_match:
            return {
                "type": "finish",
                "content": final_match.group(1).strip(),
                "raw": llm_output,
            }

        action_match = re.search(r"<action>\s*(.*?)\s*</action>", llm_output, flags=re.IGNORECASE | re.DOTALL)
        if not action_match:
            return {"type": "think", "raw": llm_output}

        action_type = _normalize_space(action_match.group(1)).lower()
        target_match = re.search(r"<target>\s*(.*?)\s*</target>", llm_output, flags=re.IGNORECASE | re.DOTALL)
        value_match = re.search(r"<value>\s*(.*?)\s*</value>", llm_output, flags=re.IGNORECASE | re.DOTALL)

        target = target_match.group(1).strip() if target_match else ""
        value = value_match.group(1).strip() if value_match else ""

        if action_type in {"finish", "done", "complete", "completed"}:
            return {
                "type": "finish",
                "content": value or target,
                "raw": llm_output,
            }

        return {
            "type": action_type if action_type else "noop",
            "target": target,
            "value": value,
            "raw": llm_output,
        }

    def _execute_action(self, action: AgentAction) -> Dict[str, Any]:
        """Execute one action against injected environment adapter."""

        try:
            # TODO: 接入 BrowserGym 执行动作
            if hasattr(self.environment, "execute_action") and callable(getattr(self.environment, "execute_action")):
                return cast(EnvironmentLike, self.environment).execute_action(action)
            if callable(self.environment):
                return cast(Callable[[AgentAction], Dict[str, Any]], self.environment)(action)
            return {
                "done": False,
                "error": "Environment does not implement execute_action and is not callable.",
            }
        except Exception as exc:
            return {"done": False, "error": f"action_execution_failed: {exc}"}

    def _get_environment_observation(self) -> Dict[str, Any]:
        """Get current environment observation if adapter supports it."""

        try:
            if hasattr(self.environment, "get_observation") and callable(getattr(self.environment, "get_observation")):
                observation = getattr(self.environment, "get_observation")()
                if isinstance(observation, dict):
                    return observation
                return {"observation_text": str(observation)}
            return {"observation_text": "No environment observation available."}
        except Exception as exc:
            return {
                "observation_text": "<observation-unavailable>",
                "error": f"get_observation_failed: {exc}",
            }

    def _print_action_observation_trace(
        self,
        step: int,
        action: AgentAction,
        pre_observation: Dict[str, Any],
        post_observation: Dict[str, Any],
        env_result: Dict[str, Any],
    ) -> None:
        """Print concise action-observation alignment trace for debugging."""

        action_type = str(action.get("type", "noop"))
        target = str(action.get("target", ""))
        value = str(action.get("value", ""))
        env_done = bool(env_result.get("done"))
        env_error = str(env_result.get("error", "")).strip()

        print(f"[TRACE] step={step} action={action_type} target='{target}' value='{value}' done={env_done}")
        print(f"[TRACE] step={step} pre_obs={self._observation_preview(pre_observation)}")
        print(f"[TRACE] step={step} post_obs={self._observation_preview(post_observation)}")
        if env_error:
            print(f"[TRACE] step={step} env_error={env_error}")

    @staticmethod
    def _observation_preview(observation: Dict[str, Any], line_limit: int = 2) -> str:
        """Build short preview text from observation content."""

        text = str(observation.get("observation_text", "")).strip()
        if not text:
            return "<no-observation>"

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return "<no-observation-lines>"

        preview = " | ".join(lines[:line_limit])
        remaining = len(lines) - line_limit
        if remaining > 0:
            preview = f"{preview} | ...(+{remaining})"
        return preview

    def _trajectory_to_text(
        self,
        task_goal: str,
        trajectory: List[Dict[str, Any]],
        success: bool,
        final_answer: str,
    ) -> str:
        """Serialize trajectory into distillation input text."""

        header = (
            f"Task Goal: {task_goal}\n"
            f"Task Success: {success}\n"
            f"Final Answer: {final_answer}\n"
            "Trajectory:\n"
        )
        body = json.dumps(trajectory, ensure_ascii=True, indent=2)
        return header + body

    def _call_llm_api(self, prompt: str) -> str:
        """Unified LLM call shell.

        You can fill api_url/model/payload details according to your provider.
        """

        payload: Dict[str, Any] = {"prompt": prompt}
        if self.model:
            payload["model"] = self.model
        return _safe_llm_request(self.api_url, self.headers, payload)


class MockEnvironment:
    """Minimal mock environment to validate agent pipeline wiring."""

    def execute_action(self, action: AgentAction) -> Dict[str, Any]:
        action_name = action.get("type", "noop")
        if action_name in {"submit", "confirm"}:
            return {
                "done": True,
                "final_answer": "Mock environment marked the task as complete.",
                "observation": f"Executed action: {action_name}",
            }
        return {
            "done": False,
            "observation": f"Executed action: {action_name}",
        }


_LAST_LLM_ERROR: str = ""


def get_last_llm_error() -> str:
    """Return last LLM request error category for debugging."""

    return _LAST_LLM_ERROR


def _safe_llm_request(api_url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> str:
    """Perform a defensive LLM HTTP call and return extracted text output."""

    global _LAST_LLM_ERROR

    if not api_url.strip():
        _LAST_LLM_ERROR = "empty_api_url"
        return ""

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        _LAST_LLM_ERROR = f"request_exception:{exc.__class__.__name__}"
        return ""

    try:
        data = response.json()
    except ValueError:
        _LAST_LLM_ERROR = "invalid_json_response"
        return ""

    extracted = _extract_text_from_llm_json(data)
    if not extracted.strip():
        _LAST_LLM_ERROR = "empty_text_output"
        return ""

    _LAST_LLM_ERROR = ""
    return extracted


def _extract_text_from_llm_json(data: Any) -> str:
    """Best-effort extraction of text from common LLM JSON response formats."""

    if isinstance(data, str):
        return data

    if isinstance(data, dict):
        for key in ("text", "content", "output", "response"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                text = first_choice.get("text")
                if isinstance(text, str) and text.strip():
                    return text
                message = first_choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content

        results = data.get("results")
        if isinstance(results, list) and results:
            first_result = results[0]
            if isinstance(first_result, dict):
                content = first_result.get("content")
                if isinstance(content, str) and content.strip():
                    return content

    return ""


def _normalize_space(text: str) -> str:
    """Normalize all whitespace runs to a single space."""

    return re.sub(r"\s+", " ", text).strip()


def _normalize_multiline(text: str) -> str:
    """Normalize multiline text while preserving line boundaries."""

    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return "\n".join(lines)
