# llm-api-proxy-check

[English](README.md) | [中文](README_zh.md)

Standard-library toolkit that **checks the integrity of OpenAI-compatible LLM API proxies** (relay / middleman endpoints).

Detects model-substitution signals, SSE tampering, tool-call rewriting, and usage anomalies.  
**Local demo needs no API key.**

---

## Beginner path (3 steps)

### 1) One-line install

**macOS / Linux**

```bash
curl -fsSL https://raw.githubusercontent.com/LegendNero/llm-api-proxy-check/main/install.sh | bash
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/LegendNero/llm-api-proxy-check/main/install.ps1 | iex
```

Requires Python **3.9+**. Installer uses an isolated venv and persists `~/.local/bin` on PATH (Windows: user PATH).

### If you see `command not found`

The tool is usually installed; the current shell just lacks PATH. Use either:

```bash
~/.local/bin/llm-api-proxy-check setup
# or
export PATH="$HOME/.local/bin:$PATH"
llm-api-proxy-check setup
```

### 2) Interactive setup (once)

```bash
llm-api-proxy-check setup
```

Prompts for Base URL, API key (hidden input, stored locally only), and model.  
Optional official/reference endpoint for stronger comparison. Connectivity smoke test available.

```bash
llm-api-proxy-check show-config
```

### 3) One-command check (economy by default)

```bash
llm-api-proxy-check check
```

Default **economy** mode (fewer tokens): short Needle, combined capability prompt, skip same-endpoint fingerprint waste.  
Report shows **token usage** and **per-check fix advice**. Use `check --full` for deeper (costlier) probes.
---

## Try without any key

```bash
llm-api-proxy-check check --demo
```

---

## More commands

```bash
llm-api-proxy-check check --format json
llm-api-proxy-check check --skip-stream
llm-api-proxy-check check --skip-tools
llm-api-proxy-check check --base-url https://your-proxy.example/v1 --api-key "$KEY" --model gpt-4o-mini
llm-api-proxy-check config-path
```

Or:

```bash
python -m llm_api_proxy_check setup
python -m llm_api_proxy_check check
```

### Environment variables (optional; override file config)

| Variable | Meaning |
|----------|---------|
| `LLM_API_PROXY_CHECK_BASE_URL` | Proxy base URL |
| `LLM_API_PROXY_CHECK_API_KEY` | API key |
| `LLM_API_PROXY_CHECK_MODEL` | Model name |
| `LLM_API_PROXY_CHECK_REF_BASE_URL` | Reference endpoint |
| `LLM_API_PROXY_CHECK_REF_API_KEY` | Reference key |
| `LLM_API_PROXY_CHECK_REF_MODEL` | Reference model |
| `LLM_API_PROXY_CHECK_CONFIG` | Custom config path |

Never commit API keys.

Default config path:

- macOS / Linux: `~/.config/llm-api-proxy-check/config.json`
- Windows: `%APPDATA%\llm-api-proxy-check\config.json`

---

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Not high risk |
| 1 | High risk detected |
| 2 | Argument / runtime error |

---

## Features

- Fingerprint suite (tokenizer, distribution, capability, Needle)
- SSE integrity (`[DONE]`, JSON, usage shape)
- Tool-call integrity across streamed deltas
- Chinese/English-friendly CLI with local setup wizard
- Zero runtime dependencies (Python 3.9+ stdlib)

## Design notes

Module map, config precedence, scoring weights, and acceptance checks: [IMPLEMENTATION.md](IMPLEMENTATION.md).

## License

MIT
