from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ENV_CONFIG = "LLM_API_PROXY_CHECK_CONFIG"
CONFIG_DIR_NAME = "llm-api-proxy-check"
CONFIG_FILE_NAME = "config.json"


@dataclass(frozen=True)
class UserConfig:
    base_url: str
    api_key: str
    model: str = "gpt-4o-mini"
    ref_base_url: str | None = None
    ref_api_key: str | None = None
    ref_model: str | None = None
    timeout: float = 30.0

    def masked(self) -> dict[str, Any]:
        data = asdict(self)
        if data.get("api_key"):
            data["api_key"] = _mask_secret(str(data["api_key"]))
        if data.get("ref_api_key"):
            data["ref_api_key"] = _mask_secret(str(data["ref_api_key"]))
        return data


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}…{value[-4:]}"


def default_config_path() -> Path:
    override = os.environ.get(ENV_CONFIG)
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / CONFIG_DIR_NAME / CONFIG_FILE_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def load_config(path: Path | None = None) -> UserConfig | None:
    config_path = path or default_config_path()
    if not config_path.is_file():
        return None
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(raw, dict):
        return None
    base_url = raw.get("base_url")
    api_key = raw.get("api_key")
    model = raw.get("model") or "gpt-4o-mini"
    if not isinstance(base_url, str) or not base_url.strip():
        return None
    if not isinstance(api_key, str) or not api_key.strip():
        return None
    if not isinstance(model, str) or not model.strip():
        return None
    timeout_raw = raw.get("timeout", 30.0)
    try:
        timeout = float(timeout_raw)
    except (TypeError, ValueError):
        timeout = 30.0
    ref_base = raw.get("ref_base_url")
    ref_key = raw.get("ref_api_key")
    ref_model = raw.get("ref_model")
    return UserConfig(
        base_url=base_url.strip(),
        api_key=api_key.strip(),
        model=model.strip(),
        ref_base_url=ref_base.strip() if isinstance(ref_base, str) and ref_base.strip() else None,
        ref_api_key=ref_key.strip() if isinstance(ref_key, str) and ref_key.strip() else None,
        ref_model=ref_model.strip() if isinstance(ref_model, str) and ref_model.strip() else None,
        timeout=timeout if timeout > 0 else 30.0,
    )


def save_config(config: UserConfig, path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "base_url": config.base_url,
        "api_key": config.api_key,
        "model": config.model,
        "timeout": config.timeout,
    }
    if config.ref_base_url:
        payload["ref_base_url"] = config.ref_base_url
    if config.ref_api_key:
        payload["ref_api_key"] = config.ref_api_key
    if config.ref_model:
        payload["ref_model"] = config.ref_model
    tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, config_path)
    try:
        os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return config_path
