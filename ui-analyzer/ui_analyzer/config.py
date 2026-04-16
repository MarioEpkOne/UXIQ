"""config.py — Read/write ~/.uxiq/config.json for persistent user preferences."""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_ALIASES: dict[str, str] = {
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-6",
    "haiku":  "claude-haiku-4-5-20251001",
}
DEFAULT_MODEL_ALIAS = "sonnet"

_CONFIG_DIR = Path.home() / ".uxiq"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def _config_file() -> Path:
    """Return the config file path. Allows tests to monkeypatch _CONFIG_FILE."""
    return _CONFIG_FILE


def get_model(config_file: Path | None = None) -> str:
    """Return the full model ID from config, or the default.

    Falls back to DEFAULT_MODEL_ALIAS when:
    - config file is absent
    - config file is corrupt (invalid JSON) — warns to stderr
    - stored alias is not in MODEL_ALIASES — warns to stderr
    """
    path = config_file if config_file is not None else _CONFIG_FILE
    if not path.exists():
        return MODEL_ALIASES[DEFAULT_MODEL_ALIAS]
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        warnings.warn(
            f"uxiq config is corrupt or unreadable ({exc}); using default model.",
            stacklevel=2,
        )
        return MODEL_ALIASES[DEFAULT_MODEL_ALIAS]

    alias = data.get("model", DEFAULT_MODEL_ALIAS)
    if alias not in MODEL_ALIASES:
        warnings.warn(
            f"Unknown model alias {alias!r} in uxiq config; using default model.",
            stacklevel=2,
        )
        return MODEL_ALIASES[DEFAULT_MODEL_ALIAS]
    return MODEL_ALIASES[alias]


def set_model(alias: str, config_file: Path | None = None) -> None:
    """Write the alias to config. Creates ~/.uxiq/ if needed.

    Args:
        alias: Must be a key in MODEL_ALIASES.
        config_file: Override path for testing. Defaults to ~/.uxiq/config.json.

    Raises:
        ValueError: if alias is not in MODEL_ALIASES.
    """
    if alias not in MODEL_ALIASES:
        valid = ", ".join(sorted(MODEL_ALIASES))
        raise ValueError(f'Unknown model: "{alias}". Valid: {valid}.')

    path = config_file if config_file is not None else _CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    # Merge — preserve any unknown future keys
    existing: dict = {}
    if path.exists():
        try:
            with path.open(encoding="utf-8") as fh:
                existing = json.load(fh)
        except (json.JSONDecodeError, OSError):
            existing = {}

    existing["model"] = alias
    with path.open("w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2)
        fh.write("\n")
