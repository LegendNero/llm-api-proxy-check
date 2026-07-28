from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

from llm_api_proxy_check.http_client import OpenAICompatibleHTTPClient


class OpenAIHandler(BaseHTTPRequestHandler):
    requests: ClassVar[list[dict[str, Any]]] = []

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        self.requests.append({"path": self.path, "authorization": self.headers.get("Authorization"), "payload": payload})
        prompt = payload["messages"][0]["content"]
        if payload.get("logprobs"):
            body = {"choices": [{"message": {"content": "42"}, "logprobs": {"content": [{"top_logprobs": [{"token": "42", "logprob": -0.1}, {"token": "73", "logprob": -2.0}]}]}}], "usage": {"prompt_tokens": 7, "total_tokens": 8}}
        else:
            body = {"choices": [{"message": {"content": "703" if "37 * 19" in prompt else "ok"}}], "usage": {"prompt_tokens": 7, "total_tokens": 8}}
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


class HTTPClientTests(unittest.TestCase):
    server: ClassVar[ThreadingHTTPServer]
    thread: ClassVar[threading.Thread]
    client: ClassVar[OpenAICompatibleHTTPClient]

    @classmethod
    def setUpClass(cls) -> None:
        OpenAIHandler.requests = []
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), OpenAIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.client = OpenAICompatibleHTTPClient(f"http://127.0.0.1:{cls.server.server_port}/v1", "test-key", "test-model")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_local_openai_compatible_end_to_end(self) -> None:
        self.assertEqual(self.client.tokenize("hello"), 7)
        self.assertEqual(self.client.complete("计算 37 * 19，只输出整数。", max_tokens=16), "703")
        distribution = self.client.distribution("从 1 到 100 选择一个数")
        self.assertGreater(distribution["42"], distribution["73"])
        self.assertTrue(all(request["path"] == "/v1/chat/completions" for request in OpenAIHandler.requests))
        self.assertTrue(all(request["authorization"] == "Bearer test-key" for request in OpenAIHandler.requests))
        self.assertTrue(all(request["payload"]["model"] == "test-model" for request in OpenAIHandler.requests))


if __name__ == "__main__":
    unittest.main()
