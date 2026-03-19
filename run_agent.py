from __future__ import annotations

import os
import sys
from typing import Any, Dict

from cer_architecture import (
    CERAgent,
    CERDistiller,
    CERMemory,
    CERRetriever,
    MockEnvironment,
    _safe_llm_request,
)
from playwright_environment import PlaywrightEnvironment


class ZhipuCERDistiller(CERDistiller):
    """CERDistiller adapter for Zhipu OpenAI-compatible API."""

    def _call_llm_api(self, prompt: str) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        return _safe_llm_request(self.api_url, self.headers, payload)


class ZhipuCERRetriever(CERRetriever):
    """CERRetriever adapter for Zhipu OpenAI-compatible API."""

    def _call_llm_api(self, prompt: str) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        return _safe_llm_request(self.api_url, self.headers, payload)


class ZhipuCERAgent(CERAgent):
    """CERAgent adapter for Zhipu OpenAI-compatible API."""

    def _call_llm_api(self, prompt: str) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        return _safe_llm_request(self.api_url, self.headers, payload)


def _build_headers(api_key: str) -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _to_bool(value: str, default: bool) -> bool:
    cleaned = value.strip().lower()
    if not cleaned:
        return default
    return cleaned in {"1", "true", "yes", "y", "on"}


def _resolve_task_goal(default_goal: str, interactive_enabled: bool) -> str:
    """Resolve task goal from env var or terminal natural-language input."""

    env_goal = os.getenv("CER_TASK_GOAL", "").strip()
    if env_goal:
        return env_goal

    if not interactive_enabled:
        return default_goal

    if not sys.stdin.isatty():
        return default_goal

    try:
        print("[INPUT] 请输入自然语言任务目标（直接回车使用默认目标）")
        user_goal = input("[INPUT] Task Goal: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[INFO] Goal input interrupted. Using default task goal.")
        return default_goal

    return user_goal if user_goal else default_goal


def _print_observation_preview(observation: Dict[str, Any], line_limit: int = 10) -> None:
    """Print a concise preview of textual observation for debugging."""

    url = str(observation.get("url", ""))
    title = str(observation.get("title", ""))
    count = int(observation.get("count", 0)) if str(observation.get("count", "")).isdigit() else observation.get("count", 0)
    print(f"[OBS] url={url}")
    print(f"[OBS] title={title}")
    print(f"[OBS] interactive_count={count}")

    text = str(observation.get("observation_text", "")).strip()
    if not text:
        print("[OBS] <empty-observation>")
        return

    lines = text.splitlines()
    preview = lines[:line_limit]
    print("[OBS] preview:")
    for line in preview:
        print(f"  {line}")
    remaining = len(lines) - len(preview)
    if remaining > 0:
        print(f"  ... (+{remaining} more lines)")


def _resolve_demo_target_from_observation(observation: Dict[str, Any], default_target: str = "#chat-textarea") -> str:
    """Pick an observation ID target for typing if available."""

    elements = observation.get("elements")
    if not isinstance(elements, list):
        return default_target

    # Prefer known visible editable controls on Baidu new homepage.
    for item in elements:
        if not isinstance(item, dict):
            continue
        element_id = item.get("id")
        selector = str(item.get("selector", ""))
        role = str(item.get("role", "")).lower()
        if isinstance(element_id, int) and selector == "#chat-textarea" and role == "textarea":
            return f"[{element_id}]"

    # Then prefer generic editable text controls that are likely visible.
    for item in elements:
        if not isinstance(item, dict):
            continue
        element_id = item.get("id")
        selector = str(item.get("selector", ""))
        role = str(item.get("role", "")).lower()
        if not isinstance(element_id, int):
            continue
        if role == "textarea":
            return f"[{element_id}]"
        if role == "input" and selector.startswith("#") and selector != "#kw":
            return f"[{element_id}]"

    # Fallback to legacy Baidu search selector if nothing better is found.
    for item in elements:
        if not isinstance(item, dict):
            continue
        element_id = item.get("id")
        selector = str(item.get("selector", ""))
        if isinstance(element_id, int) and selector == "#kw":
            return f"[{element_id}]"

    # Last fallback: first input-like role.
    for item in elements:
        if not isinstance(item, dict):
            continue
        element_id = item.get("id")
        role = str(item.get("role", "")).lower()
        if isinstance(element_id, int) and ("input" in role or "textarea" in role):
            return f"[{element_id}]"

    return default_target


def _run_playwright_smoke_demo(environment: PlaywrightEnvironment, press_enter: bool = False) -> None:
    """Run deterministic browser steps to validate action parser and execution."""

    print("\n[PLAYWRIGHT DEMO] Running deterministic Observation -> Action steps...")

    step = 1
    goto_result = environment.execute_action({"raw": "<action>goto</action><url>https://www.baidu.com</url>"})
    if goto_result.get("error"):
        print(f"[PLAYWRIGHT DEMO] Step {step} failed: {goto_result['error']}")
        return
    print(f"[PLAYWRIGHT DEMO] Step {step} success: {goto_result.get('observation', '')}")

    observation = environment.get_observation(max_items=30)
    print("[PLAYWRIGHT DEMO] Observation captured after navigation.")
    _print_observation_preview(observation)

    target_for_type = _resolve_demo_target_from_observation(observation, default_target="#chat-textarea")
    print(f"[PLAYWRIGHT DEMO] Using type target: {target_for_type}")

    step += 1
    type_result = environment.execute_action(
        {
            "raw": (
                "<action>type</action>"
                f"<target>{target_for_type}</target>"
                "<value>Dalian University of Technology</value>"
            )
        }
    )
    if type_result.get("error"):
        print(f"[PLAYWRIGHT DEMO] Step {step} failed: {type_result['error']}")
        return
    print(f"[PLAYWRIGHT DEMO] Step {step} success: {type_result.get('observation', '')}")

    step += 1
    wait_result = environment.execute_action({"raw": "<action>wait</action><value>6</value>"})
    if wait_result.get("error"):
        print(f"[PLAYWRIGHT DEMO] Step {step} failed: {wait_result['error']}")
        return
    print(f"[PLAYWRIGHT DEMO] Step {step} success: {wait_result.get('observation', '')}")

    if not press_enter:
        print("[PLAYWRIGHT DEMO] Skip Enter press to keep typed text visible in input box.")
        return

    step += 1
    press_result = environment.execute_action(
        {
            "raw": (
                "<action>press</action>"
                f"<target>{target_for_type}</target>"
                "<value>Enter</value>"
            )
        }
    )
    if press_result.get("error"):
        print(f"[PLAYWRIGHT DEMO] Step {step} failed: {press_result['error']}")
        return
    print(f"[PLAYWRIGHT DEMO] Step {step} success: {press_result.get('observation', '')}")

    step += 1
    tail_wait_result = environment.execute_action({"raw": "<action>wait</action><value>3</value>"})
    if tail_wait_result.get("error"):
        print(f"[PLAYWRIGHT DEMO] Step {step} failed: {tail_wait_result['error']}")
        return
    print(f"[PLAYWRIGHT DEMO] Step {step} success: {tail_wait_result.get('observation', '')}")


def main() -> None:
    """Run one full CER task cycle with retrieval, acting, distillation and persistence."""

    # 1) System bootstrap
    memory = CERMemory()
    memory.load_from_disk()

    api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    api_key = os.getenv("ZHIPU_API_KEY", "")
    model_name = "glm-4-flash"
    headers = _build_headers(api_key)

    if not api_key.strip():
        print("[WARN] Environment variable ZHIPU_API_KEY is empty.")

    use_playwright = _to_bool(os.getenv("CER_USE_PLAYWRIGHT", "1"), default=True)
    keep_browser_open = _to_bool(os.getenv("CER_KEEP_BROWSER_OPEN", "1"), default=True)
    only_demo = _to_bool(os.getenv("CER_ONLY_DEMO", "0"), default=False)
    demo_press_enter = _to_bool(os.getenv("CER_DEMO_PRESS_ENTER", "0"), default=False)
    trace_enabled = _to_bool(os.getenv("CER_TRACE", "1"), default=True)
    interactive_goal_enabled = _to_bool(os.getenv("CER_INTERACTIVE_GOAL", "1"), default=True)

    environment: Any = MockEnvironment()
    if use_playwright:
        try:
            environment = PlaywrightEnvironment(headless=False, keep_open=keep_browser_open)
        except Exception as exc:
            print(f"[WARN] Failed to initialize PlaywrightEnvironment: {exc}")
            print("[WARN] Falling back to MockEnvironment.")
            environment = MockEnvironment()
    else:
        print("[INFO] Using MockEnvironment because CER_USE_PLAYWRIGHT is disabled.")

    if only_demo:
        if isinstance(environment, PlaywrightEnvironment):
            _run_playwright_smoke_demo(environment, press_enter=demo_press_enter)
        else:
            print("[WARN] Demo mode requested, but Playwright environment is unavailable.")

        print("\n[DEMO SUMMARY]")
        print("Mode: CER_ONLY_DEMO=1")
        print(f"Press Enter after typing: {demo_press_enter}")
        print("Skipping agent.run_task and keeping only visual browser demonstration.")
        if not keep_browser_open and hasattr(environment, "close") and callable(getattr(environment, "close")):
            environment.close()
        return

    print("[INFO] Autonomous mode enabled: no hardcoded browser actions will run.")

    distiller = ZhipuCERDistiller(api_url=api_url, model=model_name, headers=headers)
    retriever = ZhipuCERRetriever(memory=memory, api_url=api_url, model=model_name, headers=headers)
    agent = ZhipuCERAgent(
        memory=memory,
        distiller=distiller,
        retriever=retriever,
        environment=environment,
        api_url=api_url,
        model=model_name,
        headers=headers,
        max_steps=10,
        trace_enabled=trace_enabled,
    )

    # 2) Execute one full CER round
    default_task_goal = "Open https://www.baidu.com and search for Dalian University of Technology."
    task_goal = _resolve_task_goal(
        default_goal=default_task_goal,
        interactive_enabled=interactive_goal_enabled,
    )
    print(f"[INFO] Task goal: {task_goal}")
    result: Dict[str, Any] = {}
    runtime_error = ""

    try:
        result = agent.run_task(task_goal)
    except Exception as exc:
        runtime_error = str(exc)
    finally:
        # Force persistence at the end of the run.
        memory.save_to_disk()
        if not keep_browser_open and hasattr(environment, "close") and callable(getattr(environment, "close")):
            environment.close()

    # 3) Pretty summary output
    if runtime_error:
        print("\n[RUN SUMMARY]")
        print(f"Task goal: {task_goal}")
        print("Task success: False")
        print(f"Error: {runtime_error}")
        return

    print("\n[RUN SUMMARY]")
    print(f"Task goal: {task_goal}")
    print(f"Task success: {result.get('success', False)}")
    print(f"Steps executed: {result.get('steps', 0)}")
    print(f"Retrieved dynamic IDs: {result.get('selected_dynamic_ids', [])}")
    print(f"Retrieved skill IDs: {result.get('selected_skill_ids', [])}")
    print(f"Persisted dynamic IDs: {result.get('persisted_dynamic_ids', [])}")
    print(f"Persisted skill IDs: {result.get('persisted_skill_ids', [])}")
    print("Memory file: cer_memory.json")


if __name__ == "__main__":
    main()
