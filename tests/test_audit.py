from __future__ import annotations

import json
import math
import unittest
from collections.abc import Mapping

from llm_api_proxy_check.integrity import SSEControlFrame, audit_stream, parse_sse_events
from llm_api_proxy_check.mock import MockClient, mock_sse
from llm_api_proxy_check.models import CheckResult, Status
from llm_api_proxy_check.probes import ProbeConfig, distribution_probe, js_divergence, needle_probe, run_fingerprint_suite
from llm_api_proxy_check.report import build_report, report_json


class FaultyClient(MockClient):
    def tokenize(self, text: str) -> int:
        raise RuntimeError("secret detail")


class DistributionClient(MockClient):
    def __init__(self, values: Mapping[str, float]) -> None:
        super().__init__(degraded=False)
        self.values = values

    def distribution(self, prompt: str) -> Mapping[str, float]:
        return self.values


class NeedleClient(MockClient):
    def complete(self, prompt: str, *, max_tokens: int = 64) -> str:
        return "prefix NEEDLE-7F3A suffix"


class ProbeTests(unittest.TestCase):
    def test_jsd_identical_is_zero(self) -> None:
        self.assertAlmostEqual(js_divergence({"a": 1}, {"a": 1}), 0.0)

    def test_suite_detects_degraded_mock(self) -> None:
        checks = run_fingerprint_suite(MockClient(degraded=True), MockClient(degraded=False), config=ProbeConfig())
        self.assertTrue(any(check.status is Status.FAIL for check in checks))

    def test_needle_safety_limit_is_unknown(self) -> None:
        result = run_fingerprint_suite(MockClient(degraded=False), MockClient(degraded=False), config=ProbeConfig(needle_context_limit=10))[-1]
        self.assertIs(result.status, Status.UNKNOWN)

    def test_probe_exception_is_isolated(self) -> None:
        checks = run_fingerprint_suite(FaultyClient(degraded=False), MockClient(degraded=False))
        self.assertIs(checks[0].status, Status.UNKNOWN)
        self.assertEqual(len(checks), 4)
        self.assertNotIn("secret detail", checks[0].evidence)

    def test_empty_and_non_finite_distributions_are_unknown(self) -> None:
        reference = MockClient(degraded=False)
        for values in ({}, {"42": math.nan}, {"42": math.inf}):
            with self.subTest(values=values):
                result = distribution_probe(DistributionClient(values), reference, "prompt", ProbeConfig())
                self.assertIs(result.status, Status.UNKNOWN)
                self.assertIsNone(result.value)

    def test_needle_requires_exact_answer(self) -> None:
        result = needle_probe(NeedleClient(degraded=False), context="NEEDLE-7F3A", needle="NEEDLE-7F3A", config=ProbeConfig())
        self.assertIs(result.status, Status.FAIL)


class IntegrityTests(unittest.TestCase):
    def test_multiline_sse_and_tool_rewrite(self) -> None:
        events = parse_sse_events("data: {\"a\":\ndata: 1}\n\ndata: [DONE]\n")
        self.assertIsInstance(events[0], dict)
        first_event = events[0]
        assert isinstance(first_event, dict)
        self.assertEqual(first_event["a"], 1)
        self.assertIs(events[1], SSEControlFrame.DONE)
        result = audit_stream(mock_sse(tampered=True), expected_usage=80, original_tools=({"name": "search", "arguments": '{"query":"status"}'},))
        statuses = {check.name: check.status for check in result.checks}
        self.assertIs(statuses["tool_integrity"], Status.FAIL)
        self.assertIs(statuses["usage_integrity"], Status.FAIL)

    def test_control_frame_cannot_be_forged_by_json_field(self) -> None:
        stream = 'data: {"__sse_done__":true,"choices":[]}\n\ndata: [DONE]'
        events = parse_sse_events(stream)
        self.assertIsInstance(events[0], dict)
        self.assertIs(events[1], SSEControlFrame.DONE)
        self.assertIs({check.name: check.status for check in audit_stream(stream).checks}["sse_done"], Status.PASS)

    def test_done_must_be_exactly_once_and_terminal(self) -> None:
        streams = (
            'data: {"choices":[]}\n\ndata: [DONE]\n\ndata: [DONE]',
            'data: [DONE]\n\ndata: {"choices":[]}',
            'data:  [DONE]',
            'data: {"done":true}',
        )
        for stream in streams:
            with self.subTest(stream=stream):
                statuses = {check.name: check.status for check in audit_stream(stream).checks}
                self.assertIs(statuses["sse_done"], Status.FAIL)

    def test_malformed_nested_schema_does_not_crash(self) -> None:
        malformed = {"choices": [None, "bad", {"delta": None}, {"delta": {"tool_calls": "bad"}}], "usage": []}
        stream = "data: " + json.dumps(malformed) + "\n\ndata: [DONE]"
        result = audit_stream(stream, expected_usage=10, original_tools=({"name": "search"},))
        statuses = {check.name: check.status for check in result.checks}
        self.assertIs(statuses["sse_json"], Status.PASS)
        self.assertIs(statuses["usage_integrity"], Status.UNKNOWN)
        self.assertIs(statuses["tool_integrity"], Status.FAIL)

    def test_missing_done_fails(self) -> None:
        result = audit_stream('data: {"choices":[{"delta":{"content":"ok"}}]}')
        self.assertIs(result.checks[1].status, Status.FAIL)

    def test_tool_call_fragments_are_reassembled_by_index_and_id(self) -> None:
        payloads = (
            {"choices": [{"delta": {"tool_calls": [{"index": 1, "id": "call-b", "function": {"name": "look", "arguments": '{"q":"'}}, {"index": 0, "id": "call-a", "function": {"name": "sea", "arguments": '{"query":"'}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "rch", "arguments": 'status"}'}}, {"index": 1, "id": "call-b", "function": {"name": "up", "arguments": 'docs"}'}}]}}]},
        )
        stream = "\n\n".join([*("data: " + json.dumps(payload) for payload in payloads), "data: [DONE]"])
        expected = (
            {"id": "call-a", "name": "search", "arguments": '{"query":"status"}'},
            {"id": "call-b", "name": "lookup", "arguments": '{"q":"docs"}'},
        )
        result = audit_stream(stream, original_tools=expected)
        self.assertEqual(result.tool_calls, ({"index": 0, **expected[0]}, {"index": 1, **expected[1]}))
        self.assertIs({check.name: check.status for check in result.checks}["tool_integrity"], Status.PASS)

    def test_missing_and_invalid_usage_are_unknown(self) -> None:
        streams = (
            'data: {"choices":[]}',
            'data: {"choices":[],"usage":{"total_tokens":true}}',
            'data: {"choices":[],"usage":{"total_tokens":-1}}',
            'data: {"choices":[],"usage":{"total_tokens":1.5}}',
        )
        for payload in streams:
            with self.subTest(payload=payload):
                result = audit_stream(payload + "\n\ndata: [DONE]", expected_usage=10)
                usage = next(check for check in result.checks if check.name == "usage_integrity")
                self.assertIs(usage.status, Status.UNKNOWN)
                self.assertIsNone(usage.value)


class ReportTests(unittest.TestCase):
    def test_report_penalizes_fail_and_unknown(self) -> None:
        report = build_report((CheckResult("a", Status.PASS, 1, 1, "", 1), CheckResult("b", Status.FAIL, 0, 1, "", 3), CheckResult("c", Status.UNKNOWN, None, 1, "", 2)))
        self.assertLess(report.score, 60)
        self.assertEqual(report.risk, "high")

    def test_score_uses_fixed_check_coverage(self) -> None:
        report = build_report((CheckResult("sse_json", Status.PASS, 1, 1, "", 999),))
        self.assertLess(report.score, 75)
        self.assertEqual(report.coverage, 4 / 23)
        self.assertEqual(len(report.checks), 8)

    def test_report_redacts_secrets_and_escapes_markdown(self) -> None:
        evidence = "Authorization: Bearer secret-token | row\n<script>alert(1)</script> api_key=abc123"
        report = build_report((CheckResult("sse_json", Status.FAIL, "sk-secret123", 1, evidence, 4),))
        json_output = report_json(report)
        markdown = report.markdown()
        for output in (json_output, markdown):
            self.assertNotIn("secret-token", output)
            self.assertNotIn("sk-secret123", output)
            self.assertNotIn("abc123", output)
        self.assertIn("\\|", markdown)
        self.assertIn("<br>", markdown)
        self.assertNotIn("<script>", markdown)


if __name__ == "__main__":
    unittest.main()
