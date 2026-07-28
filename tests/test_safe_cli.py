from __future__ import annotations

import os
import sys
import unittest
from collections.abc import Mapping
from typing import cast
from unittest.mock import patch

from relay_audit.safe_cli import run_command


class SafeCliTests(unittest.TestCase):
    def test_shell_metacharacters_are_data(self) -> None:
        result = run_command([sys.executable, "-c", "import sys; print(sys.argv[1])", "; echo injected"])
        self.assertTrue(result.succeeded)
        self.assertEqual(result.stdout.strip(), "; echo injected")

    def test_rejects_control_characters(self) -> None:
        with self.assertRaises(ValueError):
            run_command(["printf", "unsafe\nvalue"])

    def test_rejects_empty_executable(self) -> None:
        with self.assertRaises(ValueError):
            run_command([""])

    def test_rejects_boolean_and_non_finite_limits(self) -> None:
        for timeout in (True, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises((TypeError, ValueError)):
                run_command([sys.executable, "-c", "pass"], timeout=timeout)
        with self.assertRaises(TypeError):
            run_command([sys.executable, "-c", "pass"], max_output_bytes=True)

    def test_rejects_invalid_environment_boundaries(self) -> None:
        invalid_environments = ({"BAD-NAME": "x"}, {"OK": 1}, {"OK": "line\nvalue"})
        for environment in invalid_environments:
            with self.subTest(environment=environment), self.assertRaises((TypeError, ValueError)):
                run_command([sys.executable, "-c", "pass"], extra_env=cast(Mapping[str, str], environment))

    def test_environment_does_not_inherit_secrets(self) -> None:
        with patch.dict(os.environ, {"RELAY_SECRET": "hidden"}):
            result = run_command([sys.executable, "-c", "import os; print(os.getenv('RELAY_SECRET', 'missing'))"])
        self.assertEqual(result.stdout.strip(), "missing")

    def test_timeout_is_reported(self) -> None:
        result = run_command([sys.executable, "-c", "import time; time.sleep(1)"], timeout=0.01)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.returncode)

    def test_output_limit_is_shared_across_streams(self) -> None:
        result = run_command([sys.executable, "-c", "import sys; print('x' * 8, end=''); print('y' * 8, end='', file=sys.stderr)"], max_output_bytes=10)
        self.assertTrue(result.truncated)
        self.assertLessEqual(len(result.stdout.encode()) + len(result.stderr.encode()), 10)


if __name__ == "__main__":
    unittest.main()
