from __future__ import annotations

import argparse
import os
import sys

from llm_api_proxy_check.http_client import OpenAICompatibleHTTPClient
from llm_api_proxy_check.integrity import audit_stream
from llm_api_proxy_check.mock import MockClient, mock_sse
from llm_api_proxy_check.probes import run_fingerprint_suite
from llm_api_proxy_check.report import build_report, report_json
from llm_api_proxy_check.safe_cli import run_command

EXIT_OK = 0
EXIT_RISK = 1
EXIT_ERROR = 2

ENV_BASE_URL = "LLM_API_PROXY_CHECK_BASE_URL"
ENV_API_KEY = "LLM_API_PROXY_CHECK_API_KEY"
ENV_MODEL = "LLM_API_PROXY_CHECK_MODEL"
ENV_REF_BASE_URL = "LLM_API_PROXY_CHECK_REF_BASE_URL"
ENV_REF_API_KEY = "LLM_API_PROXY_CHECK_REF_API_KEY"
ENV_REF_MODEL = "LLM_API_PROXY_CHECK_REF_MODEL"


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


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _print_report(report, format_name: str) -> int:
    print(report_json(report) if format_name == "json" else report.markdown(), end="")
    if report.risk == "high":
        return EXIT_RISK
    return EXIT_OK


def _default_check_args(format_name: str = "markdown") -> argparse.Namespace:
    return argparse.Namespace(
        base_url=None,
        api_key=None,
        model=None,
        ref_base_url=None,
        ref_api_key=None,
        ref_model=None,
        timeout=30.0,
        format=format_name,
    )


def _check(args: argparse.Namespace) -> int:
    base_url = getattr(args, "base_url", None) or _env(ENV_BASE_URL)
    api_key = getattr(args, "api_key", None) or _env(ENV_API_KEY)
    model = getattr(args, "model", None) or _env(ENV_MODEL) or "gpt-4o-mini"
    timeout = float(getattr(args, "timeout", 30.0) or 30.0)
    format_name = getattr(args, "format", "markdown") or "markdown"
    if not base_url and not api_key:
        return _demo(format_name)
    if not base_url or not api_key:
        print(
            "llm-api-proxy-check: 真实检测需要同时提供 --base-url 与 --api-key"
            f"（或环境变量 {ENV_BASE_URL} / {ENV_API_KEY}）；仅本地演示请直接运行 check 且不传端点参数",
            file=sys.stderr,
        )
        return EXIT_ERROR
    try:
        target = OpenAICompatibleHTTPClient(base_url, api_key, model, timeout=timeout)
        ref_base = getattr(args, "ref_base_url", None) or _env(ENV_REF_BASE_URL)
        ref_key = getattr(args, "ref_api_key", None) or _env(ENV_REF_API_KEY)
        ref_model = getattr(args, "ref_model", None) or _env(ENV_REF_MODEL) or model
        if ref_base and ref_key:
            reference = OpenAICompatibleHTTPClient(ref_base, ref_key, ref_model, timeout=timeout)
        else:
            reference = target
        checks = run_fingerprint_suite(target, reference)
        report = build_report(checks)
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"llm-api-proxy-check: {error}", file=sys.stderr)
        return EXIT_ERROR
    return _print_report(report, format_name)


def _audit(command_args: list[str]) -> int:
    if not command_args:
        print("llm-api-proxy-check: audit 需要命令参数", file=sys.stderr)
        return EXIT_ERROR
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="llm-api-proxy-check",
        description="Check integrity of OpenAI-compatible LLM API proxies",
    )
    subparsers = parser.add_subparsers(dest="action")

    check = subparsers.add_parser("check", help="一键检测：无端点时跑本地 demo，有端点时检测真实代理")
    check.add_argument("--base-url", default=None, help=f"代理 Base URL，也可设 {ENV_BASE_URL}")
    check.add_argument("--api-key", default=None, help=f"API Key，也可设 {ENV_API_KEY}")
    check.add_argument("--model", default=None, help=f"模型名，默认 gpt-4o-mini，也可设 {ENV_MODEL}")
    check.add_argument("--ref-base-url", default=None, help=f"参考端点 Base URL，也可设 {ENV_REF_BASE_URL}")
    check.add_argument("--ref-api-key", default=None, help=f"参考端点 API Key，也可设 {ENV_REF_API_KEY}")
    check.add_argument("--ref-model", default=None, help=f"参考模型名，也可设 {ENV_REF_MODEL}")
    check.add_argument("--timeout", type=float, default=30.0, help="HTTP 超时秒数，默认 30")
    check.add_argument("--format", choices=("json", "markdown"), default="markdown")

    demo = subparsers.add_parser("demo", help="仅本地 Mock 演示（等同 check 无参数）")
    demo.add_argument("--format", choices=("json", "markdown"), default="markdown")

    command = subparsers.add_parser("audit", help="安全执行外部命令并返回其退出状态")
    command.add_argument("command", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    if args.action is None:
        return _check(_default_check_args())
    if args.action == "demo":
        return _demo(args.format)
    if args.action == "check":
        return _check(args)
    if args.action == "audit":
        command_args = args.command[1:] if args.command[:1] == ["--"] else args.command
        return _audit(command_args)
    parser.error(f"未知命令: {args.action}")
    return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
