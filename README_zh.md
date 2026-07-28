# llm-api-proxy-check

[English](README.md) | [中文](README_zh.md)

基于 Python 标准库的工具，用来**检测 OpenAI 兼容 LLM API 代理（中转站）是否完整、有没有被动手脚**。

可发现：模型被替换的迹象、SSE 流被篡改、工具调用被改写、用量异常等。  
**本地演示不需要任何 API Key。**

---

## 小白三步走（推荐）

### 第 1 步：一键安装

**macOS / Linux**

```bash
curl -fsSL https://raw.githubusercontent.com/LegendNero/llm-api-proxy-check/main/install.sh | bash
```

**Windows（PowerShell）**

```powershell
irm https://raw.githubusercontent.com/LegendNero/llm-api-proxy-check/main/install.ps1 | iex
```

要求：电脑上已有 Python **3.9+**。  
安装脚本会自动建独立环境，并把 `~/.local/bin` 写入 shell 配置（Windows 写入用户 PATH）。

### 若提示 `command not found`

安装其实多半已经成功，只是**当前终端还没加载 PATH**。任选一种立刻可用：

```bash
# 方式 A：完整路径（最省事）
~/.local/bin/llm-api-proxy-check setup

# 方式 B：当前终端临时生效
export PATH="$HOME/.local/bin:$PATH"
llm-api-proxy-check setup

# 方式 C：重新安装一次（新版安装脚本会自动写 PATH）
curl -fsSL https://raw.githubusercontent.com/LegendNero/llm-api-proxy-check/main/install.sh | bash
# 然后新开一个终端，再运行 llm-api-proxy-check setup
```

### 第 2 步：中文向导设置（只需一次）

```bash
llm-api-proxy-check setup
```

按提示填 3 项即可：

1. 代理地址（Base URL），例如 `https://你的中转域名/v1`
2. API Key（输入时不显示，只保存在本机）
3. 模型名（可直接回车用默认 `gpt-4o-mini`）

可选再填一个「官方/可信」参考端点，对比会更准。  
设置结束后可自动做一次连通性测试。

查看已保存配置（密钥已脱敏）：

```bash
llm-api-proxy-check show-config
```

### 第 3 步：一键检测（默认省 token）

```bash
llm-api-proxy-check check
```

默认 **economy（省 token）** 模式，自动读取本机配置，跑：

- 能力题（合并为一问）、短 Needle
- 流式 SSE + 工具完整性
- **不**对同端点空跑对照指纹；未配置参考端点时跳过耗 token 的分词/分布对照

结束后报告会显示：

- **API 用量**：本次大约消耗多少 tokens、几次请求
- **发现的问题怎么处理**：按失败/未知检查项给出可执行建议

需要更全、更费额度时：

```bash
llm-api-proxy-check check --full
```

---

## 还不会配？先本地演示

```bash
llm-api-proxy-check check --demo
```

不连网、不需要 Key，直接看一份「高风险」示例报告，了解工具长什么样。

---

## 其他常用命令

```bash
# 强制演示
llm-api-proxy-check check --demo

# 输出 JSON（给 CI / 脚本用）
llm-api-proxy-check check --format json

# 只跑指纹，跳过流式和工具（省额度、更快）
llm-api-proxy-check check --skip-stream

# 流式测 SSE，但不测工具调用
llm-api-proxy-check check --skip-tools

# 临时指定端点（不写配置文件）
llm-api-proxy-check check --base-url https://your-proxy.example/v1 --api-key "$KEY" --model gpt-4o-mini

# 打印配置文件路径
llm-api-proxy-check config-path
```

未装上命令时也可以：

```bash
python -m llm_api_proxy_check setup
python -m llm_api_proxy_check check
```

### 环境变量（可选，优先于配置文件）

| 变量 | 含义 |
|------|------|
| `LLM_API_PROXY_CHECK_BASE_URL` | 代理 Base URL |
| `LLM_API_PROXY_CHECK_API_KEY` | API Key |
| `LLM_API_PROXY_CHECK_MODEL` | 模型名 |
| `LLM_API_PROXY_CHECK_REF_BASE_URL` | 参考端点 |
| `LLM_API_PROXY_CHECK_REF_API_KEY` | 参考 Key |
| `LLM_API_PROXY_CHECK_REF_MODEL` | 参考模型 |
| `LLM_API_PROXY_CHECK_CONFIG` | 自定义配置文件路径 |

**切勿把 API Key 提交到 Git 仓库。**

配置默认位置：

- macOS / Linux：`~/.config/llm-api-proxy-check/config.json`
- Windows：`%APPDATA%\llm-api-proxy-check\config.json`

---

## 结果怎么看

| 健康分 | 风险 | 建议 |
|--------|------|------|
| ≥ 85 | low | 目前看起来正常 |
| 60–84 | medium | 有异常信号，建议对照官方端点再测 |
| < 60 | high | 高风险，优先换源或停用该代理 |

退出码：

| 码 | 含义 |
|----|------|
| 0 | 非高风险 |
| 1 | 检测到高风险 |
| 2 | 参数或运行错误（例如只填了 URL 没填 Key） |

---

## 功能一览

- **省 token 默认模式** + `--full` 完整模式
- **指纹套件**：tokenizer、输出分布、能力题、Needle
- **SSE 完整性**：事件解析、`[DONE]`、JSON、usage 形态
- **工具调用完整性**：跨 delta 重组，检测 name 被改写
- **用量统计与修复建议**：报告内展示 tokens 与按项处理指引
- **中文 setup 向导**：本机保存配置，密钥脱敏展示
- **零运行时依赖**：只要 Python 3.9+ 标准库

---

## 手动安装（可选）

Homebrew / PEP 668 环境建议用 venv：

```bash
python3 -m venv ~/.venvs/llm-api-proxy-check
~/.venvs/llm-api-proxy-check/bin/pip install "git+https://github.com/LegendNero/llm-api-proxy-check.git"
```

---

## 目录结构

```
llm_api_proxy_check/   核心库 + CLI
install.sh             macOS/Linux 一键安装
install.ps1            Windows 一键安装
tests/                 单元测试
.github/               CI
IMPLEMENTATION.md      与代码同步的实施说明（模块/数据流/验收）
```

## 开发说明

更细的模块边界、配置优先级、评分权重与验收命令见 [IMPLEMENTATION.md](IMPLEMENTATION.md)。

## 许可证

MIT
