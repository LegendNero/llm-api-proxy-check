from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from llm_api_proxy_check.config import UserConfig, load_config, save_config
from llm_api_proxy_check import __main__ as cli


class ConfigTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            original = UserConfig(
                base_url="https://proxy.example/v1",
                api_key="sk-test-secret-key",
                model="gpt-4o-mini",
                ref_base_url="https://api.openai.com/v1",
                ref_api_key="sk-ref-secret",
                ref_model="gpt-4o-mini",
                timeout=45.0,
            )
            saved = save_config(original, path)
            self.assertTrue(saved.is_file())
            loaded = load_config(path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.base_url, original.base_url)
            self.assertEqual(loaded.api_key, original.api_key)
            self.assertEqual(loaded.model, original.model)
            self.assertEqual(loaded.ref_base_url, original.ref_base_url)
            self.assertEqual(loaded.timeout, 45.0)
            masked = loaded.masked()
            self.assertNotIn("sk-test-secret-key", str(masked["api_key"]))
            self.assertIn("…", str(masked["api_key"]))

    def test_check_reads_saved_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            save_config(
                UserConfig(base_url="https://proxy.example/v1", api_key="sk-from-file", model="demo-model"),
                path,
            )
            args = cli._default_check_args(format_name="json")
            with mock.patch.dict(os.environ, {"LLM_API_PROXY_CHECK_CONFIG": str(path)}, clear=False):
                with mock.patch.object(cli, "OpenAICompatibleHTTPClient") as client_cls:
                    with mock.patch.object(cli, "run_fingerprint_suite", return_value=[]):
                        with mock.patch.object(cli, "_run_stream_checks", return_value=()):
                            with mock.patch.object(cli, "build_report") as build:
                                report = mock.Mock()
                                report.risk = "low"
                                report.markdown.return_value = "ok\n"
                                build.return_value = report
                                with mock.patch.object(cli, "report_json", return_value='{"risk":"low"}'):
                                    code = cli._check(args)
                self.assertEqual(code, 0)
                client_cls.assert_called()
                kwargs = client_cls.call_args
                self.assertEqual(kwargs.args[0], "https://proxy.example/v1")
                self.assertEqual(kwargs.args[1], "sk-from-file")
                self.assertEqual(kwargs.args[2], "demo-model")

    def test_check_demo_flag_ignores_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            save_config(UserConfig(base_url="https://proxy.example/v1", api_key="sk-x", model="m"), path)
            args = cli._default_check_args(format_name="json")
            args.demo = True
            with mock.patch.dict(os.environ, {"LLM_API_PROXY_CHECK_CONFIG": str(path)}, clear=False):
                code = cli._check(args)
            self.assertEqual(code, 1)

    def test_config_path_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "config.json"
            with mock.patch.dict(os.environ, {"LLM_API_PROXY_CHECK_CONFIG": str(path)}, clear=False):
                code = cli.main(["config-path"])
            self.assertEqual(code, 0)

    def test_save_payload_has_no_extra_nulls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            save_config(UserConfig(base_url="https://x/v1", api_key="k", model="m"), path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("ref_api_key", raw)
            self.assertEqual(raw["base_url"], "https://x/v1")


if __name__ == "__main__":
    unittest.main()
