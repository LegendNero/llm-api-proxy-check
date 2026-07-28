from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Callable, Protocol

from llm_api_proxy_check.models import CheckResult, Status


class ProbeClient(Protocol):
    def tokenize(self, text: str) -> int: ...
    def distribution(self, prompt: str) -> Mapping[str, float]: ...
    def complete(self, prompt: str, *, max_tokens: int = 64) -> str: ...


@dataclass(frozen=True)
class ProbeConfig:
    tokenizer_tolerance: float = 0.15
    jsd_match: float = 0.25
    jsd_uncertain: float = 0.35
    needle_context_limit: int = 12000


def _probability(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def _valid_distribution(distribution: Mapping[str, float]) -> bool:
    probabilities = tuple(_probability(value) for value in distribution.values())
    return bool(distribution) and all(isinstance(key, str) for key in distribution) and all(value is not None for value in probabilities) and any(value is not None and value > 0 for value in probabilities)


def js_divergence(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if not _valid_distribution(left) or not _valid_distribution(right):
        raise ValueError("分布必须非空且仅包含有限非负数")
    keys = set(left) | set(right)
    left_total = sum(float(left.get(key, 0.0)) for key in keys)
    right_total = sum(float(right.get(key, 0.0)) for key in keys)
    value = 0.0
    for key in keys:
        p = float(left.get(key, 0.0)) / left_total
        q = float(right.get(key, 0.0)) / right_total
        midpoint = (p + q) / 2
        if p:
            value += p * math.log2(p / midpoint) / 2
        if q:
            value += q * math.log2(q / midpoint) / 2
    return value


def tokenizer_probe(client: ProbeClient, reference: ProbeClient, samples: Sequence[str], config: ProbeConfig) -> CheckResult:
    observed = [client.tokenize(sample) for sample in samples]
    expected = [reference.tokenize(sample) for sample in samples]
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (*observed, *expected)):
        raise ValueError("token 数量必须是非负整数")
    ratios = [abs(actual - target) / max(1, target) for actual, target in zip(observed, expected)]
    deviation = sum(ratios) / len(ratios) if ratios else 1.0
    status = Status.PASS if deviation <= config.tokenizer_tolerance else Status.FAIL
    return CheckResult("tokenizer_fingerprint", status, round(deviation, 4), config.tokenizer_tolerance, f"samples={len(samples)}", 2)


def distribution_probe(client: ProbeClient, reference: ProbeClient, prompt: str, config: ProbeConfig) -> CheckResult:
    left = client.distribution(prompt)
    right = reference.distribution(prompt)
    if not _valid_distribution(left) or not _valid_distribution(right):
        return CheckResult("output_distribution", Status.UNKNOWN, None, config.jsd_match, "empty or non-finite distribution", 2)
    distance = js_divergence(left, right)
    status = Status.PASS if distance <= config.jsd_match else Status.UNKNOWN if distance < config.jsd_uncertain else Status.FAIL
    return CheckResult("output_distribution", status, round(distance, 4), config.jsd_match, "Jensen-Shannon divergence", 2)


def capability_probe(client: ProbeClient) -> CheckResult:
    checks = {
        "算术": client.complete("计算 37 * 19，只输出整数。", max_tokens=16).strip() == "703",
        "反转": client.complete("将字符串 abc-123 反转，只输出结果。", max_tokens=16).strip() == "321-cba",
    }
    passed = sum(checks.values())
    status = Status.PASS if passed == len(checks) else Status.FAIL
    return CheckResult("capability_baseline", status, passed, len(checks), f"passed={','.join(key for key, value in checks.items() if value)}", 2)


def needle_probe(client: ProbeClient, *, context: str, needle: str, config: ProbeConfig) -> CheckResult:
    if len(context) > config.needle_context_limit:
        return CheckResult("needle_retrieval", Status.UNKNOWN, len(context), config.needle_context_limit, "context exceeds configured safety limit", 3)
    answer = client.complete(f"在下面文本中找到唯一标记并只输出它：\n{context}", max_tokens=64).strip()
    matched = answer == needle
    return CheckResult("needle_retrieval", Status.PASS if matched else Status.FAIL, int(matched), 1, "exact needle retrieval", 3)


def _isolated(name: str, weight: int, operation: Callable[[], CheckResult]) -> CheckResult:
    try:
        return operation()
    except Exception as error:
        return CheckResult(name, Status.UNKNOWN, None, None, f"{type(error).__name__}: probe failed", weight)


def run_fingerprint_suite(client: ProbeClient, reference: ProbeClient, *, config: ProbeConfig | None = None) -> list[CheckResult]:
    settings = config or ProbeConfig()
    samples = ("1234567890", "😀中文English", "0.1+0.2=0.3")
    context = ("背景材料。" * 250) + "\n唯一标记：NEEDLE-7F3A\n" + ("背景材料。" * 250)
    return [
        _isolated("tokenizer_fingerprint", 2, lambda: tokenizer_probe(client, reference, samples, settings)),
        _isolated("output_distribution", 2, lambda: distribution_probe(client, reference, "从 1 到 100 选择一个数", settings)),
        _isolated("capability_baseline", 2, lambda: capability_probe(client)),
        _isolated("needle_retrieval", 3, lambda: needle_probe(client, context=context, needle="NEEDLE-7F3A", config=settings)),
    ]
