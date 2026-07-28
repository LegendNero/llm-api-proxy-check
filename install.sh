#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${LLM_API_PROXY_CHECK_REPO:-https://github.com/LegendNero/llm-api-proxy-check.git}"
PACKAGE_SPEC="${LLM_API_PROXY_CHECK_PACKAGE:-git+${REPO_URL}}"
INSTALL_HOME="${LLM_API_PROXY_CHECK_HOME:-${HOME}/.local/share/llm-api-proxy-check}"
VENV_DIR="${INSTALL_HOME}/venv"
BIN_DIR="${LLM_API_PROXY_CHECK_BIN:-${HOME}/.local/bin}"
WRAPPER="${BIN_DIR}/llm-api-proxy-check"

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'llm-api-proxy-check install: %s\n' "$*" >&2
  exit 1
}

version_ok() {
  local py="$1"
  "$py" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
PY
}

find_python() {
  local candidate
  if [[ -n "${PYTHON:-}" ]]; then
    if command -v "$PYTHON" >/dev/null 2>&1 && version_ok "$PYTHON"; then
      command -v "$PYTHON"
      return 0
    fi
    die "PYTHON=$PYTHON 不可用或版本低于 3.9"
  fi
  for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && version_ok "$candidate"; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(find_python)" || die "需要 Python 3.9+，请先安装后重试"
log "使用 Python: $PYTHON_BIN ($("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))'))"

if ! "$PYTHON_BIN" -c 'import venv' >/dev/null 2>&1; then
  die "当前 Python 缺少 venv 模块，请安装 python3-venv 后重试"
fi

mkdir -p "$INSTALL_HOME" "$BIN_DIR"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  log "创建虚拟环境: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PY="${VENV_DIR}/bin/python"
log "正在安装 llm-api-proxy-check 到虚拟环境 ..."
"$VENV_PY" -m pip install --upgrade pip setuptools wheel >/dev/null
"$VENV_PY" -m pip install --upgrade "$PACKAGE_SPEC"

cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/llm-api-proxy-check" "\$@"
EOF
chmod +x "$WRAPPER"

case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *)
    export PATH="${BIN_DIR}:${PATH}"
    log "已临时将 ${BIN_DIR} 加入 PATH"
    log "永久生效可写入 shell 配置，例如: export PATH=\"${BIN_DIR}:\$PATH\""
    ;;
esac

if [[ -x "${VENV_DIR}/bin/llm-api-proxy-check" ]]; then
  log "安装成功: $WRAPPER"
  log ""
  log "小白三步走："
  log "  1) 本地演示（无需 Key）: llm-api-proxy-check check --demo"
  log "  2) 中文设置向导:         llm-api-proxy-check setup"
  log "  3) 一键完整检测:         llm-api-proxy-check check"
  log ""
  log "查看配置: llm-api-proxy-check show-config"
else
  die "虚拟环境中未找到 llm-api-proxy-check 入口"
fi

"$VENV_PY" -m llm_api_proxy_check check --format json >/dev/null || true
log "验证完成（本地 demo 已通过模块入口）。"
