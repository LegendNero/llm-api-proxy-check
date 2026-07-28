from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


class OpenAICompatibleHTTPClient:
    def __init__(self, base_url: str, api_key: str, model: str, *, timeout: float = 30.0) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url 必须使用 http 或 https")
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("api_key 不能为空")
        if not isinstance(model, str) or not model:
            raise ValueError("model 不能为空")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout 必须是有限正数")
        self.base_url = base_url.rstrip("/") + "/"
        self.api_key = api_key
        self.model = model
        self.timeout = float(timeout)

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            urljoin(self.base_url, "chat/completions"),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            raise RuntimeError(f"OpenAI-compatible HTTP {error.code}") from error
        except (URLError, TimeoutError) as error:
            raise RuntimeError("OpenAI-compatible request failed") from error
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as error:
            raise RuntimeError("OpenAI-compatible response is not JSON") from error
        if not isinstance(parsed, dict):
            raise RuntimeError("OpenAI-compatible response must be an object")
        return parsed

    def _completion(self, prompt: str, *, max_tokens: int, logprobs: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0,
            "stream": False,
        }
        if logprobs:
            payload.update({"logprobs": True, "top_logprobs": 20})
        return self._request(payload)

    def tokenize(self, text: str) -> int:
        response = self._completion(text, max_tokens=1)
        usage = response.get("usage")
        value = usage.get("prompt_tokens") if isinstance(usage, dict) else None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RuntimeError("response usage.prompt_tokens invalid")
        return value

    def complete(self, prompt: str, *, max_tokens: int = 64) -> str:
        response = self._completion(prompt, max_tokens=max_tokens)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise RuntimeError("response choices invalid")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise RuntimeError("response content invalid")
        return content

    def distribution(self, prompt: str) -> Mapping[str, float]:
        response = self._completion(prompt, max_tokens=1, logprobs=True)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise RuntimeError("response choices invalid")
        logprobs = choices[0].get("logprobs")
        content = logprobs.get("content") if isinstance(logprobs, dict) else None
        if not isinstance(content, list) or not content or not isinstance(content[0], dict):
            raise RuntimeError("response logprobs invalid")
        top = content[0].get("top_logprobs")
        if not isinstance(top, list):
            raise RuntimeError("response top_logprobs invalid")
        distribution: dict[str, float] = {}
        for item in top:
            if not isinstance(item, dict):
                continue
            token = item.get("token")
            logprob = item.get("logprob")
            if isinstance(token, str) and isinstance(logprob, (int, float)) and not isinstance(logprob, bool) and math.isfinite(logprob):
                distribution[token] = math.exp(float(logprob))
        if not distribution:
            raise RuntimeError("response distribution empty")
        return distribution
