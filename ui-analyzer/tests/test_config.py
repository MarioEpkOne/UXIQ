"""Tests for config.py — get_model() and set_model()."""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from ui_analyzer.config import (
    DEFAULT_MODEL_ALIAS,
    MODEL_ALIASES,
    get_model,
    set_model,
)


# ---------------------------------------------------------------------------
# get_model() — config absent
# ---------------------------------------------------------------------------

def test_get_model_returns_default_when_config_absent(tmp_path):
    """get_model() with nonexistent config file → returns default full model ID."""
    missing = tmp_path / "nonexistent.json"
    result = get_model(config_file=missing)
    assert result == MODEL_ALIASES[DEFAULT_MODEL_ALIAS]


# ---------------------------------------------------------------------------
# get_model() — alias resolved after set_model()
# ---------------------------------------------------------------------------

def test_get_model_resolves_alias_after_set_model(tmp_path):
    """set_model('opus') then get_model() → returns claude-opus-4-6."""
    cfg = tmp_path / "config.json"
    set_model("opus", config_file=cfg)
    result = get_model(config_file=cfg)
    assert result == MODEL_ALIASES["opus"]


# ---------------------------------------------------------------------------
# get_model() — falls back on corrupt JSON, warns to stderr
# ---------------------------------------------------------------------------

def test_get_model_falls_back_on_corrupt_json(tmp_path):
    """get_model() with corrupt JSON → returns default, issues UserWarning."""
    cfg = tmp_path / "config.json"
    cfg.write_text("{ not valid json !!!", encoding="utf-8")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = get_model(config_file=cfg)
    assert result == MODEL_ALIASES[DEFAULT_MODEL_ALIAS]
    assert any("corrupt" in str(w.message).lower() for w in caught)


# ---------------------------------------------------------------------------
# set_model() — creates directory if missing
# ---------------------------------------------------------------------------

def test_set_model_creates_directory_if_missing(tmp_path):
    """set_model() with a path inside a nonexistent subdirectory → creates the directory."""
    cfg = tmp_path / "nested" / "deep" / "config.json"
    set_model("haiku", config_file=cfg)
    assert cfg.exists()
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["model"] == "haiku"


# ---------------------------------------------------------------------------
# set_model() — raises ValueError on unknown alias
# ---------------------------------------------------------------------------

def test_set_model_raises_value_error_on_unknown_alias(tmp_path):
    """set_model() with unknown alias → raises ValueError."""
    cfg = tmp_path / "config.json"
    with pytest.raises(ValueError, match="Unknown model"):
        set_model("gpt-4", config_file=cfg)


# ---------------------------------------------------------------------------
# set_model() — preserves other config keys on write
# ---------------------------------------------------------------------------

def test_set_model_preserves_other_config_keys(tmp_path):
    """set_model() merges model key without clobbering other keys."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"theme": "dark", "verbose": True}), encoding="utf-8")
    set_model("sonnet", config_file=cfg)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["model"] == "sonnet"
    assert data["theme"] == "dark"
    assert data["verbose"] is True
