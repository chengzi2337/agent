from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin, urlsplit

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
                url = str(action.get("url", action.get("content", action.get("target", action.get("value", ""))))).strip()
                if not url:
                    result = {"done": False, "error": "goto action requires a URL."}
                else:
                    normalized_url = self._normalize_navigation_url(page, url)
                    page.goto(normalized_url, wait_until="domcontentloaded")
                    result = {"done": False, "observation": f"Navigated to: {normalized_url}"}
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
            a11y_nodes.extend(self._build_completion_evidence_nodes(state))
            a11y_nodes = self._assign_observation_ids(a11y_nodes)
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
        derived_observation_text = self._build_task_observation_text(url, title, state)
        if derived_observation_text:
            if observation_text:
                observation_text = f"{observation_text}\n{derived_observation_text}"
            else:
                observation_text = derived_observation_text
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

    def _resolve_target(self, target: str) -> str:
        cleaned = str(target).strip()
        if not cleaned:
            return cleaned

        exact_match = re.match(r"^\[(\d+)\]$", cleaned)
        if exact_match:
            observation_id = int(exact_match.group(1))
            return self._id_to_selector.get(observation_id, cleaned)

        prefixed_match = re.match(r"^\[(\d+)\]\s+", cleaned)
        if prefixed_match:
            observation_id = int(prefixed_match.group(1))
            if observation_id in self._id_to_selector:
                return self._id_to_selector[observation_id]

        selector_match = re.search(r"selector='([^']+)'", cleaned)
        if selector_match:
            return selector_match.group(1).strip()

        named_target_match = re.match(r"^\[\?\]\s+\w+\s+'(.+?)'(?:\s+selector=.*)?$", cleaned)
        if named_target_match:
            return named_target_match.group(1).strip()

        return super()._resolve_target(cleaned)

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
        for flag in ("completion_ready", "goal_ready", "evidence_ready"):
            if flag in state:
                labels[flag] = bool(state.get(flag))
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
            merged_state = state if isinstance(state, dict) else {}
            task_state = self._build_dynamic_task_state(current_page)
            if task_state:
                combined = dict(merged_state)
                combined.update(task_state)
                return combined
            return merged_state
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

    def _build_dynamic_task_state(self, page: Any) -> Dict[str, Any]:
        parameters = self.task_spec.get("parameters", {})
        if not isinstance(parameters, dict):
            return {}

        checks = parameters.get("completion_checks", [])
        has_checks = isinstance(checks, list) and bool(checks)
        risky_targets = parameters.get("risky_targets", [])
        risky_keywords = parameters.get("risky_keywords", parameters.get("high_risk_keywords", []))
        selected_route = self._resolve_selected_route(page, parameters)

        state: Dict[str, Any] = {}
        if has_checks:
            snapshot = self._capture_completion_snapshot(page, checks)
            completion_state = self.evaluate_completion_checks(
                snapshot=snapshot,
                checks=checks,
                completion_mode=str(parameters.get("completion_mode", "all")),
            )
            state.update(completion_state)

        if selected_route:
            state["selected_route"] = selected_route
        if isinstance(risky_targets, list) and risky_targets:
            state["risky_targets"] = [str(item).strip() for item in risky_targets if str(item).strip()]
        if isinstance(risky_keywords, list) and risky_keywords:
            state["risky_keywords"] = [str(item).strip() for item in risky_keywords if str(item).strip()]
        return state

    def _resolve_selected_route(self, page: Any, parameters: Dict[str, Any]) -> str:
        route_checks = parameters.get("route_checks", [])
        if not isinstance(route_checks, list):
            return ""

        snapshot = self._capture_completion_snapshot(page, route_checks)
        results = self.evaluate_completion_checks(snapshot=snapshot, checks=route_checks, completion_mode="any")
        for item in results.get("completion_checks", []):
            if isinstance(item, dict) and bool(item.get("passed", False)):
                return str(item.get("route", item.get("name", ""))).strip()
        return ""

    def _capture_completion_snapshot(self, page: Any, checks: List[Dict[str, Any]]) -> Dict[str, Any]:
        selectors: List[str] = []
        seen: set[str] = set()
        for item in checks:
            if not isinstance(item, dict):
                continue
            selector = str(item.get("selector", "")).strip()
            if not selector or selector in seen:
                continue
            seen.add(selector)
            selectors.append(selector)

        try:
            snapshot = page.evaluate(
                """
                (selectors) => {
                  const normalizeText = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                  const selectorStates = {};
                  for (const selector of selectors || []) {
                    try {
                      const node = document.querySelector(selector);
                      selectorStates[selector] = {
                        exists: Boolean(node),
                        text: node ? normalizeText(node.innerText || node.textContent || '') : '',
                        value: node ? normalizeText(node.value || '') : ''
                      };
                    } catch (_) {
                      selectorStates[selector] = {
                        exists: false,
                        text: '',
                        value: ''
                      };
                    }
                  }
                  return {
                    url: String(window.location.href || ''),
                    title: String(document.title || ''),
                    body_text: normalizeText(document.body ? (document.body.innerText || document.body.textContent || '') : ''),
                    selectors: selectorStates
                  };
                }
                """,
                selectors,
            )
            return snapshot if isinstance(snapshot, dict) else {}
        except Exception:
            return {}

    def _build_task_observation_text(self, url: str, title: str, state: Dict[str, Any]) -> str:
        lines: List[str] = []
        if title:
            lines.append(f"Page title: {title}")
        if url:
            lines.append(f"Current URL: {url}")

        completion_checks = state.get("completion_checks", [])
        if isinstance(completion_checks, list):
            for item in completion_checks[:4]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "check")).strip() or "check"
                expected = str(item.get("expected", "")).strip()
                actual = str(item.get("actual", "")).strip()
                if bool(item.get("passed", False)):
                    detail = actual or expected or "matched"
                    lines.append(f"Completion evidence ready: {name} -> {detail}")
                elif expected:
                    if actual:
                        lines.append(f"Completion evidence pending: {name} expected '{expected}' but currently shows '{actual}'")
                    else:
                        lines.append(f"Completion evidence pending: {name} expects '{expected}'")

        if not lines:
            return ""
        return "\n".join(lines)

    def _build_completion_evidence_nodes(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        nodes: List[Dict[str, Any]] = []
        completion_checks = state.get("completion_checks", [])
        if not isinstance(completion_checks, list):
            return nodes

        for index, item in enumerate(completion_checks[:4], start=1):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "check")).strip() or "check"
            expected = str(item.get("expected", "")).strip()
            actual = str(item.get("actual", "")).strip()
            selector = str(item.get("selector", "")).strip()
            if bool(item.get("passed", False)):
                detail = actual or expected or "matched"
                text = f"Evidence {name}: {detail}"
            elif expected:
                detail = actual or "pending"
                text = f"Pending {name}: expected {expected}; current {detail}"
            else:
                continue
            nodes.append(
                {
                    "id": f"e{index}",
                    "role": "status",
                    "text": text,
                    "selector": selector,
                }
            )
        return nodes

    def _assign_observation_ids(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self._id_to_selector = {}
        annotated: List[Dict[str, Any]] = []
        next_observation_id = 1

        for raw in nodes:
            if not isinstance(raw, dict):
                continue
            node = dict(raw)
            selector = str(node.get("selector", "")).strip()
            role = str(node.get("role", "")).strip().lower()
            if selector and role != "status":
                node["id"] = next_observation_id
                self._id_to_selector[next_observation_id] = selector
                next_observation_id += 1
            annotated.append(node)
        return annotated

    @classmethod
    def _looks_like_relative_page_path(cls, target: str) -> bool:
        cleaned = str(target or "").strip()
        if not cleaned:
            return False
        if cleaned.startswith(("/", "./", "../", "#", "?")):
            return True
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", cleaned) or cleaned.startswith("//"):
            return False

        lowered = cleaned.lower()
        if lowered.endswith((".html", ".htm", ".php", ".asp", ".aspx", ".jsp")):
            return True
        return "." not in cleaned and ":" not in cleaned

    @classmethod
    def _normalize_navigation_url(cls, page: Any, url: str) -> str:
        cleaned = str(url or "").strip()
        if not cleaned:
            return cleaned
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", cleaned):
            return cleaned
        if cleaned.startswith("//"):
            current_scheme = urlsplit(str(getattr(page, "url", "") or "")).scheme or "http"
            return f"{current_scheme}:{cleaned}"
        if cls._looks_like_relative_page_path(cleaned):
            base_url = str(getattr(page, "url", "") or "").strip()
            return urljoin(base_url, cleaned) if base_url else cleaned
        if re.match(r"^(?:localhost|127(?:\.\d{1,3}){3})(?::\d+)?(?:/.*)?$", cleaned, flags=re.IGNORECASE):
            return f"http://{cleaned}"
        return f"http://{cleaned}"

    @staticmethod
    def _normalize_completion_text(value: Any) -> str:
        return " ".join(str(value or "").strip().split()).lower()

    @classmethod
    def evaluate_completion_checks(
        cls,
        snapshot: Dict[str, Any],
        checks: List[Dict[str, Any]],
        completion_mode: str = "all",
    ) -> Dict[str, Any]:
        url = cls._normalize_completion_text(snapshot.get("url", ""))
        title = cls._normalize_completion_text(snapshot.get("title", ""))
        body_text = cls._normalize_completion_text(snapshot.get("body_text", ""))
        selector_states = snapshot.get("selectors", {})
        if not isinstance(selector_states, dict):
            selector_states = {}

        results: List[Dict[str, Any]] = []
        for index, raw in enumerate(checks):
            if not isinstance(raw, dict):
                continue
            check_type = str(raw.get("type", "")).strip().lower()
            selector = str(raw.get("selector", "")).strip()
            expected = str(raw.get("value", raw.get("text", ""))).strip()
            expected_norm = cls._normalize_completion_text(expected)
            selector_state = selector_states.get(selector, {}) if selector else {}
            if not isinstance(selector_state, dict):
                selector_state = {}

            selector_text = str(selector_state.get("text", "")).strip()
            selector_value = str(selector_state.get("value", "")).strip()
            selector_text_norm = cls._normalize_completion_text(selector_text)
            selector_value_norm = cls._normalize_completion_text(selector_value)
            exists = bool(selector_state.get("exists", False))
            passed = False
            actual = ""

            if check_type == "url_contains":
                actual = str(snapshot.get("url", "")).strip()
                passed = bool(expected_norm) and expected_norm in url
            elif check_type == "title_contains":
                actual = str(snapshot.get("title", "")).strip()
                passed = bool(expected_norm) and expected_norm in title
            elif check_type == "body_contains":
                actual = str(snapshot.get("body_text", "")).strip()
                passed = bool(expected_norm) and expected_norm in body_text
            elif check_type == "selector_exists":
                actual = "present" if exists else "missing"
                passed = exists
            elif check_type == "selector_text_contains":
                actual = selector_text
                passed = bool(expected_norm) and expected_norm in selector_text_norm
            elif check_type == "selector_text_equals":
                actual = selector_text
                passed = bool(expected_norm) and selector_text_norm == expected_norm
            elif check_type == "selector_value_contains":
                actual = selector_value
                passed = bool(expected_norm) and expected_norm in selector_value_norm
            elif check_type == "selector_value_equals":
                actual = selector_value
                passed = bool(expected_norm) and selector_value_norm == expected_norm

            results.append(
                {
                    "name": str(raw.get("name", f"check_{index + 1}")).strip() or f"check_{index + 1}",
                    "type": check_type,
                    "selector": selector,
                    "route": str(raw.get("route", "")).strip(),
                    "expected": expected,
                    "actual": actual,
                    "passed": passed,
                }
            )

        normalized_mode = str(completion_mode or "all").strip().lower()
        if not results:
            completion_ready = False
        elif normalized_mode == "any":
            completion_ready = any(bool(item.get("passed", False)) for item in results)
        else:
            completion_ready = all(bool(item.get("passed", False)) for item in results)

        return {
            "completion_ready": completion_ready,
            "goal_ready": completion_ready,
            "evidence_ready": completion_ready,
            "completion_checks": results,
        }

