from __future__ import annotations

from collections.abc import Iterable

from llm_api_proxy_check.models import CheckResult, Status

_ADVICE: dict[str, dict[str, str]] = {
    "tokenizer_fingerprint": {
        "fail": "分词计数与参考端点偏差过大，常见于「名义模型」和实际后端不一致。建议：1) 在 setup 里配置官方/可信参考端点再测；2) 向供应商确认真实 model id；3) 换一家中转或要求提供官方直连对照。",
        "unknown": "未能完成分词对比（无参考端点、接口失败，或为省 token 已跳过）。若要验证换模风险，请配置参考端点后使用 `check --full`。",
    },
    "output_distribution": {
        "fail": "输出概率分布与参考差异大，可能被换小模型或改写采样。建议对照官方同一 model 复测；避免只看营销名，要求供应商锁定模型版本。",
        "unknown": "分布探针未完成（多数中转不支持 logprobs，或省 token 模式已跳过）。可改用 `--full` 并配置支持 logprobs 的参考端点。",
    },
    "capability_baseline": {
        "fail": "基础算术/字符串能力未通过，模型可能被降级或指令被中间层改写。建议：换模型名重试、对比官方同题答案、检查系统提示/安全策略是否改写了输出。",
        "unknown": "能力探针请求失败。先检查 Key、余额、模型名与 Base URL 是否指向 `/v1`。",
    },
    "needle_retrieval": {
        "fail": "长/中上下文定位失败，可能被截断上下文、换弱模型或中间层摘要。建议：确认 max context 宣传是否属实；用更短业务上下文压测；要求供应商关闭「偷压缩」。",
        "unknown": "Needle 未跑完（超安全上限或请求失败）。省 token 模式使用短上下文；需要更强结论时用 `--full`。",
    },
    "sse_json": {
        "fail": "流式 SSE 不是合法 JSON 事件流，客户端可能解析失败。建议：换支持标准 OpenAI SSE 的中转；抓包看是否夹杂 HTML/网关错误页；关闭非标准心跳格式。",
        "unknown": "流式请求未成功，无法判断 SSE。检查网络、TLS、路径是否为 `.../v1/chat/completions`。",
    },
    "sse_done": {
        "fail": "`[DONE]` 缺失、重复或不在末尾，流式结束不可靠。建议要求供应商按 OpenAI 规范结束流；业务侧加超时与不完整缓冲保护。",
        "unknown": "未拿到完整流，无法验证 `[DONE]`。",
    },
    "usage_integrity": {
        "fail": "usage/计费字段异常或与预期严重不符，存在虚高计量风险。建议：保存原始响应中的 usage；同一 prompt 对照官方计量；与供应商对账并要求返回标准 usage。",
        "unknown": "响应未带 `usage.total_tokens` 或格式非法。要求中转在非流式/流式（`stream_options.include_usage`）中返回标准 usage。",
    },
    "tool_integrity": {
        "fail": "工具调用的 name/参数被改写或未按要求调用，Agent/函数调用场景高风险。建议：禁用会改写 tool 的「增强网关」；换支持 tools 的线路；关键业务侧校验 tool name 白名单。",
        "unknown": "工具流未成功（模型拒 tools 或中转不支持）。可先 `check --skip-tools` 只验 SSE；或换支持 function calling 的模型。",
    },
}


def advice_for_checks(checks: Iterable[CheckResult]) -> tuple[str, ...]:
    lines: list[str] = []
    for check in checks:
        if check.status is Status.PASS:
            continue
        bucket = _ADVICE.get(check.name)
        if not bucket:
            lines.append(f"- **{check.name}**（{check.status.value}）：请根据证据排查供应商与配置，必要时换源复测。")
            continue
        text = bucket.get(check.status.value) or bucket.get("unknown")
        if text:
            lines.append(f"- **{check.name}**（{check.status.value}）：{text}")
    if not lines:
        lines.append("- 未发现失败项。若未配置参考端点，指纹类结论有限，建议在 setup 中增加官方对照后再测一次。")
    return tuple(lines)
