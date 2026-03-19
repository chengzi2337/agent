import unittest
from typing import Any, Dict, List, Tuple

from cer_architecture import CERAgent, CERDistiller, CERMemory, CERRetriever


class _NoopDistiller(CERDistiller):
    def distill_dynamics(self, trajectory: str):
        return []

    def distill_skills(self, trajectory: str):
        return []


class _NoopRetriever(CERRetriever):
    def __init__(self, memory: CERMemory) -> None:
        super().__init__(memory=memory)

    def retrieve(self, task_goal: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return [], []


class _SearchFlowEnvironment:
    def __init__(self) -> None:
        self._action_count = 0

    def get_observation(self) -> Dict[str, Any]:
        if self._action_count == 0:
            return {
                "url": "https://www.baidu.com/",
                "title": "百度一下，你就知道",
                "observation_text": "[1] textarea '智谱清言' selector='#chat-textarea'",
            }

        return {
            "url": "https://www.baidu.com/s?wd=%E6%99%BA%E8%B0%B1%E6%B8%85%E8%A8%80",
            "title": "智谱清言_百度搜索",
            "observation_text": "[1] textarea '智谱清言' selector='#chat-textarea'",
        }

    def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        self._action_count += 1
        return {"done": False, "observation": f"executed {action.get('type', '')}"}


class _AlreadyDoneObservationEnvironment:
    def get_observation(self) -> Dict[str, Any]:
        return {
            "url": "https://www.baidu.com/s?wd=%E6%99%BA%E8%B0%B1%E6%B8%85%E8%A8%80",
            "title": "智谱清言_百度搜索",
            "observation_text": "[1] textarea '智谱清言' selector='#chat-textarea'",
        }

    def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        return {"done": False, "observation": "noop"}


class _PressThenEmptyAgent(CERAgent):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.call_count = 0

    def _call_llm_api(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count == 1:
            return "<action>press</action><target>[1]</target><value>Enter</value>"
        return ""


class _AlwaysEmptyAgent(CERAgent):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.call_count = 0

    def _call_llm_api(self, prompt: str) -> str:
        self.call_count += 1
        return ""


class CERCompletionInferenceTests(unittest.TestCase):
    def _build_common(self):
        memory = CERMemory()
        distiller = _NoopDistiller()
        retriever = _NoopRetriever(memory=memory)
        return memory, distiller, retriever

    def test_infers_completion_from_post_observation_after_search_action(self) -> None:
        memory, distiller, retriever = self._build_common()
        environment = _SearchFlowEnvironment()

        agent = _PressThenEmptyAgent(
            memory=memory,
            distiller=distiller,
            retriever=retriever,
            environment=environment,
            max_steps=5,
        )

        result = agent.run_task("打开百度并搜索智谱清言")

        self.assertTrue(result["success"])
        self.assertEqual(result["steps"], 1)
        self.assertEqual(agent.call_count, 1)

        trajectory = result["trajectory"]
        self.assertTrue(trajectory)
        self.assertTrue(trajectory[-1].get("completion_inferred", False))

    def test_empty_response_retries_once_and_infers_completion_from_pre_observation(self) -> None:
        memory, distiller, retriever = self._build_common()
        environment = _AlreadyDoneObservationEnvironment()

        agent = _AlwaysEmptyAgent(
            memory=memory,
            distiller=distiller,
            retriever=retriever,
            environment=environment,
            max_steps=5,
        )

        result = agent.run_task("打开百度并搜索智谱清言")

        self.assertTrue(result["success"])
        self.assertEqual(result["steps"], 1)
        self.assertEqual(agent.call_count, 2)

        trajectory = result["trajectory"]
        self.assertTrue(trajectory)
        self.assertEqual(trajectory[-1].get("error"), "empty_llm_response")
        self.assertTrue(trajectory[-1].get("completion_inferred", False))


if __name__ == "__main__":
    unittest.main()
