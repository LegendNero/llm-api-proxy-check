# llm-api-proxy-check 实施说明

本文描述当前开源 MVP 的真实实现，便于开发者理解模块边界与验收标准。  
产品定位：检测 **OpenAI 兼容 LLM API 代理（中转）** 的完整性风险信号。

## 1. 目标与范围

已实现：

1. **安全 CLI 适配层**：参数数组调用外部命令，`shell=False`，限制超时、输出大小与环境变量继承。
2. **指纹与 Needle 探针**：tokenizer 计数、输出分布（JSD）、客观能力题、长上下文 Needle。
3. **SSE 与工具完整性**：解析 SSE、校验 `[DONE]`、usage 形态、跨 delta 重组 tool call 并检测改写。
4. **风险评分报告**：固定检查集加权 0–100 分，输出 JSON / Markdown；证据脱敏。
5. **真实代理 HTTP 客户端**：非流式 chat + 流式 SSE（含可选 tools）。
6. **本机配置与中文 setup 向导**：保存 Base URL / API Key / 模型（及可选参考端点），`check` 自动读取。
7. **一键安装与 CI**：`install.sh` / `install.ps1`；GitHub Action 跑测试、ruff、mypy、Mock 演示。

**不在本阶段**：厂商专有 SDK、PII 脱敏网关、在线数据库、企业控制台、计费对账平台。

## 2. 技术约束

- Python **3.9+**（`pyproject.toml`：`requires-python = ">=3.9"`）。
- **运行时零第三方依赖**，仅标准库。
- 探针面向 `ProbeClient` 协议；Mock 与 `OpenAICompatibleHTTPClient` 可替换。
- 外部命令必须走 `safe_cli.run_command`，禁止 shell 拼接。
- 报告与日志不得输出完整 API Key、Authorization 或敏感请求体。
- 退出码：`0` 非高风险，`1` 高风险，`2` 参数/运行错误。

## 3. 模块一览

| 模块 | 职责 |
|------|------|
| `__main__.py` | CLI：`setup` / `check` / `demo` / `show-config` / `config-path` / `audit`；默认 economy |
| `config.py` | 本机 `config.json` 读写、脱敏、路径（XDG / APPDATA / 环境变量覆盖） |
| `wizard.py` | 中文交互向导、可选连通性 smoke test |
| `http_client.py` | OpenAI 兼容 HTTP：tokenize / complete / distribution / stream_chat；累计 `TokenUsage` |
| `probes.py` | 指纹套件、`economy_config` / `full_config`、`run_fingerprint_suite` |
| `integrity.py` | SSE 解析、`audit_stream`、tool 匹配（含 JSON 参数归一） |
| `usage.py` | 请求级 token 累加、`summary_line` |
| `advice.py` | 按检查项 fail/unknown 生成处理建议 |
| `report.py` | 固定权重评分、`AuditReport`（含 mode / token_usage / advice）、Markdown/JSON、脱敏 |
| `models.py` | `Status` / `CheckResult` / `CommandResult` |
| `mock.py` | 本地 Mock 客户端与可篡改 SSE |
| `safe_cli.py` | 安全 `subprocess` 封装 |

## 4. 模块设计要点

### 4.1 CLI 与配置优先级

`check` 解析端点顺序（后者仅在前者缺失时使用）：

1. 命令行 `--base-url` / `--api-key` / …
2. 环境变量 `LLM_API_PROXY_CHECK_*`
3. 本机配置文件（`setup` 写入）

无任何端点时：跑本地 **Mock demo**（高风险示例报告）。  
`--demo` 强制 Mock，忽略已保存配置。  
有配置时默认 **economy**：短 Needle、合并能力题、同端点跳过对照指纹、默认不跑 logprobs 分布；串联 **能力/Needle + 流式 SSE + 工具**（`--skip-stream` / `--skip-tools` 再裁剪；`--full` 打开完整探针）。  
报告附带 `token_usage` 与 `advice`（Markdown 含「发现的问题怎么处理」）。
### 4.2 安全命令执行

`safe_cli.run_command`：

- 校验参数数量/长度/控制字符；
- 仅继承白名单环境（如 `PATH`、`LANG` 等）；
- 超时与共享输出字节上限；
- 返回 `CommandResult`（含 timeout / truncated）。

`audit` 子命令仅演示该适配层，不解析 LLM 业务结果。

### 4.3 指纹探针

`probes.py` 中 `ProbeClient` 协议：`tokenize` / `distribution` / `complete`。

- **tokenizer_fingerprint**：多样本 token 数相对偏差。
- **output_distribution**：Jensen–Shannon；空或非有限分布 → `unknown`。
- **capability_baseline**：固定算术/反转题。
- **needle_retrieval**：答案须与 needle **完全一致**（防回声攻击）；超安全上下文上限 → `unknown`。

单项探针异常隔离为 `unknown`，不中断整套。

### 4.4 SSE 与工具

`integrity.py`：

- 控制帧使用 `SSEControlFrame` 枚举，避免 JSON 字段伪造 `[DONE]`。
- `[DONE]` 必须恰好一次且位于末尾。
- tool call 按 `index` / `id` 跨事件拼接 `name` / `arguments`。
- 参数比较：尝试 JSON 解析后做字典子集匹配，降低空白/键序噪音。
- 无期望 usage 时：校验 usage 形态（有合法 `total_tokens` 可通过形态检查）。

### 4.5 HTTP 客户端

`OpenAICompatibleHTTPClient`：

- `chat/completions` 非流式用于指纹；
- `stream_chat` 读取 SSE 正文，有字节上限防爆内存；
- 可选 `tools` / `tool_choice` / `stream_options.include_usage`。

### 4.6 评分

`report.build_report` 使用**固定检查名与权重**（未跑的项记 `unknown` 并半权惩罚），保证覆盖率可比：

| 检查 | 权重（示意） |
|------|----------------|
| tokenizer_fingerprint | 2 |
| output_distribution | 2 |
| capability_baseline | 2 |
| needle_retrieval | 3 |
| sse_json | 4 |
| sse_done | 3 |
| usage_integrity | 3 |
| tool_integrity | 4 |

风险：`score ≥ 85` → low；`≥ 60` → medium；否则 high。

## 5. 数据流

```
setup → config.json
         ↓
check → 解析配置/环境/参数
         ↓
OpenAICompatibleHTTPClient 或 MockClient
         ↓
run_fingerprint_suite → CheckResult[]
stream_chat → audit_stream → CheckResult[]
         ↓
build_report → Markdown / JSON → 退出码
```

CI 以退出码与 JSON artifact 为准；人读用 Markdown。

## 6. 安全边界

- 配置文件写入后尽量 `chmod 600`（平台允许时）。
- `show-config` / 报告证据路径做密钥脱敏。
- 用户输入一律当数据，不经 shell。
- Mock 与 `--demo` 默认不访问网络。
- 安装脚本使用独立 venv，避免污染系统 Python（PEP 668 / Homebrew）。

## 7. 测试与质量门禁

```bash
python -m unittest discover -s tests -v
python -m compileall -q llm_api_proxy_check tests
ruff check llm_api_proxy_check tests   # CI
mypy llm_api_proxy_check tests         # CI
python -m llm_api_proxy_check check --demo --format json
```

测试覆盖：安全 CLI、JSD/Needle 边界、SSE 多行与 tool 重组、报告脱敏、配置读写、`check` 读配置与 `--demo`、本地 HTTP mock 端到端。

## 8. 小白使用路径（与实现对应）

```bash
# 安装（独立 venv + 启动器）
curl -fsSL https://raw.githubusercontent.com/LegendNero/llm-api-proxy-check/main/install.sh | bash

llm-api-proxy-check setup    # wizard.py → config.py
llm-api-proxy-check check    # 指纹 + SSE + 工具
llm-api-proxy-check check --demo   # 无需 Key
```

## 9. 验收标准

- 上述 unittest / compileall 通过。
- `check --demo` 产出高风险示例且输出中无真实密钥形态泄漏。
- 无端点时 `check` 行为与 demo 一致；半截参数返回退出码 2 并提示 `setup`。
- 有本机配置时 `check` 发起真实检测链路（指纹 ± 流式/工具）。
- GitHub Action 在无真实凭证下可完成测试与 Mock 报告 artifact。
