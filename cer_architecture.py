from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, TypedDict, cast
from urllib.parse import unquote, urlsplit, urlunsplit

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


class ActionSecurityPolicy(TypedDict, total=False):
    """Deterministic guardrail policy applied before environment execution."""

    allowed_domains: List[str]
    blocked_domains: List[str]
    high_risk_keywords: List[str]
    interactive_approval: bool


class TargetMetadata(TypedDict, total=False):
    """Environment-provided metadata for one actionable target."""

    selector: str
    role: str
    text: str
    aria_label: str
    name: str
    tag: str
    type: str
    title: str


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

        canonical_url = self._canonicalize_url(validated_url)
        for index, item in enumerate(self._dynamics):
            if self._canonicalize_url(item["url"]) != canonical_url:
                continue

            merged_name = self._merge_prefer_informative(item["name"], validated_name)
            merged_description = self._merge_unique_text(item["description"], validated_description)
            merged_usages = self._merge_unique_text(item["usages"], validated_usages)

            updated: DynamicEntry = {
                "id": item["id"],
                "url": item["url"],
                "name": merged_name,
                "description": merged_description,
                "usages": merged_usages,
            }
            self._dynamics[index] = updated
            return deepcopy(updated)

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

    @staticmethod
    def _canonicalize_url(url: str) -> str:
        """Canonicalize URL for duplicate detection."""

        cleaned = url.strip()
        if not cleaned:
            return cleaned

        try:
            parsed = urlsplit(cleaned)
        except Exception:
            return cleaned.lower().rstrip("/")

        scheme = (parsed.scheme or "https").lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        query = parsed.query

        canonical = urlunsplit((scheme, netloc, path, query, ""))
        return canonical if canonical else cleaned.lower().rstrip("/")

    @staticmethod
    def _merge_unique_text(existing: str, incoming: str, separator: str = " | ", max_length: int = 1200) -> str:
        """Merge text snippets while removing case-insensitive duplicates."""

        left = existing.strip()
        right = incoming.strip()
        if not left:
            return right[:max_length]
        if not right:
            return left[:max_length]

        left_norm = left.lower()
        right_norm = right.lower()
        if left_norm == right_norm:
            return left[:max_length]
        if right_norm in left_norm:
            return left[:max_length]
        if left_norm in right_norm:
            return right[:max_length]

        merged = f"{left}{separator}{right}"
        return merged[:max_length]

    @staticmethod
    def _merge_prefer_informative(existing: str, incoming: str) -> str:
        """Prefer the longer informative name when duplicates are merged."""

        left = existing.strip()
        right = incoming.strip()
        if not left:
            return right
        if not right:
            return left
        if len(right) > len(left):
            return right
        return left


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

        json_obj = _extract_first_json_object(llm_response)
        if isinstance(json_obj, dict):
            json_results = self._parse_dynamics_from_json_obj(json_obj)
            if json_results:
                return json_results

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

    def _parse_dynamics_from_json_obj(self, payload: Dict[str, Any]) -> List[DynamicPayload]:
        """Parse dynamics from JSON payload with flexible key shapes."""

        keys = ["dynamics", "pages", "items", "results"]
        records: Any = None
        for key in keys:
            candidate = payload.get(key)
            if isinstance(candidate, list):
                records = candidate
                break

        if records is None and all(k in payload for k in ("url", "name", "description", "usages")):
            records = [payload]

        if not isinstance(records, list):
            return []

        parsed_results: List[DynamicPayload] = []
        for item in records:
            if not isinstance(item, dict):
                continue

            url = _normalize_space(str(item.get("url", "")))
            name = _normalize_space(str(item.get("name", item.get("title", ""))))
            description = _normalize_space(str(item.get("description", item.get("summary", ""))))
            usages = _normalize_space(str(item.get("usages", item.get("usage", ""))))

            if not url or not name or not description or not usages:
                continue

            parsed_results.append(
                {
                    "url": url,
                    "name": name,
                    "description": description,
                    "usages": usages,
                }
            )

        return parsed_results

    def parse_skills(self, llm_response: str) -> List[SkillPayload]:
        """Parse skill records from XML-like text.

        Expected pattern per record:
        <skill>skill name</skill>
        <steps>step 1 ... step 2 ...</steps>
        """

        if not llm_response.strip():
            return []

        json_obj = _extract_first_json_object(llm_response)
        if isinstance(json_obj, dict):
            json_results = self._parse_skills_from_json_obj(json_obj)
            if json_results:
                return json_results

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

    def _parse_skills_from_json_obj(self, payload: Dict[str, Any]) -> List[SkillPayload]:
        """Parse skills from JSON payload with flexible key shapes."""

        keys = ["skills", "items", "results"]
        records: Any = None
        for key in keys:
            candidate = payload.get(key)
            if isinstance(candidate, list):
                records = candidate
                break

        if records is None and all(k in payload for k in ("name", "steps")):
            records = [payload]

        if not isinstance(records, list):
            return []

        parsed_results: List[SkillPayload] = []
        for item in records:
            if not isinstance(item, dict):
                continue

            name = _normalize_space(str(item.get("name", item.get("skill", ""))))
            steps_raw = str(item.get("steps", item.get("procedure", "")))
            steps = _normalize_multiline(steps_raw)
            if not name or not steps:
                continue
            parsed_results.append({"name": name, "steps": steps})

        return parsed_results

    def _build_dynamics_prompt(self, trajectory: str) -> str:
        return (
            "Extract dynamics from trajectory and return JSON only (no markdown).\n"
            "Schema: {\"dynamics\":[{\"url\":\"...\",\"name\":\"...\",\"description\":\"...\",\"usages\":\"...\"}]}.\n"
            f"Trajectory:\n{trajectory}"
        )

    def _build_skills_prompt(self, trajectory: str) -> str:
        return (
            "Extract reusable skills from trajectory and return JSON only (no markdown).\n"
            "Schema: {\"skills\":[{\"name\":\"...\",\"steps\":\"step1\\nstep2\"}]}.\n"
            f"Trajectory:\n{trajectory}"
        )

    def _call_llm_api(self, prompt: str) -> str:
        """Unified LLM call shell.

        You can fill api_url/model/payload details according to your provider.
        """

        payload: Dict[str, Any] = {"prompt": prompt}
        if self.model:
            payload["model"] = self.model
        extracted_text, _, _ = _safe_llm_request(self.api_url, self.headers, payload)
        return extracted_text


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

        json_obj = _extract_first_json_object(llm_response)
        if isinstance(json_obj, dict):
            json_ids = self._parse_selected_ids_from_json_obj(json_obj)
            if json_ids:
                return json_ids

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

    def _parse_selected_ids_from_json_obj(self, payload: Dict[str, Any]) -> List[int]:
        """Parse selected IDs from JSON payload with flexible key names."""

        candidate_lists: List[Any] = []
        for key in ("selected_ids", "ids", "selected", "selected_pages", "selected_skills"):
            value = payload.get(key)
            if isinstance(value, list):
                candidate_lists.append(value)

        if not candidate_lists:
            return []

        ids: List[int] = []
        for items in candidate_lists:
            for value in items:
                parsed_id: Optional[int] = None
                if isinstance(value, int):
                    parsed_id = value
                elif isinstance(value, str) and value.strip().isdigit():
                    parsed_id = int(value.strip())
                elif isinstance(value, dict):
                    raw_id = value.get("id")
                    if isinstance(raw_id, int):
                        parsed_id = raw_id
                    elif isinstance(raw_id, str) and raw_id.strip().isdigit():
                        parsed_id = int(raw_id.strip())

                if parsed_id is None or parsed_id <= 0:
                    continue
                if parsed_id not in ids:
                    ids.append(parsed_id)
        return ids

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
            "Return JSON only (no markdown).\n"
            "Schema: {\"selected_ids\":[1,2,3]}.\n\n"
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
            "Return JSON only (no markdown).\n"
            "Schema: {\"selected_ids\":[1,2,3]}.\n\n"
            f"Candidates:\n{candidate_text}"
        )

    def _call_llm_api(self, prompt: str) -> str:
        """Unified LLM call shell.

        You can fill api_url/model/payload details according to your provider.
        """

        payload: Dict[str, Any] = {"prompt": prompt}
        if self.model:
            payload["model"] = self.model
        extracted_text, _, _ = _safe_llm_request(self.api_url, self.headers, payload)
        return extracted_text


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
        security_policy: Optional[ActionSecurityPolicy] = None,
        repeat_constraints_each_step: bool = False,
        history_mode: str = "full",
        action_history_limit: int = 8,
        enable_finish_gate: bool = True,
        enable_static_interceptor: bool = True,
        enable_dead_end_memory: bool = True,
        dead_end_limit: int = 8,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive.")
        if llm_empty_retry < 0:
            raise ValueError("llm_empty_retry must be >= 0.")
        if prompt_observation_line_limit <= 0:
            raise ValueError("prompt_observation_line_limit must be positive.")
        if prompt_observation_char_limit <= 0:
            raise ValueError("prompt_observation_char_limit must be positive.")
        if history_mode not in {"full", "summary"}:
            raise ValueError("history_mode must be 'full' or 'summary'.")
        if action_history_limit <= 0:
            raise ValueError("action_history_limit must be positive.")
        if dead_end_limit <= 0:
            raise ValueError("dead_end_limit must be positive.")

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
        self.security_policy = security_policy or {}
        self.repeat_constraints_each_step = repeat_constraints_each_step
        self.history_mode = history_mode
        self.action_history_limit = action_history_limit
        self.enable_finish_gate = enable_finish_gate
        self.enable_static_interceptor = enable_static_interceptor
        self.enable_dead_end_memory = enable_dead_end_memory
        self.dead_end_limit = dead_end_limit
        self.global_constraints: str = ""
        self.total_tokens: int = 0
        self.total_latency: float = 0.0

    def set_global_constraints(self, text: str) -> None:
        """Set the current top-priority constraint block."""

        self.global_constraints = text.strip()

    def replace_global_constraints(self, text: str) -> None:
        """Replace the current top-priority constraint block."""

        self.set_global_constraints(text)

    def append_global_constraint(self, text: str) -> None:
        """Append one more top-priority constraint line."""

        addition = text.strip()
        if not addition:
            return
        if not self.global_constraints:
            self.global_constraints = addition
            return
        self.global_constraints = f"{self.global_constraints}\n{addition}"

    def run_task(
        self,
        task_goal: str,
        global_constraints: str = "",
        use_isolation: bool = True,
    ) -> Dict[str, Any]:
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

        if global_constraints.strip():
            self.replace_global_constraints(global_constraints)

        self.total_tokens = 0
        self.total_latency = 0.0

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
            prompt = self._build_agent_prompt(
                composed_context,
                trajectory,
                step,
                current_observation,
                self.global_constraints,
                use_isolation=use_isolation,
            )
            prompt_metadata = self._build_prompt_metadata(
                prompt=prompt,
                observation=current_observation,
                trajectory=trajectory,
                global_constraints=self.global_constraints,
                use_isolation=use_isolation,
            )
            llm_output = ""
            llm_retries = 0
            llm_error = "unknown"

            while True:
                llm_output, token_count, latency_ms = self._call_agent_llm(prompt, current_observation)
                self.total_tokens += token_count
                self.total_latency += latency_ms
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
                    "prompt": prompt,
                    "prompt_metadata": prompt_metadata,
                }

                if done_by_observation:
                    success = True
                    final_answer = inferred_answer
                    empty_event["completion_inferred"] = True
                    empty_event["completion_reason"] = inferred_reason

                trajectory.append(empty_event)
                break

            action = self._parse_action(llm_output)
            state_signature_before = self._get_environment_state_signature(current_observation)
            if action.get("type") == "finish":
                if self.enable_finish_gate:
                    allow_finish, finish_reason = self._should_accept_finish_action(
                        task_goal=normalized_goal,
                        step=step,
                        current_observation=current_observation,
                        trajectory=trajectory,
                    )
                    finish_gate_result: Dict[str, Any] = {
                        "enabled": True,
                        "allowed": allow_finish,
                        "reason": finish_reason,
                    }
                else:
                    allow_finish = True
                    finish_reason = "finish_gate_disabled"
                    finish_gate_result = {
                        "enabled": False,
                        "allowed": True,
                        "reason": finish_reason,
                    }
                if not allow_finish:
                    if self.trace_enabled:
                        print(
                            f"[TRACE] step={step} finish_rejected "
                            f"reason={finish_reason} pre_obs={self._observation_preview(current_observation)}"
                        )
                    trajectory.append(
                        {
                            "step": step,
                            "llm_output": llm_output,
                            "action": action,
                            "pre_observation": current_observation,
                            "prompt": prompt,
                            "prompt_metadata": prompt_metadata,
                            "finish_rejected": True,
                            "finish_reject_reason": finish_reason,
                            "finish_gate_result": finish_gate_result,
                            "observation": "Model finish rejected due to insufficient completion evidence.",
                            "state_signature_before": state_signature_before,
                            "state_signature_after": state_signature_before,
                            "state_changed": False,
                        }
                    )
                    continue

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
                        "prompt": prompt,
                        "prompt_metadata": prompt_metadata,
                        "finish_gate_result": finish_gate_result,
                        "observation": "Task marked completed by model.",
                        "state_signature_before": state_signature_before,
                        "state_signature_after": state_signature_before,
                        "state_changed": False,
                    }
                )
                break

            violation_error = self._evaluate_security_policy(action) if self.enable_static_interceptor else None
            if violation_error is not None:
                interceptor_result = {
                    "enabled": True,
                    "blocked": True,
                    "block_reason": violation_error,
                    "risk_class": "static_policy_violation",
                }
                env_result = {
                    "done": False,
                    "error": violation_error,
                }
            else:
                interceptor_result = {
                    "enabled": self.enable_static_interceptor,
                    "blocked": False,
                    "block_reason": "",
                    "risk_class": "",
                }
                env_result = self._execute_action(action)
            post_observation = self._get_environment_observation()
            state_signature_after = self._get_environment_state_signature(post_observation)
            if self.trace_enabled:
                self._print_action_observation_trace(step, action, current_observation, post_observation, env_result)

            step_event: Dict[str, Any] = {
                "step": step,
                "llm_output": llm_output,
                "action": action,
                "pre_observation": current_observation,
                "post_observation": post_observation,
                "prompt": prompt,
                "prompt_metadata": prompt_metadata,
                "finish_gate_result": {
                    "enabled": self.enable_finish_gate,
                    "allowed": True,
                    "reason": "not_finish_action",
                },
                "interceptor_result": interceptor_result,
                "observation": env_result,
                "state_signature_before": state_signature_before,
                "state_signature_after": state_signature_after,
                "state_changed": state_signature_before != state_signature_after,
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
            "total_tokens": self.total_tokens,
            "total_latency": self.total_latency,
            "trajectory": trajectory,
        }

    def _should_accept_finish_action(
        self,
        task_goal: str,
        step: int,
        current_observation: Dict[str, Any],
        trajectory: List[Dict[str, Any]],
    ) -> Tuple[bool, str]:
        """Gate model-proposed finish to reduce step-1 false positives."""

        done_by_observation, _, completion_reason = self._infer_completion_from_observation(
            task_goal,
            current_observation,
        )
        if done_by_observation:
            return True, f"observation_evidence:{completion_reason}"

        if step <= 1:
            return False, "step_too_early_without_evidence"

        for event in trajectory:
            if not isinstance(event, dict):
                continue

            action_obj = event.get("action")
            if not isinstance(action_obj, dict):
                continue

            action_type = str(action_obj.get("type", "")).strip().lower()
            if action_type in {"", "noop", "think", "finish"}:
                continue
            return True, "has_meaningful_action_history"

        return False, "no_meaningful_action_history"

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
        observation: Dict[str, Any],
        global_constraints: str,
        use_isolation: bool = True,
    ) -> str:
        """Build iterative prompt for action generation."""

        if self.history_mode == "summary":
            recent_action_history = self._summarize_action_history_for_prompt(trajectory)
        else:
            recent_action_history = self._build_action_history_for_prompt(
                trajectory,
                max_items=self.action_history_limit,
            )
        dead_end_lines = (
            self._build_dead_end_memory_for_prompt(trajectory)
            if self.enable_dead_end_memory
            else []
        )
        if use_isolation:
            prompt_action_history = recent_action_history
        else:
            legacy_constraints = global_constraints.strip()
            prompt_action_history = recent_action_history
            if legacy_constraints:
                legacy_seed = {
                    "step": 0,
                    "action": "GLOBAL_CONSTRAINTS",
                    "target": "",
                    "value": legacy_constraints,
                    "done": False,
                    "error": "",
                }
                prompt_action_history = [legacy_seed, *recent_action_history][-8:]

        trajectory_text = json.dumps(prompt_action_history, ensure_ascii=True)
        global_state_text = self._build_global_state_for_prompt(composed_context)
        observation_block = self._format_observation_for_prompt(observation)
        prompt_prefix = (
            f"Step: {step}\n\n"
            "<Critical_Task_Constraints>\n"
            "- Output MUST be exactly one JSON object, with no markdown code fence.\n"
            "- Decide one next action ONLY from: goto, type, fill, click, press, wait, finish.\n"
            "- Prefer observation IDs as target (e.g. [12]).\n"
            "- Keep URL in field 'url' for goto action.\n"
            "- Keep final completion text in field 'final_answer' for finish action.\n"
            "- Do NOT use finish unless completion is verifiable from observation evidence.\n"
            "- JSON schema: {\"action\": str, \"target\": str, \"value\": str, \"url\": str, \"final_answer\": str}.\n"
            "- Leave irrelevant fields as empty string.\n"
            "</Critical_Task_Constraints>\n\n"
        )

        global_state_block = (
            "<Global_State>\n"
            f"{global_state_text}\n"
            "</Global_State>\n\n"
            "<Current_Observation>\n"
            f"{observation_block}\n"
            "</Current_Observation>\n\n"
            "<Action_History_JSON>\n"
            f"{trajectory_text}\n\n"
            "</Action_History_JSON>\n\n"
            "Return exactly one JSON object only.\n"
        )
        repeated_constraints_block = ""
        if self.repeat_constraints_each_step and global_constraints.strip():
            repeated_constraints_block = (
                "<Repeated_Global_Constraints>\n"
                f"{global_constraints.strip()}\n"
                "</Repeated_Global_Constraints>\n\n"
            )

        if use_isolation:
            constraints_block = global_constraints.strip() if global_constraints.strip() else "None"
            return (
                prompt_prefix
                + "<User_Global_Constraints>\n"
                + "The following constraints are CRITICAL and must be strictly followed regardless of the action history:\n"
                + f"{constraints_block}\n"
                + "</User_Global_Constraints>\n\n"
                + repeated_constraints_block
                + "<Explored_Dead_Ends>\n"
                + self._format_dead_ends_for_prompt(dead_end_lines)
                + "\n</Explored_Dead_Ends>\n\n"
                + global_state_block
            )

        return prompt_prefix + repeated_constraints_block + global_state_block

    def _format_observation_for_prompt(self, observation: Dict[str, Any] | str) -> str:
        """Format structured observation into a prompt-sized textual block."""

        if isinstance(observation, dict):
            a11y_nodes = observation.get("a11y_nodes")
            if isinstance(a11y_nodes, list) and a11y_nodes:
                return self._format_a11y_observation_for_prompt(a11y_nodes)
            observation_text = str(observation.get("observation_text", "")).strip()
        else:
            observation_text = str(observation).strip()

        cleaned = observation_text.strip()
        if not cleaned:
            return "No environment observation available."

        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if not lines:
            return "No environment observation available."

        scored_lines: List[Tuple[int, int, str]] = []
        for index, line in enumerate(lines):
            scored_lines.append((self._score_observation_line(line), index, line))

        scored_lines.sort(key=lambda item: (-item[0], item[1]))
        selected_candidates = scored_lines[: self.prompt_observation_line_limit]
        selected_candidates.sort(key=lambda item: item[1])
        selected_lines = [item[2] for item in selected_candidates]
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

    def _format_a11y_observation_for_prompt(self, a11y_nodes: List[Dict[str, Any]]) -> str:
        """Rank and clip structured accessibility nodes for prompting."""

        if not a11y_nodes:
            return "No environment observation available."

        scored_nodes: List[Tuple[int, int, Dict[str, Any]]] = []
        for index, node in enumerate(a11y_nodes):
            if not isinstance(node, dict):
                continue
            scored_nodes.append((self._score_a11y_node(node), index, node))

        scored_nodes.sort(key=lambda item: (-item[0], item[1]))
        selected_candidates = scored_nodes[: self.prompt_observation_line_limit]
        selected_candidates.sort(key=lambda item: item[1])

        lines: List[str] = []
        for _, _, node in selected_candidates:
            node_id = node.get("id", "?")
            role = str(node.get("role", "element")).strip() or "element"
            name = str(node.get("text", node.get("name", ""))).strip() or "<no-name>"
            selector = str(node.get("selector", "")).strip()
            disabled = bool(node.get("disabled", False))
            hidden = bool(node.get("hidden", False))
            status_parts: List[str] = []
            if disabled:
                status_parts.append("disabled")
            if hidden:
                status_parts.append("hidden")
            status_suffix = f" [{' '.join(status_parts)}]" if status_parts else ""
            selector_suffix = f" selector='{selector}'" if selector else ""
            lines.append(f"[{node_id}] {role} '{name}'{selector_suffix}{status_suffix}")

        clipped_text = "\n".join(lines)
        char_truncated = False
        if len(clipped_text) > self.prompt_observation_char_limit:
            clipped_text = clipped_text[: self.prompt_observation_char_limit].rstrip()
            char_truncated = True

        omitted_count = max(len(a11y_nodes) - len(selected_candidates), 0)
        if omitted_count > 0:
            clipped_text = f"{clipped_text}\n... (+{omitted_count} more accessibility nodes omitted)"
        if char_truncated:
            clipped_text = f"{clipped_text}\n... (truncated for prompt size)"
        return clipped_text

    @staticmethod
    def _score_a11y_node(node: Dict[str, Any]) -> int:
        """Score one accessibility node by task relevance."""

        role = str(node.get("role", "")).lower()
        text = str(node.get("text", node.get("name", ""))).lower()
        score = 0

        if role == "textbox":
            score += 140
        if role in {"searchbox", "combobox"}:
            score += 130
        if role in {"button", "link"}:
            score += 100
        if role in {"checkbox", "radio", "tab", "menuitem"}:
            score += 80
        if "search" in text:
            score += 20
        if "submit" in text or "confirm" in text:
            score += 10
        return score

    @staticmethod
    def _score_observation_line(line: str) -> int:
        """Score one observation line by interaction importance."""

        normalized = line.lower()
        score = 0

        if "textarea" in normalized:
            score += 120
        if "input" in normalized:
            score += 100
        if "button" in normalized or "role='button" in normalized:
            score += 80
        if "select" in normalized:
            score += 60
        if "selector='" in normalized:
            score += 20
        if normalized.startswith("["):
            score += 10

        return score

    def _build_action_history_for_prompt(
        self,
        trajectory: List[Dict[str, Any]],
        max_items: int = 8,
    ) -> List[Dict[str, Any]]:
        """Build compact action history and keep recent causal events."""

        compact_history: List[Dict[str, Any]] = []
        for item in trajectory:
            if not isinstance(item, dict):
                continue

            if "step" not in item:
                continue

            action_obj = item.get("action")
            action_type = ""
            action_target = ""
            action_value = ""
            if isinstance(action_obj, dict):
                action_type = str(action_obj.get("type", ""))
                action_target = str(action_obj.get("target", ""))
                action_value = str(action_obj.get("value", ""))

            env_obs = item.get("observation")
            env_error = ""
            env_done = False
            if isinstance(env_obs, dict):
                env_error = str(env_obs.get("error", ""))
                env_done = bool(env_obs.get("done", False))

            compact_history.append(
                {
                    "step": item.get("step"),
                    "action": action_type,
                    "target": action_target,
                    "value": action_value,
                    "done": env_done,
                    "error": env_error,
                }
            )

        return compact_history[-max_items:]

    def _summarize_action_history_for_prompt(self, trajectory: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Compress long history into a compact summary for ablation baselines."""

        step_events = [item for item in trajectory if isinstance(item, dict) and "step" in item]
        if not step_events:
            return []

        action_counts: Dict[str, int] = {}
        last_failure_signal = ""
        for item in step_events:
            action_obj = item.get("action")
            if isinstance(action_obj, dict):
                action_type = str(action_obj.get("type", "")).strip().lower() or "unknown"
                action_counts[action_type] = action_counts.get(action_type, 0) + 1

            if bool(item.get("finish_rejected")):
                last_failure_signal = str(item.get("finish_reject_reason", "")).strip() or last_failure_signal

            observation = item.get("observation")
            if isinstance(observation, dict):
                env_error = str(observation.get("error", "")).strip()
                if env_error:
                    last_failure_signal = env_error

        return [
            {
                "step_count": len(step_events),
                "action_counts": action_counts,
                "last_failure_signal": last_failure_signal,
            }
        ]

    def _build_dead_end_memory_for_prompt(
        self,
        trajectory: List[Dict[str, Any]],
        max_items: int = 3,
    ) -> List[str]:
        """Summarize truncated failure paths so the agent remembers explored dead ends."""

        step_events = [item for item in trajectory if isinstance(item, dict) and "step" in item]
        if len(step_events) <= max_items:
            return []

        dead_end_summaries: List[str] = []
        seen_signatures: set[Tuple[str, str, str]] = set()
        older_events = step_events[:-max_items]

        for event in older_events:
            summary = self._summarize_dead_end_event(event)
            if summary is None:
                continue

            signature = (
                summary["action"].lower(),
                summary["target"].lower(),
                summary["reason"].lower(),
            )
            if signature in seen_signatures:
                continue

            seen_signatures.add(signature)
            dead_end_summaries.append(summary["text"])

        return dead_end_summaries[-self.dead_end_limit :]

    def _summarize_dead_end_event(self, event: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Convert one older failed event into a compact causal summary."""

        action_obj = event.get("action")
        action_type = ""
        action_target = ""
        if isinstance(action_obj, dict):
            action_type = str(action_obj.get("type", "")).strip()
            action_target = str(action_obj.get("target", "")).strip()

        if str(event.get("error", "")).strip() == "empty_llm_response":
            llm_reason = str(event.get("llm_error", "")).strip() or "empty_llm_response"
            return {
                "action": "llm_request",
                "target": "",
                "reason": self._normalize_dead_end_reason(llm_reason),
                "text": f"LLM request failed with {llm_reason}.",
            }

        if bool(event.get("finish_rejected")):
            finish_reason = str(event.get("finish_reject_reason", "")).strip() or "finish_rejected"
            return {
                "action": action_type or "finish",
                "target": action_target,
                "reason": self._normalize_dead_end_reason(finish_reason),
                "text": f"Tried finish {self._render_dead_end_target(action_target)}, but it was rejected: {finish_reason}.",
            }

        observation = event.get("observation")
        if isinstance(observation, dict):
            env_error = str(observation.get("error", "")).strip()
            if env_error:
                return {
                    "action": action_type,
                    "target": action_target,
                    "reason": self._normalize_dead_end_reason(env_error),
                    "text": f"Tried {action_type or 'action'} {self._render_dead_end_target(action_target)}, got error: {env_error}.",
                }

        pre_observation_text = ""
        post_observation_text = ""
        pre_observation = event.get("pre_observation")
        post_observation = event.get("post_observation")
        if isinstance(pre_observation, dict):
            pre_observation_text = str(pre_observation.get("observation_text", "")).strip()
        if isinstance(post_observation, dict):
            post_observation_text = str(post_observation.get("observation_text", "")).strip()

        if (
            action_type.lower() in {"click", "press", "goto", "type", "fill"}
            and pre_observation_text
            and post_observation_text
            and pre_observation_text == post_observation_text
        ):
            return {
                "action": action_type,
                "target": action_target,
                "reason": "no_state_change",
                "text": (
                    f"Tried {action_type} {self._render_dead_end_target(action_target)}, "
                    "but the page state did not change."
                ),
            }

        return None

    @staticmethod
    def _normalize_dead_end_reason(reason: str) -> str:
        """Normalize one failure reason for deduplication."""

        cleaned = re.sub(r"\s+", " ", reason.strip().lower())
        return cleaned[:160]

    @staticmethod
    def _render_dead_end_target(target: str) -> str:
        """Render one optional action target for prompt summaries."""

        return target if target else "<no-target>"

    @staticmethod
    def _format_dead_ends_for_prompt(dead_end_lines: List[str]) -> str:
        """Serialize dead-end summaries into the prompt slot."""

        if not dead_end_lines:
            return "None"
        return "\n".join(f"- {line}" for line in dead_end_lines)

    @staticmethod
    def _build_global_state_for_prompt(composed_context: str) -> str:
        """Keep global constraints/context isolated from action history."""

        return composed_context.strip() if composed_context.strip() else "No global state available."

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

        cleaned_output = self._strip_markdown_fence(llm_output)

        action_from_json = self._parse_action_from_json(cleaned_output)
        if action_from_json is not None:
            return action_from_json

        final_match = re.search(
            r"<final-answer(?:\s+[^>]*)?>\s*(.*?)\s*</final-answer>",
            cleaned_output,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if final_match:
            return {
                "type": "finish",
                "content": final_match.group(1).strip(),
                "raw": cleaned_output,
            }

        action_match = re.search(
            r"<action(?:\s+[^>]*)?>\s*(.*?)\s*</action>",
            cleaned_output,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not action_match:
            return {"type": "think", "raw": cleaned_output}

        action_type = _normalize_space(action_match.group(1)).lower()
        target_match = re.search(
            r"<target(?:\s+[^>]*)?>\s*(.*?)\s*</target>",
            cleaned_output,
            flags=re.IGNORECASE | re.DOTALL,
        )
        value_match = re.search(
            r"<value(?:\s+[^>]*)?>\s*(.*?)\s*</value>",
            cleaned_output,
            flags=re.IGNORECASE | re.DOTALL,
        )
        url_match = re.search(
            r"<url(?:\s+[^>]*)?>\s*(.*?)\s*</url>",
            cleaned_output,
            flags=re.IGNORECASE | re.DOTALL,
        )

        target = target_match.group(1).strip() if target_match else ""
        value = value_match.group(1).strip() if value_match else ""
        url = url_match.group(1).strip() if url_match else ""

        if action_type in {"finish", "done", "complete", "completed"}:
            return {
                "type": "finish",
                "content": value or target,
                "raw": cleaned_output,
            }

        if action_type in {"goto", "navigate"} and url and not target and not value:
            target = url

        parsed_action: AgentAction = {
            "type": action_type if action_type else "noop",
            "target": target,
            "value": value,
            "raw": cleaned_output,
        }
        if url:
            parsed_action["content"] = url
        return parsed_action

    @staticmethod
    def _strip_markdown_fence(text: str) -> str:
        """Remove surrounding markdown code fence when model wraps JSON/XML."""

        cleaned = text.strip()
        if not cleaned.startswith("```"):
            return cleaned

        fence_match = re.match(r"^```[a-zA-Z0-9_-]*\s*(.*?)\s*```$", cleaned, flags=re.DOTALL)
        if not fence_match:
            return cleaned
        return fence_match.group(1).strip()

    def _parse_action_from_json(self, text: str) -> Optional[AgentAction]:
        """Parse action from strict/near-strict JSON object output."""

        candidate = text.strip()
        if not candidate:
            return None

        if not (candidate.startswith("{") and candidate.endswith("}")):
            first_brace = candidate.find("{")
            last_brace = candidate.rfind("}")
            if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
                return None
            candidate = candidate[first_brace : last_brace + 1]

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None

        if not isinstance(parsed, dict):
            return None

        action_type = str(parsed.get("action", parsed.get("type", ""))).strip().lower()
        target = str(parsed.get("target", "")).strip()
        value = str(parsed.get("value", "")).strip()
        url = str(parsed.get("url", "")).strip()
        final_answer = str(parsed.get("final_answer", parsed.get("content", ""))).strip()

        if final_answer:
            return {
                "type": "finish",
                "content": final_answer,
                "raw": text,
            }

        if action_type in {"finish", "done", "complete", "completed"}:
            return {
                "type": "finish",
                "content": final_answer or value or target,
                "raw": text,
            }

        if not action_type:
            return None

        if action_type in {"goto", "navigate"} and url and not target and not value:
            target = url

        result: AgentAction = {
            "type": action_type,
            "target": target,
            "value": value,
            "raw": text,
        }
        if url:
            result["content"] = url
        return result

    def _legacy_execute_action_unchecked(self, action: AgentAction) -> Dict[str, Any]:
        """Legacy unchecked action executor kept for debugging/reference."""

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

    def _execute_action(self, action: AgentAction) -> Dict[str, Any]:
        """Execute one action against injected environment adapter."""

        try:
            violation_error = self._evaluate_security_policy(action) if self.enable_static_interceptor else None
            if violation_error is not None:
                return {
                    "done": False,
                    "error": violation_error,
                }

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

    def _evaluate_security_policy(self, action: AgentAction) -> Optional[str]:
        """Return a violation string when an action breaks the static security policy."""

        action_type = str(action.get("type", "")).strip().lower()
        url = str(action.get("url", action.get("content", ""))).strip()
        target = str(action.get("target", "")).strip()
        value = str(action.get("value", "")).strip()

        if action_type in {"goto", "navigate"}:
            allowed_domains = self.security_policy.get("allowed_domains", [])
            if allowed_domains:
                parsed = urlsplit(url or target or value)
                netloc = parsed.netloc.strip().lower()
                if ":" in netloc:
                    netloc = netloc.split(":", 1)[0]

                if not netloc:
                    return "Security Violation: Domain not in allowed_domains list."

                is_allowed = False
                for allowed_domain in allowed_domains:
                    normalized_domain = str(allowed_domain).strip().lower()
                    if not normalized_domain:
                        continue
                    if netloc == normalized_domain or netloc.endswith(f".{normalized_domain}"):
                        is_allowed = True
                        break

                if not is_allowed:
                    return "Security Violation: Domain not in allowed_domains list."

        normalized_target = target.lower()
        normalized_value = value.lower()
        for keyword in self.security_policy.get("high_risk_keywords", []):
            normalized_keyword = str(keyword).strip().lower()
            if not normalized_keyword:
                continue
            if normalized_keyword in normalized_target or normalized_keyword in normalized_value:
                return f"Security Violation: Action contains high-risk keyword '{keyword}'."

        return None

    def _build_prompt_metadata(
        self,
        prompt: str,
        observation: Dict[str, Any],
        trajectory: List[Dict[str, Any]],
        global_constraints: str,
        use_isolation: bool,
    ) -> Dict[str, Any]:
        """Capture prompt composition statistics for benchmark reports."""

        if self.history_mode == "summary":
            history_payload: Any = self._summarize_action_history_for_prompt(trajectory)
        else:
            history_payload = self._build_action_history_for_prompt(
                trajectory,
                max_items=self.action_history_limit,
            )
        dead_end_lines = (
            self._build_dead_end_memory_for_prompt(trajectory)
            if self.enable_dead_end_memory
            else []
        )
        observation_block = self._format_observation_for_prompt(observation)
        return {
            "total_chars": len(prompt),
            "total_tokens_est": max(len(prompt) // 4, 1),
            "constraint_block_chars": len(global_constraints.strip()) if use_isolation else 0,
            "repeated_constraint_chars": len(global_constraints.strip()) if self.repeat_constraints_each_step else 0,
            "dead_end_block_chars": len("\n".join(dead_end_lines)),
            "history_block_chars": len(json.dumps(history_payload, ensure_ascii=True)),
            "observation_block_chars": len(observation_block),
            "history_mode": self.history_mode,
            "use_isolation": use_isolation,
        }

    def _get_environment_state_signature(self, observation: Dict[str, Any]) -> str:
        """Return a stable signature for the current environment state."""

        signature = str(observation.get("state_signature", "")).strip()
        if signature:
            return signature

        try:
            if hasattr(self.environment, "get_state_signature") and callable(
                getattr(self.environment, "get_state_signature")
            ):
                candidate = getattr(self.environment, "get_state_signature")()
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
        except Exception:
            pass

        digest_source = json.dumps(
            {
                "url": observation.get("url", ""),
                "title": observation.get("title", ""),
                "observation_text": observation.get("observation_text", ""),
                "elements": observation.get("elements", []),
                "a11y_nodes": observation.get("a11y_nodes", []),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        return hashlib.sha1(digest_source.encode("utf-8")).hexdigest()

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

    def _call_llm_api(self, prompt: str) -> Tuple[str, int, float]:
        """Unified LLM call shell.

        You can fill api_url/model/payload details according to your provider.
        """

        payload: Dict[str, Any] = {"prompt": prompt}
        if self.model:
            payload["model"] = self.model
        return _safe_llm_request(self.api_url, self.headers, payload)

    def _call_agent_llm(self, prompt: str, observation: Dict[str, Any]) -> Tuple[str, int, float]:
        """Call the action model, optionally using richer observation payloads."""

        return self._call_llm_api(prompt)


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


def _safe_llm_request(
    api_url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
) -> Tuple[str, int, float]:
    """Perform a defensive LLM HTTP call and return text, token count, and latency."""

    global _LAST_LLM_ERROR

    if not api_url.strip():
        _LAST_LLM_ERROR = "empty_api_url"
        return "", 0, 0.0

    timeout_seconds = _resolve_llm_timeout_seconds()

    started_at = time.time()
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        _LAST_LLM_ERROR = f"request_exception:{exc.__class__.__name__}"
        latency_ms = (time.time() - started_at) * 1000.0
        return "", 0, latency_ms

    try:
        data = response.json()
    except ValueError:
        _LAST_LLM_ERROR = "invalid_json_response"
        latency_ms = (time.time() - started_at) * 1000.0
        return "", 0, latency_ms

    latency_ms = (time.time() - started_at) * 1000.0
    total_tokens = _extract_total_tokens_from_llm_json(data)
    extracted = _extract_text_from_llm_json(data)
    if not extracted.strip():
        _LAST_LLM_ERROR = "empty_text_output"
        return "", total_tokens, latency_ms

    _LAST_LLM_ERROR = ""
    return extracted, total_tokens, latency_ms


def _extract_total_tokens_from_llm_json(data: Any) -> int:
    """Best-effort extraction of total token usage from common LLM JSON responses."""

    if not isinstance(data, dict):
        return 0

    usage = data.get("usage")
    if not isinstance(usage, dict):
        return 0

    total_tokens = usage.get("total_tokens", 0)
    if isinstance(total_tokens, int):
        return max(total_tokens, 0)

    try:
        return max(int(total_tokens), 0)
    except (TypeError, ValueError):
        return 0


def _resolve_llm_timeout_seconds(default_timeout: float = 60.0) -> float:
    """Resolve request timeout from environment with defensive fallback."""

    raw_timeout = os.getenv("CER_LLM_TIMEOUT_SECONDS", "").strip()
    if not raw_timeout:
        return default_timeout

    try:
        parsed_timeout = float(raw_timeout)
    except ValueError:
        return default_timeout

    if parsed_timeout <= 0:
        return default_timeout
    return parsed_timeout


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


def _extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Extract first JSON object from raw model text, tolerating wrappers."""

    cleaned = text.strip()
    if not cleaned:
        return None

    # Strip a surrounding markdown code fence if present.
    fence_match = re.match(r"^```[a-zA-Z0-9_-]*\s*(.*?)\s*```$", cleaned, flags=re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    candidates = [cleaned]
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(cleaned[first_brace : last_brace + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    return None


def _normalize_space(text: str) -> str:
    """Normalize all whitespace runs to a single space."""

    return re.sub(r"\s+", " ", text).strip()


def _normalize_multiline(text: str) -> str:
    """Normalize multiline text while preserving line boundaries."""

    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return "\n".join(lines)
