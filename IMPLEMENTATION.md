# 中转 API 完整性监控 MVP 实施文档

## 1. 目标与范围

本阶段把已批准的五步方案落为一个可本地运行、可测试、可接入 CI 的 Python 标准库 MVP：

1. 安全 CLI 适配层：以参数数组调用外部命令，禁止 shell 拼接，限制超时、输出大小和环境变量泄漏。
2. 指纹与 Needle 探针：通过 tokenizer 计数、单 token 分布、客观能力题和长上下文 Needle 测试形成可解释信号。
3. SSE 与工具完整性：解析 SSE 事件，检查事件顺序、JSON 完整性、usage 偏差和工具调用是否被重写。
4. 基线评分报告：把探针结果归一化为风险评分，输出 JSON 与 Markdown 报告。
5. GitHub Action 与 Mock 演示：无需真实 API Key 即可运行完整演示，CI 执行测试、lint 和类型检查。

本阶段不实现真实模型厂商适配、PII 脱敏、网关转发、企业合规审计和在线数据库；这些属于后续扩展。所有网络调用通过可注入的客户端接口完成，避免把凭证写入日志或测试数据。

## 2. 技术约束

- Python 3.11+。
- 运行时仅使用 Python 标准库。
- 核心逻辑保持纯函数或显式依赖注入，Mock 与真实 API 客户端可替换。
- CLI 外部调用必须使用 `subprocess.run([...], shell=False)` 语义，并设置超时、输出上限及最小化环境。
- 报告不得包含 API Key、Authorization header 或完整敏感请求体。
- CLI 退出码：0 表示通过，1 表示检测到风险，2 表示参数或运行错误。

## 3. 模块设计

### 3.1 安全 CLI 适配层

`llm_api_proxy_check/cli.py` 提供 `run_command` 与 `main`。`run_command` 接收不可变参数数组，拒绝空命令、shell 元字符和超出长度的参数；仅继承必要的 locale/path 环境，捕获 stdout/stderr 并限制字节数。适配层不负责解析业务结果。

### 3.2 指纹与 Needle 探针

`llm_api_proxy_check/probes.py` 定义 `ProbeClient` 协议及四类探针：

- tokenizer：对固定字符串集合比较 token 数量向量。
- distribution：比较离散概率分布并计算 Jensen-Shannon 散度。
- capability：检查算术、反转等客观题答案。
- needle：在固定长文本中寻找唯一 needle，分别记录短上下文与长上下文结果。

`run_fingerprint_suite` 返回结构化 `ProbeResult`，每个信号包括名称、状态、数值、阈值和安全的证据摘要。

### 3.3 SSE 与工具完整性

`integrity.py` 提供 SSE 事件解析器和 `audit_stream`：

- 按空行分隔事件，支持 `data:` 多行拼接。
- 校验 JSON 可解析性、事件终止标记和 usage 数值。
- 收集 tool call 的 id、name、arguments，检查同一调用是否发生名称或参数重写。
- 对 token 计数采用可注入计数器；缺省使用空白分词近似，仅用于 Mock 和基线，不宣称等同厂商 tokenizer。

### 3.4 基线评分与报告

`llm_api_proxy_check/report.py` 将探针与完整性结果映射为 0-100 健康分和风险等级：

- 每个失败信号扣分，严重的流完整性、工具重写和 token 计费偏差权重更高。
- 缺失信号标记为 `unknown`，不伪装成通过。
- JSON 是机器接口；Markdown 是人读报告，证据只保留摘要和数值，不输出凭证。

### 3.5 Mock 与 CLI

`llm_api_proxy_check/mock.py` 提供稳定的本地 Mock 客户端和带风险的 Mock SSE 流。`python -m llm_api_proxy_check demo --format markdown` 运行全套检查；`python -m llm_api_proxy_check audit --command ...` 展示安全 CLI 适配层。真实 API 接入可在不改变探针接口的前提下增加客户端。

## 4. 数据流

`ProbeClient` → `ProbeResult[]`；Mock/真实流 → `StreamAuditResult`；两者 → `build_report` → JSON/Markdown 渲染器 → CLI 或 CI artifact。

CI 只依赖退出码和 JSON 摘要，不解析 Markdown。报告中明确区分 `pass`、`fail`、`unknown`，便于后续加入基线历史和漂移比较。

## 5. 错误处理与安全边界

- 外部命令超时、非零退出和输出截断均转为显式错误结果。
- 探针客户端异常不会吞掉；单项探针记录 `unknown` 并继续执行其余探针。
- 所有用户输入按数据处理，不通过 shell 解释。
- 输出脱敏只允许固定字段和摘要，禁止打印完整请求头、环境变量和原始 token。
- Mock 默认不发网络请求。

## 6. 测试与质量门禁

测试覆盖：命令注入防护、超时、JSD 边界、Needle 长上下文、SSE 多行 data、usage 偏差、工具调用重写、报告扣分和 CLI demo。质量门禁使用标准库 `unittest`，并以 `python -m compileall` 作为类型/语法级检查；GitHub Action 同时运行测试、编译检查和仓库内置的轻量 lint 脚本。

## 7. 交付验收标准

- `python -m unittest discover -s tests -v` 通过。
- `python -m compileall -q llm_api_proxy_check tests` 通过。
- `python -m llm_api_proxy_check demo --format json` 返回风险结果且不泄漏秘密。
- 安全 CLI 不允许 shell 注入，并能报告超时与非零退出。
- GitHub Action 文件可在无真实凭证环境中执行 Mock 演示。
