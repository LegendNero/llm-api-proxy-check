from __future__ import annotations

import math
import os
import subprocess
from collections.abc import Mapping, Sequence

from llm_api_proxy_check.models import CommandResult

_MAX_ARGS = 128
_MAX_ARG_LENGTH = 4096
_MAX_OUTPUT_BYTES = 1_000_000
_FORBIDDEN = {"\n", "\r", "\x00"}
_ALLOWED_ENV = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ")


def _validate_args(args: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(args)
    if not normalized:
        raise ValueError("命令不能为空")
    if len(normalized) > _MAX_ARGS:
        raise ValueError("命令参数过多")
    for position, arg in enumerate(normalized):
        if not isinstance(arg, str):
            raise TypeError("命令参数必须是字符串")
        if position == 0 and not arg.strip():
            raise ValueError("可执行文件不能为空")
        if len(arg) > _MAX_ARG_LENGTH:
            raise ValueError("命令参数过长")
        if any(character in arg for character in _FORBIDDEN):
            raise ValueError("命令参数包含非法控制字符")
    return normalized


def _safe_env(extra_env: Mapping[str, str] | None) -> dict[str, str]:
    environment = {key: os.environ[key] for key in _ALLOWED_ENV if key in os.environ}
    if extra_env:
        for key, value in extra_env.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError("环境变量名称和值必须是字符串")
            if not key or not key.replace("_", "a").isalnum() or "=" in key or any(character in value for character in _FORBIDDEN):
                raise ValueError("环境变量非法")
            environment[key] = value
    return environment


def _limit_output(value: str, limit: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return value, False
    shortened = encoded[:limit].decode("utf-8", errors="ignore")
    return shortened, True


def run_command(args: Sequence[str], *, timeout: float = 30.0, max_output_bytes: int = _MAX_OUTPUT_BYTES, extra_env: Mapping[str, str] | None = None) -> CommandResult:
    command = _validate_args(args)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("超时必须是有限正数")
    if isinstance(max_output_bytes, bool) or not isinstance(max_output_bytes, int) or max_output_bytes <= 0:
        raise TypeError("输出限制必须是正整数")
    try:
        completed = subprocess.run(command, capture_output=True, check=False, env=_safe_env(extra_env), shell=False, text=True, timeout=timeout)
        stdout, stdout_truncated = _limit_output(completed.stdout, max_output_bytes)
        remaining = max(0, max_output_bytes - len(stdout.encode("utf-8")))
        stderr, stderr_truncated = _limit_output(completed.stderr, remaining)
        return CommandResult(command, completed.returncode, stdout, stderr, False, stdout_truncated or stderr_truncated or len(completed.stderr.encode("utf-8")) > remaining)
    except subprocess.TimeoutExpired as error:
        stdout_value = error.stdout or ""
        stderr_value = error.stderr or ""
        if isinstance(stdout_value, bytes):
            stdout_value = stdout_value.decode("utf-8", errors="replace")
        if isinstance(stderr_value, bytes):
            stderr_value = stderr_value.decode("utf-8", errors="replace")
        stdout, stdout_truncated = _limit_output(stdout_value, max_output_bytes)
        stderr, stderr_truncated = _limit_output(stderr_value, max(0, max_output_bytes - len(stdout.encode("utf-8"))))
        return CommandResult(command, None, stdout, stderr, True, stdout_truncated or stderr_truncated)
