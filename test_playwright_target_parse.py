import unittest

from playwright_environment import PlaywrightEnvironment


class PlaywrightTargetParseTests(unittest.TestCase):
    def test_target_to_observation_id_supports_bracket_format(self) -> None:
        self.assertEqual(PlaywrightEnvironment._target_to_observation_id("[15]"), 15)

    def test_target_to_observation_id_supports_prefix_format(self) -> None:
        self.assertEqual(PlaywrightEnvironment._target_to_observation_id("id: 16"), 16)

    def test_target_to_observation_id_supports_plain_digits(self) -> None:
        # Regression: model may output plain numeric IDs like "15".
        self.assertEqual(PlaywrightEnvironment._target_to_observation_id("15"), 15)

    def test_resolve_target_maps_plain_digits_to_selector(self) -> None:
        environment = PlaywrightEnvironment(headless=True)
        environment._id_to_selector = {15: "#chat-textarea"}
        self.assertEqual(environment._resolve_target("15"), "#chat-textarea")


if __name__ == "__main__":
    unittest.main()
