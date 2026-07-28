from __future__ import annotations

import argparse
import sys

from llm_api_proxy_check.integrity import audit_stream
from llm_api_proxy_check.mock import MockClient, mock_sse
from llm_api_proxy_check.probes import run_fingerprint_suite
from llm_api_proxy_check.report import build_report, report_json
from llm_api_proxy_check.safe_cli import run_command

EXIT_OK = 0
EXIT_RISK = 1
EXIT_ERROR = 2


def _demo(format_name: str) -> int:
    checks = run_fingerprint_suite(MockClient(degraded=True), MockClient(degraded=False))
    stream = audit_stream(
        mock_sse(tampered=True),
        expected_usage=80,
        original_tools=({"name": "search", "arguments": '{"query":"status"}'},),
    )
    report = build_report((*checks, *stream.checks))
    print(report_json(report) if format_name == "json" else report.markdown(), end="")
    return EXIT_RISK if report.risk == "high" else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llm-api-proxy-check")
    subparsers = parser.add_subparsers(dest="action", required=True)
    demo = subparsers.add_parser("demo")
    demo.add_argument("--format", choices=("json", "markdown"), default="markdown")
    command = subparsers.add_parser("audit")
    command.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.action == "demo":
        return _demo(args.format)
    command_args = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command_args:
        parser.error("audit 需要命令参数")
    try:
        result = run_command(command_args)
    except (OSError, TypeError, ValueError) as error:
        print(f"llm-api-proxy-check: {error}", file=sys.stderr)
        return EXIT_ERROR
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.timed_out or result.truncated:
        return EXIT_ERROR
    return EXIT_OK if result.succeeded else EXIT_RISK


if __name__ == "__main__":
    raise SystemExit(main())
