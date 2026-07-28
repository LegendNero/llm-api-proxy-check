# llm-api-proxy-check

[English](README.md) | [中文](README_zh.md)

Standard-library toolkit that **checks the integrity of OpenAI-compatible LLM API proxies** (relay / middleman endpoints).

Detects common risks such as model-substitution signals, SSE stream tampering, tool-call rewriting, and usage accounting anomalies — no cloud account required for the local mock demo.

Search keywords: **LLM**, **API**, **proxy**, OpenAI-compatible, integrity, SSE, tool calls, audit, fingerprint.

## One-line install

**macOS / Linux**

```bash
curl -fsSL https://raw.githubusercontent.com/LegendNero/llm-api-proxy-check/main/install.sh | bash
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/LegendNero/llm-api-proxy-check/main/install.ps1 | iex
```

Requirements: Python **3.9+**. The script creates an isolated venv under `~/.local/share/llm-api-proxy-check`, installs from this GitHub repo, and places a launcher in `~/.local/bin`.

Manual install (venv recommended on Homebrew / PEP 668 systems):

```bash
python3 -m venv ~/.venvs/llm-api-proxy-check
~/.venvs/llm-api-proxy-check/bin/pip install "git+https://github.com/LegendNero/llm-api-proxy-check.git"
```

## Everyday commands

```bash
# Local demo (no API key) — default entry after install
llm-api-proxy-check check

# Real proxy check
llm-api-proxy-check check --base-url https://your-proxy.example/v1 --api-key "$KEY" --model gpt-4o-mini

# JSON for CI
llm-api-proxy-check check --format json
```

Or without installing the console script:

```bash
python -m llm_api_proxy_check check
```

Environment variables (optional):

| Variable | Meaning |
|----------|---------|
| `LLM_API_PROXY_CHECK_BASE_URL` | Proxy base URL |
| `LLM_API_PROXY_CHECK_API_KEY` | API key |
| `LLM_API_PROXY_CHECK_MODEL` | Model name (default `gpt-4o-mini`) |
| `LLM_API_PROXY_CHECK_REF_BASE_URL` | Optional reference endpoint |
| `LLM_API_PROXY_CHECK_REF_API_KEY` | Optional reference API key |
| `LLM_API_PROXY_CHECK_REF_MODEL` | Optional reference model |

Never commit API keys.

## Features

- **Fingerprint suite**: tokenizer counts, output distribution distance, capability checks, long-context Needle probe
- **SSE integrity**: event parsing, `[DONE]` control frames, JSON validity, usage shape checks
- **Tool-call integrity**: reassembly and rewrite detection across streamed deltas
- **Risk scoring**: weighted 0–100 score with `pass` / `fail` / `unknown` coverage
- **Safe CLI adapter**: `subprocess` with `shell=False`, timeouts, and output limits
- **CI-ready**: GitHub Action runs tests, ruff, mypy, and a mock demo report
- **Zero runtime deps**: Python 3.9+ standard library only

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Audit passed (low/medium risk treated as non-failure for exit; high → 1) |
| 1 | High risk detected |
| 2 | Parameter / runtime error |

## Project layout

```
llm_api_proxy_check/   core library + CLI
install.sh             one-line install (macOS/Linux)
install.ps1            one-line install (Windows)
tests/                 unittest suite
.github/               CI workflow
IMPLEMENTATION.md      design notes for the MVP
```

## License

MIT
