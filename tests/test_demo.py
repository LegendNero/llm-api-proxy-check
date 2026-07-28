from __future__ import annotations

import json
import subprocess
import sys
import unittest


class DemoTests(unittest.TestCase):
    def test_demo_outputs_high_risk_json(self) -> None:
        completed = subprocess.run([sys.executable, "-m", "llm_api_proxy_check", "demo", "--format", "json"], capture_output=True, text=True, check=False)
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(payload["risk"], "high")
        self.assertNotIn("api_key", completed.stdout.lower())
        self.assertNotIn("authorization", completed.stdout.lower())

    def test_check_without_endpoint_runs_demo(self) -> None:
        completed = subprocess.run([sys.executable, "-m", "llm_api_proxy_check", "check", "--format", "json"], capture_output=True, text=True, check=False)
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(payload["risk"], "high")

    def test_default_action_is_check(self) -> None:
        completed = subprocess.run([sys.executable, "-m", "llm_api_proxy_check"], capture_output=True, text=True, check=False)
        self.assertIn("high", completed.stdout.lower())
        self.assertIn("健康分", completed.stdout)
        self.assertEqual(completed.returncode, 1)

    def test_check_partial_endpoint_is_error(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "llm_api_proxy_check", "check", "--base-url", "https://example.com/v1"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("setup", completed.stderr.lower())

    def test_check_demo_flag(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "llm_api_proxy_check", "check", "--demo", "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(payload["risk"], "high")

    def test_help_mentions_setup(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "llm_api_proxy_check", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("setup", completed.stdout)


if __name__ == "__main__":
    unittest.main()
