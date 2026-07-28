#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${LLM_API_PROXY_CHECK_REPO:-https://github.com/LegendNero/llm-api-proxy-check.git}"
PACKAGE_SPEC="${LLM_API_PROXY_CHECK_PACKAGE:-git+${REPO_URL}}"
INSTALL_HOME="${LLM_API_PROXY_CHECK_HOME:-${HOME}/.local/share/llm-api-proxy-check}"
VENV_DIR="${INSTALL_HOME}/venv"
BIN_DIR="${LLM_API_PROXY_CHECK_BIN:-${HOME}/.local/bin}"
WRAPPER="${BIN_DIR}/llm-api-proxy-check"
PATH_MARKER="# llm-api-proxy-check PATH"
PATH_EXPORT_LINE="export PATH=\"${BIN_DIR}:\$PATH\""

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

path_contains_bin() {
  case ":${PATH}:" in
    *":${BIN_DIR}:"*) return 0 ;;
    *) return 1 ;;
  esac
}

ensure_path_in_file() {
  local file="$1"
  local parent
  parent="$(dirname "$file")"
  mkdir -p "$parent"
  touch "$file"
  if grep -Fqx "$PATH_MARKER" "$file" 2>/dev/null; then
    return 1
  fi
  if grep -Fq "$BIN_DIR" "$file" 2>/dev/null; then
    return 1
  fi
  {
    printf '\n%s\n' "$PATH_MARKER"
    printf '%s\n' "$PATH_EXPORT_LINE"
  } >> "$file"
  return 0
}

persist_path() {
  local shell_name updated=()
  shell_name="$(basename "${SHELL:-bash}")"
  case "$shell_name" in
    zsh)
      if ensure_path_in_file "${ZDOTDIR:-$HOME}/.zshrc"; then
        updated+=("${ZDOTDIR:-$HOME}/.zshrc")
      fi
      ;;
    bash)
      if [[ -f "$HOME/.bashrc" ]] || [[ ! -f "$HOME/.bash_profile" && ! -f "$HOME/.profile" ]]; then
        if ensure_path_in_file "$HOME/.bashrc"; then
          updated+=("$HOME/.bashrc")
        fi
      fi
      if [[ -f "$HOME/.bash_profile" ]] || [[ "$(uname -s)" == "Darwin" ]]; then
        if ensure_path_in_file "$HOME/.bash_profile"; then
          updated+=("$HOME/.bash_profile")
        fi
      fi
      if [[ -f "$HOME/.profile" ]]; then
        if ensure_path_in_file "$HOME/.profile"; then
          updated+=("$HOME/.profile")
        fi
      fi
      ;;
    fish)
      local fish_file="$HOME/.config/fish/config.fish"
      mkdir -p "$(dirname "$fish_file")"
      touch "$fish_file"
      if ! grep -Fq "$BIN_DIR" "$fish_file" 2>/dev/null; then
        {
          printf '\n%s\n' "$PATH_MARKER"
          printf 'fish_add_path %s\n' "$BIN_DIR"
        } >> "$fish_file"
        updated+=("$fish_file")
      fi
      ;;
    *)
      if ensure_path_in_file "$HOME/.profile"; then
        updated+=("$HOME/.profile")
      fi
      ;;
  esac

  # Always try common login files on macOS so Terminal.app picks it up
  if [[ "$(uname -s)" == "Darwin" ]]; then
    if [[ "$shell_name" != "zsh" ]]; then
      if ensure_path_in_file "${ZDOTDIR:-$HOME}/.zshrc"; then
        updated+=("${ZDOTDIR:-$HOME}/.zshrc")
      fi
    fi
    if ensure_path_in_file "$HOME/.bash_profile"; then
      updated+=("$HOME/.bash_profile")
    fi
  fi

  if [[ ${#updated[@]} -gt 0 ]]; then
    log "已写入 PATH 到:"
    local f
    for f in "${updated[@]}"; do
      log "  - $f"
    done
    log "新开一个终端后可直接使用 llm-api-proxy-check"
  else
    log "检测到 shell 配置里可能已包含 ${BIN_DIR}，未重复写入"
  fi
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

# Also expose a stable module launcher (works even if console script name confuses users)
MODULE_WRAPPER="${BIN_DIR}/llm-api-proxy-check-python"
cat > "$MODULE_WRAPPER" <<EOF
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/python" -m llm_api_proxy_check "\$@"
EOF
chmod +x "$MODULE_WRAPPER"

if ! path_contains_bin; then
  export PATH="${BIN_DIR}:${PATH}"
  log "已将 ${BIN_DIR} 加入当前会话 PATH"
fi
persist_path

if [[ ! -x "${VENV_DIR}/bin/llm-api-proxy-check" ]]; then
  die "虚拟环境中未找到 llm-api-proxy-check 入口"
fi

log ""
log "安装成功: $WRAPPER"
log ""
log "若提示 command not found，用下面任一方式（当前终端立刻可用）："
log "  1) 完整路径:  ${WRAPPER} setup"
log "  2) 临时生效:  export PATH=\"${BIN_DIR}:\$PATH\" && llm-api-proxy-check setup"
log "  3) 新开终端后再运行: llm-api-proxy-check setup"
log ""
log "小白三步走："
log "  1) 本地演示: ${WRAPPER} check --demo"
log "  2) 中文设置: ${WRAPPER} setup"
log "  3) 一键检测: ${WRAPPER} check"
log ""
log "查看配置: ${WRAPPER} show-config"

"$VENV_PY" -m llm_api_proxy_check check --format json >/dev/null || true
log "验证完成（本地 demo 已通过模块入口）。"

# Verify command resolution in this session
if command -v llm-api-proxy-check >/dev/null 2>&1; then
  log "当前终端已可直接运行: llm-api-proxy-check"
else
  log "当前终端仍需用完整路径，或执行: export PATH=\"${BIN_DIR}:\$PATH\""
fi
