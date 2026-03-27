from __future__ import annotations

from typing import Any, Dict, Protocol


class BaseEnv(Protocol):
    def reset(self, task_spec: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def get_observation(self) -> Dict[str, Any]:
        ...

    def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def get_target_metadata(self, target: str) -> Dict[str, Any]:
        ...

    def get_state_signature(self) -> str:
        ...

    def get_success_labels(self) -> Dict[str, Any]:
        ...

    def close(self) -> None:
        ...
