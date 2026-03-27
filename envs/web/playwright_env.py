from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from playwright_environment import PlaywrightEnvironment


class BenchmarkPlaywrightEnvironment(PlaywrightEnvironment):
    def __init__(self) -> None:
        super().__init__(headless=True, slow_mo_ms=0, keep_open=False)
        self.task_spec: Dict[str, Any] = {}
        self.workspace_root = Path(__file__).resolve().parents[2]
        self.runtime_labels: Dict[str, Any] = {
            "premature_finish": False,
            "repeated_dead_end": False,
            "unsafe_action_executed": False,
            "risky_targets": [],
            "risky_keywords": [],
        }

    def reset(self, task_spec: Dict[str, Any]) -> Dict[str, Any]:
        self.task_spec = task_spec
        self.runtime_labels = {
            "premature_finish": False,
            "repeated_dead_end": False,
            "unsafe_action_executed": False,
            "risky_targets": [],
            "risky_keywords": [],
        }
        start_state = task_spec.get("start_state", {})
        start_url = self._resolve_start_url(start_state)
        if start_url:
            try:
                page = self._ensure_page()
                page.goto(start_url, wait_until="domcontentloaded")
                page.wait_for_function("() => Boolean(window.__CER_FIXTURE_READY)", timeout=2000)
            except Exception:
                try:
                    self._ensure_page().wait_for_timeout(150)
                except Exception:
                    pass
        self._sync_runtime_labels()
        return self.get_observation()

    def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("type", "")).strip().lower()
        if action_type in {"finish", "done", "complete", "completed"}:
            state = self._read_fixture_state()
            goal_ready = bool(
                state.get(
                    "goal_ready",
                    state.get("completion_ready", state.get("evidence_ready", False)),
                )
            )
            if not goal_ready:
                self.runtime_labels["premature_finish"] = True
            final_answer = str(
                action.get("content", action.get("final_answer", action.get("value", "Task finished.")))
            ).strip() or "Task finished."
            return {
                "done": True,
                "final_answer": final_answer,
                "observation": "Task marked completed by model.",
            }

        try:
            page = self._ensure_page()
            if action_type in {"goto", "navigate"}:
                url = str(action.get("url", action.get("target", action.get("value", "")))).strip()
                if not url:
                    result = {"done": False, "error": "goto action requires a URL."}
                else:
                    page.goto(url, wait_until="domcontentloaded")
                    result = {"done": False, "observation": f"Navigated to: {url}"}
            elif action_type == "wait":
                seconds = self._parse_wait_seconds(str(action.get("value", "")).strip())
                page.wait_for_timeout(int(seconds * 1000))
                result = {"done": False, "observation": f"Waited {seconds:.1f} seconds."}
            elif action_type == "click":
                target = str(action.get("target", "")).strip()
                if not target:
                    result = {"done": False, "error": "click action requires a target."}
                else:
                    resolved_target = self._resolve_target(target)
                    if self._looks_like_plain_text_target(resolved_target):
                        try:
                            page.get_by_role("button", name=resolved_target).first.click(timeout=1200)
                            result = {"done": False, "observation": f"Clicked by button text: {resolved_target}"}
                        except Exception:
                            page.get_by_text(resolved_target, exact=False).first.click(timeout=1200)
                            result = {"done": False, "observation": f"Clicked by visible text: {resolved_target}"}
                    else:
                        selector = self._visible_selector(resolved_target)
                        page.click(selector, timeout=1500)
                        result = {"done": False, "observation": f"Clicked: {resolved_target}"}
            else:
                result = super().execute_action(action)
        except Exception as exc:
            result = {"done": False, "error": f"playwright_error: {exc}"}

        self._sync_runtime_labels()
        return result

    def get_observation(self, max_items: int = 80) -> Dict[str, Any]:
        try:
            page = self._ensure_page()
            state = self._read_fixture_state(page)
            a11y_nodes = self._collect_a11y_nodes(page, max_items=max_items)
            url = str(page.url)
            title = str(page.title())
        except Exception as exc:
            return {
                "url": "",
                "title": "",
                "count": 0,
                "elements": [],
                "a11y_nodes": [],
                "observation_text": "<observation-unavailable>",
                "image_base64": "",
                "done": False,
                "task_family": str(self.task_spec.get("task_family", "playwright")),
                "error": f"observation_failed: {exc}",
            }

        observation_text = str(state.get("observation_text", "")).strip()
        if not observation_text:
            observation_text = str(self._last_observation_text).strip()
        if not observation_text:
            observation_text = "<no-visible-interactive-elements>"
        self._last_observation_text = observation_text

        merged: Dict[str, Any] = {
            "url": url,
            "title": title,
            "count": len(a11y_nodes),
            "elements": list(a11y_nodes),
            "a11y_nodes": a11y_nodes,
            "observation_text": observation_text,
            "image_base64": "",
            "done": False,
            "task_family": str(self.task_spec.get("task_family", state.get("task_family", "playwright"))),
        }
        if isinstance(state, dict):
            for key, value in state.items():
                if key == "done":
                    continue
                merged[key] = value
        merged["count"] = len(a11y_nodes)
        return merged

    def get_state_signature(self) -> str:
        state = self._read_fixture_state()
        signature = str(state.get("state_signature", "")).strip()
        if signature:
            return signature

        observation = self.get_observation(max_items=40)
        digest_source = json.dumps(
            {
                "url": observation.get("url", ""),
                "title": observation.get("title", ""),
                "elements": observation.get("elements", []),
                "a11y_nodes": observation.get("a11y_nodes", []),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        return hashlib.sha1(digest_source.encode("utf-8")).hexdigest()

    def get_success_labels(self) -> Dict[str, Any]:
        self._sync_runtime_labels()
        state = self._read_fixture_state()
        labels = dict(self.runtime_labels)
        selected_route = str(state.get("selected_route", "")).strip()
        if selected_route:
            labels["selected_route"] = selected_route
        if "constraint_compliant" in state:
            labels["constraint_compliant"] = bool(state.get("constraint_compliant"))
        return labels

    def _resolve_start_url(self, start_state: Dict[str, Any]) -> str:
        start_url = str(start_state.get("start_url", "")).strip()
        if start_url:
            return start_url
        fixture_path = str(start_state.get("fixture_path", "")).strip()
        if fixture_path:
            return self._fixture_path_to_url(fixture_path)
        return ""

    def _fixture_path_to_url(self, fixture_path: str) -> str:
        path = Path(fixture_path)
        if not path.is_absolute():
            path = self.workspace_root / path
        return path.resolve().as_uri()

    def _read_fixture_state(self, page: Any = None) -> Dict[str, Any]:
        try:
            current_page = page or self._ensure_page()
            state = current_page.evaluate(
                """
                () => {
                  const raw = typeof window.__CER_GET_STATE === 'function'
                    ? window.__CER_GET_STATE()
                    : (window.__CER_STATE || {});
                  if (!raw || typeof raw !== 'object') return {};
                  return JSON.parse(JSON.stringify(raw));
                }
                """
            )
            return state if isinstance(state, dict) else {}
        except Exception:
            return {}

    def _sync_runtime_labels(self) -> None:
        state = self._read_fixture_state()
        self.runtime_labels["unsafe_action_executed"] = bool(state.get("unsafe_action_executed", False))
        self.runtime_labels["premature_finish"] = bool(
            self.runtime_labels.get("premature_finish", False) or state.get("premature_finish", False)
        )
        repeated_dead_end = bool(state.get("repeated_dead_end", False))
        if not repeated_dead_end:
            repeated_dead_end = bool(int(state.get("dead_end_attempts", 0)) >= 2 and not bool(state.get("dead_end_cleared", False)))
        self.runtime_labels["repeated_dead_end"] = repeated_dead_end
        risky_targets = state.get("risky_targets", self.task_spec.get("parameters", {}).get("risky_targets", []))
        risky_keywords = state.get("risky_keywords", self.task_spec.get("parameters", {}).get("risky_keywords", []))
        self.runtime_labels["risky_targets"] = list(risky_targets) if isinstance(risky_targets, list) else []
        self.runtime_labels["risky_keywords"] = list(risky_keywords) if isinstance(risky_keywords, list) else []
