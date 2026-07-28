from __future__ import annotations

import getpass
import sys
from typing import TextIO

from llm_api_proxy_check.config import UserConfig, default_config_path, load_config, save_config
from llm_api_proxy_check.http_client import OpenAICompatibleHTTPClient


def _print(message: str, *, file: TextIO = sys.stdout) -> None:
    print(message, file=file)


def _prompt(label: str, *, default: str | None = None, required: bool = True, secret: bool = False, keep_secret_hint: bool = False) -> str:
    if secret and keep_secret_hint and default:
        suffix = " [回车保留已有 Key]"
    elif default and not secret:
        suffix = f" [{default}]"
    else:
        suffix = ""
    while True:
        try:
            raw = getpass.getpass(f"{label}{suffix}: ") if secret else input(f"{label}{suffix}: ")
        except EOFError as error:
            raise RuntimeError("输入已中断，设置未完成") from error
        value = raw.strip()
        if not value and default is not None:
            return default
        if value:
            return value
        if not required:
            return ""
        _print("这项是必填的，请再输入一次。", file=sys.stderr)


def _prompt_yes_no(label: str, *, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        try:
            raw = input(f"{label} ({hint}): ").strip().lower()
        except EOFError as error:
            raise RuntimeError("输入已中断，设置未完成") from error
        if not raw:
            return default
        if raw in {"y", "yes", "是", "好"}:
            return True
        if raw in {"n", "no", "否"}:
            return False
        _print("请输入 y 或 n。", file=sys.stderr)


def _normalize_base_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ValueError("地址必须以 http:// 或 https:// 开头")
    if url.endswith("/chat/completions"):
        url = url[: -len("/chat/completions")].rstrip("/")
    return url


def _smoke_test(config: UserConfig) -> None:
    client = OpenAICompatibleHTTPClient(config.base_url, config.api_key, config.model, timeout=min(config.timeout, 20.0))
    reply = client.complete("只回复一个字：好", max_tokens=8)
    if not isinstance(reply, str) or not reply.strip():
        raise RuntimeError("连通性测试失败：模型没有返回内容")


def run_setup(*, input_stream: TextIO | None = None, output_stream: TextIO | None = None) -> UserConfig:
    if input_stream is not None:
        raise RuntimeError("当前向导仅支持交互式终端输入")
    out = output_stream or sys.stdout
    path = default_config_path()
    existing = load_config(path)

    _print("", file=out)
    _print("========================================", file=out)
    _print("  llm-api-proxy-check 快速设置向导", file=out)
    _print("========================================", file=out)
    _print("只需填 3 项就能开始检测；参考端点可选。", file=out)
    _print(f"配置将保存到: {path}", file=out)
    _print("API Key 只会保存在本机，不会上传。", file=out)
    _print("", file=out)

    if existing is not None:
        _print("检测到已有配置：", file=out)
        masked = existing.masked()
        _print(f"  代理地址: {masked.get('base_url')}", file=out)
        _print(f"  模型名称: {masked.get('model')}", file=out)
        _print(f"  API Key : {masked.get('api_key')}", file=out)
        if not _prompt_yes_no("要覆盖现有配置吗？", default=True):
            _print("已保留原配置，未做修改。", file=out)
            return existing

    base_url = _normalize_base_url(
        _prompt("1/3 代理 Base URL（例如 https://api.openai.com/v1）", default=existing.base_url if existing else None)
    )
    api_key = _prompt("2/3 API Key（输入时不显示）", secret=True, default=None if not existing else None)
    if not api_key and existing is not None:
        api_key = existing.api_key
    if not api_key:
        raise RuntimeError("API Key 不能为空")
    model = _prompt("3/3 模型名", default=(existing.model if existing else "gpt-4o-mini"))

    ref_base_url = None
    ref_api_key = None
    ref_model = None
    if _prompt_yes_no("要不要再填一个「官方/可信」参考端点？（可选，用于更准的对比）", default=False):
        ref_base_url = _normalize_base_url(_prompt("参考端点 Base URL", default=existing.ref_base_url if existing else None))
        ref_api_key = _prompt(
            "参考端点 API Key（输入时不显示）",
            secret=True,
            default=existing.ref_api_key if existing and existing.ref_api_key else None,
            keep_secret_hint=bool(existing and existing.ref_api_key),
        )
        if not ref_api_key:
            raise RuntimeError("已选择参考端点，但 API Key 为空")
        ref_model = _prompt("参考模型名", default=(existing.ref_model if existing and existing.ref_model else model))

    config = UserConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        ref_base_url=ref_base_url,
        ref_api_key=ref_api_key,
        ref_model=ref_model,
        timeout=existing.timeout if existing else 30.0,
    )

    if _prompt_yes_no("现在做一次连通性测试吗？", default=True):
        _print("正在测试连接…", file=out)
        try:
            _smoke_test(config)
            _print("连通性测试通过。", file=out)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            _print(f"连通性测试失败: {error}", file=sys.stderr)
            if not _prompt_yes_no("仍然保存这份配置吗？", default=False):
                raise RuntimeError("已取消保存") from error

    saved = save_config(config, path)
    _print("", file=out)
    _print(f"已保存配置: {saved}", file=out)
    _print("下一步直接运行：", file=out)
    _print("  llm-api-proxy-check check", file=out)
    _print("即可自动读取配置，完成指纹 + 流式 SSE + 工具完整性检测。", file=out)
    _print("", file=out)
    return config


def show_config() -> int:
    path = default_config_path()
    config = load_config(path)
    if config is None:
        print(f"还没有配置文件: {path}")
        print("请先运行: llm-api-proxy-check setup")
        return 2
    masked = config.masked()
    print(f"配置文件: {path}")
    for key in ("base_url", "model", "api_key", "ref_base_url", "ref_model", "ref_api_key", "timeout"):
        value = masked.get(key)
        if value is None:
            continue
        print(f"  {key}: {value}")
    return 0
