# llm-api-proxy-check

[English](README.md) | [中文](README_zh.md)

基于 Python 标准库的工具包，用于**检测 OpenAI 兼容 LLM API 代理（中转 / 中间层）的完整性**。

可发现常见风险信号：模型替换迹象、SSE 流篡改、工具调用被改写、用量计费异常等。本地 Mock 演示**无需云账号或 API Key**。

搜索关键词：**LLM**、**API**、**proxy**、OpenAI 兼容、完整性、SSE、工具调用、审计、指纹。

## 一键安装

**macOS / Linux**

```bash
curl -fsSL https://raw.githubusercontent.com/LegendNero/llm-api-proxy-check/main/install.sh | bash
```

**Windows（PowerShell）**

```powershell
irm https://raw.githubusercontent.com/LegendNero/llm-api-proxy-check/main/install.ps1 | iex
```

要求：Python **3.9+**。脚本会在 `~/.local/share/llm-api-proxy-check` 创建独立 venv，从本 GitHub 仓库安装，并把启动器放到 `~/.local/bin`。

手动安装（Homebrew / PEP 668 环境建议用 venv）：

```bash
python3 -m venv ~/.venvs/llm-api-proxy-check
~/.venvs/llm-api-proxy-check/bin/pip install "git+https://github.com/LegendNero/llm-api-proxy-check.git"
```

## 日常命令

```bash
# 本地演示（无需 API Key）— 安装后的默认入口
llm-api-proxy-check check

# 真实代理检测
llm-api-proxy-check check --base-url https://your-proxy.example/v1 --api-key "$KEY" --model gpt-4o-mini

# CI 用 JSON
llm-api-proxy-check check --format json
```

未装上控制台命令时：

```bash
python -m llm_api_proxy_check check
```

可选环境变量：

| 变量 | 含义 |
|------|------|
| `LLM_API_PROXY_CHECK_BASE_URL` | 代理 Base URL |
| `LLM_API_PROXY_CHECK_API_KEY` | API Key |
| `LLM_API_PROXY_CHECK_MODEL` | 模型名（默认 `gpt-4o-mini`） |
| `LLM_API_PROXY_CHECK_REF_BASE_URL` | 可选参考端点 |
| `LLM_API_PROXY_CHECK_REF_API_KEY` | 可选参考 Key |
| `LLM_API_PROXY_CHECK_REF_MODEL` | 可选参考模型 |

**切勿将密钥提交到仓库。**

## 功能

- **指纹套件**：tokenizer 计数、输出分布距离、能力题、长上下文 Needle 探针
- **SSE 完整性**：事件解析、`[DONE]` 控制帧、JSON 合法性、usage 形态检查
- **工具调用完整性**：跨流式 delta 重组，检测 name/arguments 被重写
- **风险评分**：0–100 加权分，结果含 `pass` / `fail` / `unknown` 与覆盖率
- **安全 CLI 适配层**：`subprocess` + `shell=False`、超时与输出上限
- **CI 就绪**：GitHub Action 跑测试、ruff、mypy 与 Mock 演示报告
- **零运行时依赖**：仅需 Python 3.9+ 标准库

## 退出码

| 码 | 含义 |
|----|------|
| 0 | 非高风险（通过或中低风险按当前策略不记为失败退出） |
| 1 | 检测到高风险 |
| 2 | 参数或运行错误 |

## 目录结构

```
llm_api_proxy_check/   核心库 + CLI
install.sh             macOS/Linux 一键安装
install.ps1            Windows 一键安装
tests/                 unittest 测试
.github/               CI 工作流
IMPLEMENTATION.md      MVP 设计说明
```

## 许可证

MIT
