from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _isolated_env(config_path: Path | None = None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("LLM_API_PROXY_CHECK_")}
    if config_path is not None:
        env["LLM_API_PROXY_CHECK_CONFIG"] = str(config_path)
    else:
        env["LLM_API_PROXY_CHECK_CONFIG"] = str(Path(tempfile.mkdtemp()) / "missing-config.json")
    return env


class DemoTests(unittest.TestCase):
    def test_demo_outputs_high_risk_json(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "llm_api_proxy_check", "demo", "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
            env=_isolated_env(),
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(payload["risk"], "high")
        self.assertNotIn("api_key", completed.stdout.lower())
        self.assertNotIn("authorization", completed.stdout.lower())

    def test_check_without_endpoint_runs_demo(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "llm_api_proxy_check", "check", "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
            env=_isolated_env(),
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(payload["risk"], "high")

    def test_default_action_is_check(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "llm_api_proxy_check"],
            capture_output=True,
            text=True,
            check=False,
            env=_isolated_env(),
        )
        self.assertIn("high", completed.stdout.lower())
        self.assertIn("健康分", completed.stdout)
        self.assertEqual(completed.returncode, 1)

    def test_check_partial_endpoint_is_error(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "llm_api_proxy_check", "check", "--base-url", "https://example.com/v1"],
            capture_output=True,
            text=True,
            check=False,
            env=_isolated_env(),
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("setup", completed.stderr.lower())

    def test_check_demo_flag(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "llm_api_proxy_check", "check", "--demo", "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
            env=_isolated_env(),
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
            env=_isolated_env(),
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("setup", completed.stdout)
        self.assertIn("economy", completed.stdout.lower())

    def test_demo_markdown_has_advice_and_usage(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "llm_api_proxy_check", "check", "--demo"],
            capture_output=True,
            text=True,
            check=False,
            env=_isolated_env(),
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("怎么处理", completed.stdout)
        self.assertIn("API 用量", completed.stdout)
        payload = json.loads(
            subprocess.run(
                [sys.executable, "-m", "llm_api_proxy_check", "demo", "--format", "json"],
                capture_output=True,
                text=True,
                check=False,
                env=_isolated_env(),
            ).stdout
        )
        self.assertIn("advice", payload)
        self.assertIn("token_usage", payload)


if __name__ == "__main__":
    unittest.main()
