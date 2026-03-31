from __future__ import annotations

import json
import os
from typing import List

from benchmarks.schemas import TaskSpec


def load_task_specs(task_dir: str) -> List[TaskSpec]:
    tasks: List[TaskSpec] = []
    for entry in sorted(os.listdir(task_dir)):
        if not entry.endswith(".json"):
            continue
        path = os.path.join(task_dir, entry)
        with open(path, "r", encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            raise ValueError(f"Task file '{path}' must contain a JSON object.")
        task = TaskSpec(raw)
        if not task.get("task_id"):
            raise ValueError(f"Task file '{path}' is missing 'task_id'.")
        tasks.append(task)
    return tasks
