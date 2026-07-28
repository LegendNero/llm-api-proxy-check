from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass

from llm_api_proxy_check.models import CheckResult, Status

_CHECK_WEIGHTS = {
    "tokenizer_fingerprint": 2,
    "output_distribution": 2,
    "capability_baseline": 2,
    "needle_retrieval": 3,
    "sse_json": 4,
    "sse_done": 3,
    "usage_integrity": 3,
    "tool_integrity": 4,
}
_REDACTIONS = (
    (re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;|]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*)[^\s,;|]+"), r"\1[REDACTED]"),
    (re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{6,}\b"), "[REDACTED]"),
)


def _redact(value: float | str | None) -> float | str | None:
    if not isinstance(value, str):
        return value
    redacted = value
    for pattern, replacement in _REDACTIONS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _sanitize(check: CheckResult, weight: int | None = None) -> CheckResult:
    return CheckResult(str(_redact(check.name)), check.status, _redact(check.value), _redact(check.threshold), str(_redact(check.evidence)), check.weight if weight is None else weight)


def _markdown_cell(value: object) -> str:
    escaped = html.escape(str(value), quote=False).replace("|", "\\|")
    return escaped.replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")


@dataclass(frozen=True)
class AuditReport:
    score: int
    risk: str
    coverage: float
    checks: tuple[CheckResult, ...]

    def as_dict(self) -> dict[str, object]:
        return {"score": self.score, "risk": self.risk, "coverage": self.coverage, "checks": [check.as_dict() for check in self.checks]}

    def markdown(self) -> str:
        lines = [f"# Relay API Audit\n\n- 健康分：**{self.score}/100**\n- 风险等级：**{self.risk}**\n- 检查覆盖率：**{self.coverage:.1%}**\n", "| 检查 | 状态 | 值 | 阈值 | 证据 |", "|---|---|---:|---:|---|"]
        lines.extend(f"| {_markdown_cell(check.name)} | {check.status.value} | {_markdown_cell(check.value)} | {_markdown_cell(check.threshold)} | {_markdown_cell(check.evidence)} |" for check in self.checks)
        return "\n".join(lines) + "\n"


def build_report(checks: Iterable[CheckResult]) -> AuditReport:
    supplied = tuple(checks)
    by_name = {check.name: check for check in supplied if check.name in _CHECK_WEIGHTS}
    expected = tuple(_sanitize(by_name[name], weight) if name in by_name else CheckResult(name, Status.UNKNOWN, None, None, "check not run", weight) for name, weight in _CHECK_WEIGHTS.items())
    extras = tuple(_sanitize(check) for check in supplied if check.name not in _CHECK_WEIGHTS)
    total_weight = sum(_CHECK_WEIGHTS.values())
    penalty = sum(check.weight for check in expected if check.status is Status.FAIL)
    unknown_penalty = sum(check.weight for check in expected if check.status is Status.UNKNOWN) * 0.5
    score = max(0, round(100 * (1 - (penalty + unknown_penalty) / total_weight)))
    coverage = sum(check.weight for check in expected if check.status is not Status.UNKNOWN) / total_weight
    risk = "low" if score >= 85 else "medium" if score >= 60 else "high"
    return AuditReport(score, risk, coverage, (*expected, *extras))


def report_json(report: AuditReport) -> str:
    return json.dumps(report.as_dict(), ensure_ascii=False, indent=2)
