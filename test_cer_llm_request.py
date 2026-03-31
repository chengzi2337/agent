import unittest
from unittest.mock import Mock, patch

import requests

from cer_architecture import _safe_llm_request, get_last_llm_error


class CERLLMRequestTests(unittest.TestCase):
    def test_http_error_records_status_and_provider_code(self) -> None:
        response = Mock()
        response.status_code = 401
        response.json.return_value = {"error": {"code": "1000", "message": "auth failed"}}
        error = requests.exceptions.HTTPError("401 Client Error")
        error.response = response

        with patch("cer_architecture.requests.post", side_effect=error):
            text, tokens, latency_ms = _safe_llm_request(
                api_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers={"Authorization": "Bearer test"},
                payload={"model": "glm-4.6v", "messages": [{"role": "user", "content": "hello"}]},
            )

        self.assertEqual(text, "")
        self.assertEqual(tokens, 0)
        self.assertGreaterEqual(latency_ms, 0.0)
        self.assertEqual(
            get_last_llm_error(),
            "request_exception:HTTPError:status=401:provider_code=1000",
        )


if __name__ == "__main__":
    unittest.main()
