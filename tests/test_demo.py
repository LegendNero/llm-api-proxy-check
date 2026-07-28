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


if __name__ == "__main__":
    unittest.main()
