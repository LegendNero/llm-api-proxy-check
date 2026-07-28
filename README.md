# relay-audit

Standard-library toolkit for auditing OpenAI-compatible **relay / proxy API integrity**.

Detects common integrity risks such as model substitution signals, SSE stream tampering, tool-call rewriting, and usage accounting anomalies — without requiring a cloud account for the local mock demo.

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
python -m relay_audit demo --format markdown

# JSON report for CI
python -m relay_audit demo --format json

# run tests
python -m unittest discover -s tests -v
```

Optional install as a console script:

```bash
pip install -e .
relay-audit demo --format markdown
```

## Real endpoint (optional)

Use an OpenAI-compatible base URL and API key via environment variables / CLI flags supported by the HTTP client path (see `relay_audit/http_client.py` and `python -m relay_audit --help`). Never commit keys.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Audit passed (low risk) |
| 1 | Risk detected |
| 2 | Parameter / runtime error |

## Project layout

```
relay_audit/     core library + CLI
tests/           unittest suite
.github/         CI workflow
IMPLEMENTATION.md  design notes for the MVP
```

## License

MIT
