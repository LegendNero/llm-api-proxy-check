from __future__ import annotations

import unittest

from llm_api_proxy_check.advice import advice_for_checks
from llm_api_proxy_check.mock import MockClient
from llm_api_proxy_check.models import CheckResult, Status
from llm_api_proxy_check.probes import economy_config, full_config, run_fingerprint_suite
from llm_api_proxy_check.usage import TokenUsage


class UsageTests(unittest.TestCase):
    def test_record_and_merge(self) -> None:
        left = TokenUsage()
        left.record({"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}, label="a")
        right = TokenUsage()
        right.record({"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}, label="b")
        merged = left.merge(right)
        self.assertEqual(merged.total_tokens, 11)
        self.assertEqual(merged.requests, 2)
        self.assertEqual(merged.by_label["a"], 6)
        self.assertEqual(merged.by_label["b"], 5)

    def test_missing_usage(self) -> None:
        usage = TokenUsage()
        usage.record(None, label="x")
        self.assertEqual(usage.missing_usage_responses, 1)
        self.assertIn("可能偏低", usage.summary_line())

    def test_advice_for_fail(self) -> None:
        lines = advice_for_checks((CheckResult("tool_integrity", Status.FAIL, 0, 1, "x", 4),))
        self.assertTrue(any("工具" in line for line in lines))

    def test_economy_skips_same_endpoint_fingerprint(self) -> None:
        client = MockClient(degraded=False)
        checks = {item.name: item for item in run_fingerprint_suite(client, client, config=economy_config())}
        self.assertEqual(checks["tokenizer_fingerprint"].status, Status.UNKNOWN)
        self.assertIn("save tokens", checks["tokenizer_fingerprint"].evidence)
        self.assertEqual(checks["output_distribution"].status, Status.UNKNOWN)
        self.assertIn("save tokens", checks["output_distribution"].evidence)
        self.assertIn("combined", checks["capability_baseline"].evidence)

    def test_full_runs_more_samples_when_reference_differs(self) -> None:
        target = MockClient(degraded=True)
        reference = MockClient(degraded=False)
        checks = {item.name: item for item in run_fingerprint_suite(target, reference, config=full_config())}
        self.assertNotEqual(checks["tokenizer_fingerprint"].status, Status.UNKNOWN)
        self.assertIn("samples=3", checks["tokenizer_fingerprint"].evidence)
        self.assertIn("split", checks["capability_baseline"].evidence)


if __name__ == "__main__":
    unittest.main()
