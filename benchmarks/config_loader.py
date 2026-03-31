from __future__ import annotations

import json
import os
from typing import List

from benchmarks.schemas import AgentConfigSpec


def load_agent_configs(config_dir: str) -> List[AgentConfigSpec]:
    configs: List[AgentConfigSpec] = []
    for entry in sorted(os.listdir(config_dir)):
        if not entry.endswith(".json"):
            continue
        path = os.path.join(config_dir, entry)
        with open(path, "r", encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            raise ValueError(f"Config file '{path}' must contain a JSON object.")
        config = AgentConfigSpec(raw)
        if not config.get("name"):
            raise ValueError(f"Config file '{path}' is missing 'name'.")
        configs.append(config)
    return configs
