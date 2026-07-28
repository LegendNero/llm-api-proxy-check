# llm-api-proxy-check

[English](README.md) | [中文](README_zh.md)

基于 Python 标准库的工具包，用于**检测 OpenAI 兼容 LLM API 代理（中转 / 中间层）的完整性**。

可发现常见风险信号：模型替换迹象、SSE 流篡改、工具调用被改写、用量计费异常等。本地 Mock 演示**无需云账号或 API Key**。

搜索关键词：**LLM**、**API**、**proxy**、OpenAI 兼容、完整性、SSE、工具调用、审计、指纹。

## 功能

- **指纹套件**：tokenizer 计数、输出分布距离、能力题、长上下文 Needle 探针
- **SSE 完整性**：事件解析、`[DONE]` 控制帧、JSON 合法性、usage 形态检查
- **工具调用完整性**：跨流式 delta 重组，检测 name/arguments 被重写
- **风险评分**：0–100 加权分，结果含 `pass` / `fail` / `unknown` 与覆盖率
- **安全 CLI 适配层**：`subprocess` + `shell=False`、超时与输出上限
- **CI 就绪**：GitHub Action 跑测试、ruff、mypy 与 Mock 演示报告
- **零运行时依赖**：仅需 Python 3.9+ 标准库

## 快速开始

```bash
# Mock 演示（无需 API Key）
python -m llm_api_proxy_check demo --format markdown

# 供 CI 使用的 JSON 报告
python -m llm_api_proxy_check demo --format json

# 运行测试
python -m unittest discover -s tests -v
```

可选安装为命令行工具：

```bash
pip install -e .
llm-api-proxy-check demo --format markdown
```

## 真实接口（可选）

通过 HTTP 客户端路径接入 OpenAI 兼容的 `base_url` 与 API Key（见 `llm_api_proxy_check/http_client.py` 与 `python -m llm_api_proxy_check --help`）。**切勿将密钥提交到仓库。**

## 退出码

| 码 | 含义 |
|----|------|
| 0 | 审计通过（低风险） |
| 1 | 检测到风险 |
| 2 | 参数或运行错误 |

## 目录结构

```
llm_api_proxy_check/   核心库 + CLI
tests/                 unittest 测试
.github/               CI 工作流
IMPLEMENTATION.md      MVP 设计说明
```

## 许可证

MIT
