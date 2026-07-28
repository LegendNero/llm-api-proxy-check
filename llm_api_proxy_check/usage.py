from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _nonneg_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0
    missing_usage_responses: int = 0
    by_label: dict[str, int] = field(default_factory=dict)

    def record(self, usage: object, *, label: str = "request") -> None:
        self.requests += 1
        if not isinstance(usage, dict):
            self.missing_usage_responses += 1
            self.by_label[label] = self.by_label.get(label, 0)
            return
        prompt = _nonneg_int(usage.get("prompt_tokens"))
        completion = _nonneg_int(usage.get("completion_tokens"))
        total = _nonneg_int(usage.get("total_tokens"))
        if prompt is None and completion is None and total is None:
            self.missing_usage_responses += 1
            return
        prompt_v = prompt or 0
        completion_v = completion or 0
        if total is None:
            total_v = prompt_v + completion_v
        else:
            total_v = total
            if prompt is None and completion is None:
                prompt_v = 0
                completion_v = 0
        self.prompt_tokens += prompt_v
        self.completion_tokens += completion_v
        self.total_tokens += total_v
        self.by_label[label] = self.by_label.get(label, 0) + total_v

    def merge(self, other: "TokenUsage") -> "TokenUsage":
        merged_labels = dict(self.by_label)
        for key, value in other.by_label.items():
            merged_labels[key] = merged_labels.get(key, 0) + value
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            requests=self.requests + other.requests,
            missing_usage_responses=self.missing_usage_responses + other.missing_usage_responses,
            by_label=merged_labels,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "requests": self.requests,
            "missing_usage_responses": self.missing_usage_responses,
            "by_label": dict(self.by_label),
            "complete": self.missing_usage_responses == 0 and self.requests > 0,
        }

    def summary_line(self) -> str:
        if self.requests <= 0:
            return "本次未产生 API 调用（本地 Mock / 未发请求）"
        base = (
            f"本次约消耗 **{self.total_tokens}** tokens"
            f"（prompt {self.prompt_tokens} + completion {self.completion_tokens}，"
            f"请求 {self.requests} 次）"
        )
        if self.missing_usage_responses:
            base += f"；其中 {self.missing_usage_responses} 次响应未返回 usage，统计可能偏低"
        return base
