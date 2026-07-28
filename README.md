# llm-api-proxy-check

[English](README.md) | [中文](README_zh.md)

Standard-library toolkit that **checks the integrity of OpenAI-compatible LLM API proxies** (relay / middleman endpoints).

Detects common risks such as model-substitution signals, SSE stream tampering, tool-call rewriting, and usage accounting anomalies — no cloud account required for the local mock demo.

Search keywords: **LLM**, **API**, **proxy**, OpenAI-compatible, integrity, SSE, tool calls, audit, fingerprint.

## Features

- **Fingerprint suite**: tokenizer counts, output distribution distance, capability checks, long-context Needle probe
- **SSE integrity**: event parsing, `[DONE]` control frames, JSON validity, usage shape checks
- **Tool-call integrity**: reassembly and rewrite detection across streamed deltas
- **Risk scoring**: weighted 0–100 score with `pass` / `fail` / `unknown` coverage
- **Safe CLI adapter**: `subprocess` with `shell=False`, timeouts, and output limits
- **CI-ready**: GitHub Action runs tests, ruff, mypy, and a mock demo report
- **Zero runtime deps**: Python 3.9+ standard library only

## Quick start

```bash
# mock demo (no API key)
python -m llm_api_proxy_check demo --format markdown

# JSON report for CI
python -m llm_api_proxy_check demo --format json

# run tests
python -m unittest discover -s tests -v
```

Optional install as a console script:

```bash
pip install -e .
llm-api-proxy-check demo --format markdown
```

## Real endpoint (optional)

Use an OpenAI-compatible base URL and API key via the HTTP client path (`llm_api_proxy_check/http_client.py` and `python -m llm_api_proxy_check --help`). Never commit keys.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Audit passed (low risk) |
| 1 | Risk detected |
| 2 | Parameter / runtime error |

## Project layout

```
llm_api_proxy_check/   core library + CLI
tests/                 unittest suite
.github/               CI workflow
IMPLEMENTATION.md      design notes for the MVP
```

## License

MIT
