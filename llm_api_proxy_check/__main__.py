from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from llm_api_proxy_check.config import UserConfig, default_config_path, load_config
from llm_api_proxy_check.http_client import OpenAICompatibleHTTPClient
from llm_api_proxy_check.integrity import audit_stream
from llm_api_proxy_check.mock import MockClient, mock_sse
from llm_api_proxy_check.probes import economy_config, full_config, run_fingerprint_suite
from llm_api_proxy_check.report import build_report, report_json
from llm_api_proxy_check.safe_cli import run_command
from llm_api_proxy_check.usage import TokenUsage
from llm_api_proxy_check.wizard import run_setup, show_config

EXIT_OK = 0
EXIT_RISK = 1
EXIT_ERROR = 2

ENV_BASE_URL = "LLM_API_PROXY_CHECK_BASE_URL"
ENV_API_KEY = "LLM_API_PROXY_CHECK_API_KEY"
ENV_MODEL = "LLM_API_PROXY_CHECK_MODEL"
ENV_REF_BASE_URL = "LLM_API_PROXY_CHECK_REF_BASE_URL"
ENV_REF_API_KEY = "LLM_API_PROXY_CHECK_REF_API_KEY"
ENV_REF_MODEL = "LLM_API_PROXY_CHECK_REF_MODEL"

TOOL_PROBE_NAME = "get_weather"
TOOL_PROBE_CITY = "北京"
TOOL_DEFINITION: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": TOOL_PROBE_NAME,
        "description": "查询城市天气",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名"}},
            "required": ["city"],
        },
    },
}


def _demo(format_name: str) -> int:
    checks = run_fingerprint_suite(MockClient(degraded=True), MockClient(degraded=False), config=full_config())
    stream = audit_stream(
        mock_sse(tampered=True),
        expected_usage=80,
        original_tools=({"name": "search", "arguments": '{"query":"status"}'},),
    )
    usage = TokenUsage()
    usage.record({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, label="demo")
    usage.requests = 0
    usage.total_tokens = 0
    report = build_report((*checks, *stream.checks), token_usage=usage, mode="demo")
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
        timeout=None,
        format=format_name,
        demo=False,
        skip_stream=False,
        skip_tools=False,
        full=False,
        economy=True,
    )


def _progress(enabled: bool, message: str) -> None:
    if enabled:
        print(message, file=sys.stderr)


def _resolve_config(args: argparse.Namespace) -> UserConfig | None:
    file_config = load_config()
    base_url = getattr(args, "base_url", None) or _env(ENV_BASE_URL) or (file_config.base_url if file_config else None)
    api_key = getattr(args, "api_key", None) or _env(ENV_API_KEY) or (file_config.api_key if file_config else None)
    model = getattr(args, "model", None) or _env(ENV_MODEL) or (file_config.model if file_config else None) or "gpt-4o-mini"
    timeout_arg = getattr(args, "timeout", None)
    if timeout_arg is None:
        timeout = file_config.timeout if file_config else 30.0
    else:
        timeout = float(timeout_arg)
    if not base_url or not api_key:
        return None
    ref_base = getattr(args, "ref_base_url", None) or _env(ENV_REF_BASE_URL) or (file_config.ref_base_url if file_config else None)
    ref_key = getattr(args, "ref_api_key", None) or _env(ENV_REF_API_KEY) or (file_config.ref_api_key if file_config else None)
    ref_model = getattr(args, "ref_model", None) or _env(ENV_REF_MODEL) or (file_config.ref_model if file_config else None) or model
    return UserConfig(
        base_url=str(base_url).strip(),
        api_key=str(api_key).strip(),
        model=str(model).strip(),
        ref_base_url=str(ref_base).strip() if ref_base else None,
        ref_api_key=str(ref_key).strip() if ref_key else None,
        ref_model=str(ref_model).strip() if ref_model else None,
        timeout=float(timeout) if float(timeout) > 0 else 30.0,
    )


def _probe_config(args: argparse.Namespace):
    if bool(getattr(args, "full", False)):
        return full_config()
    return economy_config()


def _run_stream_checks(client: OpenAICompatibleHTTPClient, *, skip_tools: bool, verbose: bool) -> tuple:
    from llm_api_proxy_check.models import CheckResult, Status

    if skip_tools:
        _progress(verbose, "→ 正在检测流式 SSE（短回复，省 token）…")
        raw = client.stream_chat([{"role": "user", "content": "只回复：好"}], max_tokens=4, label="sse")
        stream = audit_stream(raw)
        return stream.checks

    _progress(verbose, "→ 正在检测流式 SSE + 工具调用 …")
    try:
        raw = client.stream_chat(
            [{"role": "user", "content": f"调用工具 {TOOL_PROBE_NAME}，city={TOOL_PROBE_CITY}，不要直接回答。"}],
            tools=[TOOL_DEFINITION],
            tool_choice={"type": "function", "function": {"name": TOOL_PROBE_NAME}},
            max_tokens=32,
            label="sse+tools",
        )
        expected_tools = ({"name": TOOL_PROBE_NAME},)
        stream = audit_stream(raw, original_tools=expected_tools)
        return stream.checks
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        _progress(verbose, f"  工具流失败，改为普通短流式：{error}")
        try:
            raw = client.stream_chat([{"role": "user", "content": "只回复：好"}], max_tokens=4, label="sse-fallback")
            stream = audit_stream(raw)
            fallback = list(stream.checks)
            fallback.append(CheckResult("tool_integrity", Status.UNKNOWN, None, 1, f"tool stream failed: {error}", 4))
            return tuple(fallback)
        except (OSError, RuntimeError, TypeError, ValueError) as stream_error:
            return (
                CheckResult("sse_json", Status.FAIL, None, None, str(stream_error), 4),
                CheckResult("sse_done", Status.UNKNOWN, None, 1, "stream request failed", 3),
                CheckResult("usage_integrity", Status.UNKNOWN, None, None, "stream request failed", 3),
                CheckResult("tool_integrity", Status.UNKNOWN, None, 1, f"tool stream failed: {error}", 4),
            )


def _merge_client_usage(*clients: object) -> TokenUsage:
    total = TokenUsage()
    seen: set[int] = set()
    for client in clients:
        ident = id(client)
        if ident in seen:
            continue
        seen.add(ident)
        usage = getattr(client, "token_usage", None)
        if isinstance(usage, TokenUsage):
            total = total.merge(usage)
    return total


def _check(args: argparse.Namespace) -> int:
    format_name = getattr(args, "format", "markdown") or "markdown"
    force_demo = bool(getattr(args, "demo", False))
    verbose = format_name != "json"
    if force_demo:
        return _demo(format_name)

    config = _resolve_config(args)
    if config is None:
        has_partial = bool(
            getattr(args, "base_url", None)
            or getattr(args, "api_key", None)
            or _env(ENV_BASE_URL)
            or _env(ENV_API_KEY)
        )
        if has_partial:
            print(
                "llm-api-proxy-check: 真实检测需要同时提供代理地址和 API Key。\n"
                f"  方式 1（推荐）: llm-api-proxy-check setup\n"
                f"  方式 2: --base-url 与 --api-key，或环境变量 {ENV_BASE_URL} / {ENV_API_KEY}\n"
                "  仅本地演示: llm-api-proxy-check check --demo",
                file=sys.stderr,
            )
            return EXIT_ERROR
        if load_config() is None and not getattr(args, "base_url", None) and not _env(ENV_BASE_URL):
            _progress(verbose, "未找到已保存配置，先跑本地演示。正式使用请运行: llm-api-proxy-check setup")
        return _demo(format_name)

    try:
        probe_cfg = _probe_config(args)
        mode = probe_cfg.mode
        _progress(verbose, f"使用配置检测: {config.base_url} / model={config.model} / mode={mode}")
        if mode == "economy":
            _progress(verbose, "省 token 模式：短 Needle、合并能力题、默认同端点不跑对照指纹；需要更全请加 --full")
        target = OpenAICompatibleHTTPClient(config.base_url, config.api_key, config.model, timeout=config.timeout)
        if config.ref_base_url and config.ref_api_key:
            reference = OpenAICompatibleHTTPClient(
                config.ref_base_url,
                config.ref_api_key,
                config.ref_model or config.model,
                timeout=config.timeout,
            )
            _progress(verbose, f"参考端点: {config.ref_base_url}")
        else:
            reference = target
            _progress(verbose, "未配置参考端点：跳过耗 token 的对照指纹，优先测能力/SSE/工具")

        _progress(verbose, "→ 正在跑指纹套件 …")
        checks = list(run_fingerprint_suite(target, reference, config=probe_cfg))

        if not getattr(args, "skip_stream", False):
            stream_checks = _run_stream_checks(
                target,
                skip_tools=bool(getattr(args, "skip_tools", False)),
                verbose=verbose,
            )
            checks.extend(stream_checks)
        else:
            _progress(verbose, "已跳过流式 / 工具检测")

        usage = _merge_client_usage(target, reference)
        report = build_report(checks, token_usage=usage, mode=mode)
        _progress(verbose, f"检测完成。{usage.summary_line()}")
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"llm-api-proxy-check: {error}", file=sys.stderr)
        print("若还没设置过，可先运行: llm-api-proxy-check setup", file=sys.stderr)
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


def _setup() -> int:
    try:
        run_setup()
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"llm-api-proxy-check: {error}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="llm-api-proxy-check",
        description="检测 OpenAI 兼容 LLM API 代理完整性（默认省 token；结束显示用量与处理建议）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "快速上手:\n"
            "  1) llm-api-proxy-check setup\n"
            "  2) llm-api-proxy-check check          # 默认 economy，少耗 token\n"
            "  3) llm-api-proxy-check check --full   # 更全、更费 token\n"
            "  4) llm-api-proxy-check check --demo   # 本地演示\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="action")

    check = subparsers.add_parser("check", help="一键检测：默认省 token；报告含用量与处理建议")
    check.add_argument("--base-url", default=None, help=f"代理 Base URL，也可设 {ENV_BASE_URL} 或先 setup")
    check.add_argument("--api-key", default=None, help=f"API Key，也可设 {ENV_API_KEY} 或先 setup")
    check.add_argument("--model", default=None, help=f"模型名，默认读配置或 gpt-4o-mini，也可设 {ENV_MODEL}")
    check.add_argument("--ref-base-url", default=None, help=f"参考端点 Base URL，也可设 {ENV_REF_BASE_URL}")
    check.add_argument("--ref-api-key", default=None, help=f"参考端点 API Key，也可设 {ENV_REF_API_KEY}")
    check.add_argument("--ref-model", default=None, help=f"参考模型名，也可设 {ENV_REF_MODEL}")
    check.add_argument("--timeout", type=float, default=None, help="HTTP 超时秒数，默认读配置或 30")
    check.add_argument("--format", choices=("json", "markdown"), default="markdown")
    check.add_argument("--demo", action="store_true", help="强制本地 Mock 演示，不读真实配置")
    check.add_argument("--skip-stream", action="store_true", help="跳过流式 SSE / 工具，进一步省 token")
    check.add_argument("--skip-tools", action="store_true", help="流式只测 SSE，不测工具")
    check.add_argument("--full", action="store_true", help="完整模式：更多样本、长 Needle、分布探针（更费 token）")
    check.add_argument("--economy", action="store_true", default=False, help="省 token 模式（默认，可不写）")

    demo = subparsers.add_parser("demo", help="仅本地 Mock 演示（等同 check --demo）")
    demo.add_argument("--format", choices=("json", "markdown"), default="markdown")

    subparsers.add_parser("setup", help="中文交互向导：保存代理地址 / API Key / 模型到本机")
    subparsers.add_parser("show-config", help="查看本机已保存配置（密钥脱敏）")
    subparsers.add_parser("config-path", help="打印配置文件路径")

    command = subparsers.add_parser("audit", help="安全执行外部命令并返回其退出状态")
    command.add_argument("command", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    if args.action is None:
        return _check(_default_check_args())
    if args.action == "demo":
        return _demo(args.format)
    if args.action == "check":
        return _check(args)
    if args.action == "setup":
        return _setup()
    if args.action == "show-config":
        return show_config()
    if args.action == "config-path":
        print(default_config_path())
        return EXIT_OK
    if args.action == "audit":
        command_args = args.command[1:] if args.command[:1] == ["--"] else args.command
        return _audit(command_args)
    parser.error(f"未知命令: {args.action}")
    return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
