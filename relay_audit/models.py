from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    value: float | int | str | None
    threshold: float | int | str | None
    evidence: str
    weight: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "value": self.value,
            "threshold": self.threshold,
            "evidence": self.evidence,
            "weight": self.weight,
        }


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.timed_out
