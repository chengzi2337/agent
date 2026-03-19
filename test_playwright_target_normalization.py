import unittest

from playwright_environment import PlaywrightEnvironment


class _FakeElement:
    def __init__(self, tag_name: str, input_type: str = "text") -> None:
        self._tag_name = tag_name
        self._input_type = input_type

    def evaluate(self, script: str):
        script_lower = script.lower()
        if "tagname" in script_lower:
            return self._tag_name.lower()
        if "el.type" in script_lower:
            return self._input_type.lower()
        return ""


class _FakePage:
    def __init__(self, mapping):
        self._mapping = mapping

    def query_selector(self, selector: str):
        return self._mapping.get(selector)


class PlaywrightTargetNormalizationTests(unittest.TestCase):
    def test_is_text_entry_selector_for_textarea(self) -> None:
        page = _FakePage({"#chat-textarea": _FakeElement("textarea")})
        self.assertTrue(PlaywrightEnvironment._is_text_entry_selector(page, "#chat-textarea"))

    def test_is_text_entry_selector_for_submit_is_false(self) -> None:
        page = _FakePage({"#su": _FakeElement("input", input_type="submit")})
        self.assertFalse(PlaywrightEnvironment._is_text_entry_selector(page, "#su"))

    def test_ensure_typing_target_redirects_to_chat_textarea(self) -> None:
        page = _FakePage(
            {
                "#chat-textarea": _FakeElement("textarea"),
                "a[href='hot']": _FakeElement("a"),
            }
        )
        resolved = PlaywrightEnvironment._ensure_typing_target(page, "a[href='hot']")
        self.assertEqual(resolved, "#chat-textarea")

    def test_ensure_enter_target_redirects_to_chat_textarea(self) -> None:
        page = _FakePage(
            {
                "#chat-textarea": _FakeElement("textarea"),
                "#su": _FakeElement("input", input_type="submit"),
            }
        )
        resolved = PlaywrightEnvironment._ensure_enter_target(page, "#su")
        self.assertEqual(resolved, "#chat-textarea")


if __name__ == "__main__":
    unittest.main()
