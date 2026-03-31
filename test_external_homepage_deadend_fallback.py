import unittest

from cer_architecture import CERAgent, CERDistiller, CERMemory, CERRetriever
from envs.web.playwright_env import BenchmarkPlaywrightEnvironment


class ExternalHomepageDeadendFallbackTests(unittest.TestCase):
    def test_environment_relative_goto_uses_start_url_from_error_page(self) -> None:
        captured: list[str] = []

        class DummyPage:
            url = 'chrome-error://chromewebdata/'

            @staticmethod
            def title() -> str:
                return 'localhost'

            @staticmethod
            def wait_for_timeout(_ms: int) -> None:
                return None

            @staticmethod
            def evaluate(_script: str):
                return {}

            def goto(self, url: str, wait_until: str = 'domcontentloaded') -> None:
                captured.append(url)

        env = BenchmarkPlaywrightEnvironment()
        try:
            env.task_spec = {
                'start_state': {'start_url': 'http://127.0.0.1:4399/'},
                'task_family': 'homepage_control_deadend',
            }
            env._ensure_page = lambda: DummyPage()
            env._sync_runtime_labels = lambda: None
            result = env.execute_action({'type': 'goto', 'target': 'scratchpad.html'})
            self.assertEqual(captured[-1], 'http://127.0.0.1:4399/scratchpad.html')
            self.assertEqual(result['observation'], 'Navigated to: http://127.0.0.1:4399/scratchpad.html')
        finally:
            env.close()

    def test_security_policy_allows_relative_navigation_from_error_page_using_start_url(self) -> None:
        memory = CERMemory()
        agent = CERAgent(
            memory=memory,
            distiller=CERDistiller(),
            retriever=CERRetriever(memory),
            environment=lambda action: {'done': False},
            security_policy={'allowed_domains': ['127.0.0.1', 'localhost']},
        )

        current_observation = {
            'url': 'chrome-error://chromewebdata/',
            'start_url': 'http://127.0.0.1:4399/',
        }
        self.assertIsNone(agent._evaluate_security_policy({'type': 'goto', 'target': 'scratchpad.html'}, current_observation))
        self.assertIsNone(agent._evaluate_security_policy({'type': 'goto', 'target': 'calculator.html'}, current_observation))


if __name__ == '__main__':
    unittest.main()
