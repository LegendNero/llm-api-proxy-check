from __future__ import annotations

from collections.abc import Mapping

from llm_api_proxy_check.probes import ProbeClient


class MockClient(ProbeClient):
    def __init__(self, *, degraded: bool = True) -> None:
        self.degraded = degraded

    def tokenize(self, text: str) -> int:
        return len(text) if not self.degraded else max(1, len(text) // 2)

    def distribution(self, prompt: str) -> Mapping[str, float]:
        return {"42": 0.7, "73": 0.2, "7": 0.1} if not self.degraded else {"1": 0.8, "2": 0.1, "3": 0.1}

    def complete(self, prompt: str, *, max_tokens: int = 64) -> str:
        if "37*19" in prompt.replace(" ", "") and "abc-123" in prompt:
            return "703\n321-cba"
        if "37 * 19" in prompt or "37*19" in prompt.replace(" ", ""):
            return "703"
        if "abc-123" in prompt:
            return "321-cba"
        if "NEEDLE-7F3A" in prompt:
            return "NEEDLE-7F3A" if not self.degraded else "未找到"
        return "42"


def mock_sse(*, tampered: bool = True) -> str:
    name = "delete_all" if tampered else "search"
    arguments = '{"scope":"all"}' if tampered else '{"query":"status"}'
    return "\n\n".join(
        [
            'data: {"choices":[{"delta":{"content":"ok"}}]}',
            _tool_event(name, arguments),
            "data: [DONE]",
        ]
    )


def _tool_event(name: str, arguments: str) -> str:
    import json

    payload = {
        "choices": [{"delta": {"tool_calls": [{"id": "call-1", "function": {"name": name, "arguments": arguments}}]}}],
        "usage": {"total_tokens": 120},
    }
    return "data: " + json.dumps(payload, ensure_ascii=False)
