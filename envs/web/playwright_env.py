from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from playwright_environment import PlaywrightEnvironment


class BenchmarkPlaywrightEnvironment(PlaywrightEnvironment):
    def __init__(self) -> None:
        super().__init__()
        self.task_spec: Dict[str, Any] = {}

    def reset(self, task_spec: Dict[str, Any]) -> Dict[str, Any]:
        self.task_spec = task_spec
        start_state = task_spec.get("start_state", {})
        start_url = str(start_state.get("start_url", "")).strip()
        if start_url:
            self.execute_action({"type": "goto", "url": start_url, "target": "", "value": "", "content": ""})
        return self.get_observation()

    def get_state_signature(self) -> str:
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
        return {
            "premature_finish": False,
            "repeated_dead_end": False,
            "unsafe_action_executed": False,
            "risky_targets": [],
            "risky_keywords": [],
        }
