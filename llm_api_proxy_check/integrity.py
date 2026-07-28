from __future__ import annotations

import json
import re
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Union

from llm_api_proxy_check.models import CheckResult, Status


class SSEControlFrame(Enum):
    DONE = "done"
    INVALID_DONE = "invalid_done"


SSEEvent = Union[dict[str, Any], SSEControlFrame]


@dataclass(frozen=True)
class StreamAuditResult:
    checks: tuple[CheckResult, ...]
    text: str
    tool_calls: tuple[dict[str, Any], ...]


def parse_sse_events(stream: str) -> list[SSEEvent]:
    events: list[SSEEvent] = []
    normalized = stream.replace("\r\n", "\n").replace("\r", "\n")
    for block in re.split(r"\n{2,}", normalized):
        data_lines = [line[6:] if line.startswith("data: ") else line[5:] for line in block.splitlines() if line.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines)
        if payload == "[DONE]":
            events.append(SSEControlFrame.DONE)
            continue
        if payload.strip() == "[DONE]":
            events.append(SSEControlFrame.INVALID_DONE)
            continue
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise TypeError("SSE data 必须是 JSON 对象")
        events.append(parsed)
    return events


def _objects(value: object) -> Iterable[dict[str, Any]]:
    if not isinstance(value, list):
        return ()
    return (item for item in value if isinstance(item, dict))


def _extract_tools(events: Iterable[SSEEvent]) -> tuple[dict[str, Any], ...]:
    calls: OrderedDict[int, dict[str, Any]] = OrderedDict()
    id_to_index: dict[str, int] = {}
    next_index = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        for choice in _objects(event.get("choices")):
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue
            for tool in _objects(delta.get("tool_calls")):
                raw_index = tool.get("index")
                tool_id = tool.get("id") if isinstance(tool.get("id"), str) else None
                if isinstance(raw_index, int) and not isinstance(raw_index, bool) and raw_index >= 0:
                    index = raw_index
                elif tool_id is not None and tool_id in id_to_index:
                    index = id_to_index[tool_id]
                else:
                    while next_index in calls:
                        next_index += 1
                    index = next_index
                    next_index += 1
                if tool_id is not None:
                    id_to_index[tool_id] = index
                call = calls.setdefault(index, {"index": index, "id": None, "name": "", "arguments": ""})
                if tool_id is not None:
                    call["id"] = tool_id
                function = tool.get("function")
                if isinstance(function, dict):
                    name = function.get("name")
                    arguments = function.get("arguments")
                    if isinstance(name, str):
                        call["name"] = call["name"] + name
                    if isinstance(arguments, str):
                        call["arguments"] = call["arguments"] + arguments
    return tuple(call for _, call in sorted(calls.items()))


def _token_count(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def audit_stream(stream: str, *, expected_usage: int | None = None, original_tools: tuple[dict[str, Any], ...] = ()) -> StreamAuditResult:
    try:
        events = parse_sse_events(stream)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return StreamAuditResult((CheckResult("sse_json", Status.FAIL, None, None, str(error), 4), CheckResult("sse_done", Status.UNKNOWN, None, 1, "stream could not be parsed", 3)), "", ())
    done_positions = [position for position, event in enumerate(events) if event is SSEControlFrame.DONE]
    done = len(done_positions) == 1 and done_positions[0] == len(events) - 1
    text_parts: list[str] = []
    usage: int | None = None
    usage_invalid = False
    for event in events:
        if not isinstance(event, dict):
            continue
        usage_data = event.get("usage")
        if usage_data is not None:
            if isinstance(usage_data, dict) and "total_tokens" in usage_data:
                candidate = _token_count(usage_data.get("total_tokens"))
                if candidate is None:
                    usage_invalid = True
                else:
                    usage = candidate
            elif usage_data is not None:
                usage_invalid = True
        for choice in _objects(event.get("choices")):
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue
            content = delta.get("content")
            if isinstance(content, str):
                text_parts.append(content)
    checks = [CheckResult("sse_json", Status.PASS, 1, 1, f"events={len(events)}", 4), CheckResult("sse_done", Status.PASS if done else Status.FAIL, int(done), 1, "exactly one terminal [DONE] event", 3)]
    expected = _token_count(expected_usage)
    if expected_usage is not None and expected is None:
        checks.append(CheckResult("usage_integrity", Status.UNKNOWN, None, None, "expected usage invalid", 3))
    elif expected is not None:
        if usage_invalid:
            checks.append(CheckResult("usage_integrity", Status.UNKNOWN, None, expected, "usage.total_tokens invalid", 3))
        elif usage is None:
            checks.append(CheckResult("usage_integrity", Status.UNKNOWN, None, expected, "usage.total_tokens missing", 3))
        else:
            ratio = abs(usage - expected) / max(1, expected)
            checks.append(CheckResult("usage_integrity", Status.PASS if ratio <= 0.2 else Status.FAIL, round(ratio, 4), 0.2, f"reported={usage}", 3))
    else:
        checks.append(CheckResult("usage_integrity", Status.UNKNOWN, None, None, "expected usage not provided", 3))
    tools = _extract_tools(events)
    if original_tools:
        normalized_actual = tuple({key: call[key] for key in ("id", "name", "arguments")} for call in tools)
        normalized_expected = tuple({key: call.get(key) for key in ("id", "name", "arguments")} for call in original_tools)
        changed = normalized_actual != normalized_expected
        checks.append(CheckResult("tool_integrity", Status.FAIL if changed else Status.PASS, int(not changed), 1, f"observed={len(tools)}", 4))
    return StreamAuditResult(tuple(checks), "".join(text_parts), tools)
