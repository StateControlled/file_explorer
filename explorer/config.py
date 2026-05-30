"""Configuration options"""
import json
from pathlib import Path

import typer

from explorer import __app_name__

CONFIG_DIR: Path = Path(typer.get_app_dir(__app_name__))
CONFIG_FILE: Path = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "show_hidden": False,
    "sort_by": "name",  # name | size | date | type
    "sort_reverse": False,
    "max_history": 20,
    "color_theme": "default",
    "date_format": "%Y-%m-%d %H:%M"
}

THEMES = {
    "default": {
        "dir"       : "cyan",
        "file"      : "white",
        "symlink"   : "magenta",
        "exec"      : "green",
        "size"      : "yellow",
        "date"      : "dim white",
        "header"    : "bold blue",
        "accent"    : "bold cyan",
        "warning"   : "bold yellow",
        "error"     : "bold red",
        "success"   : "bold green"
    }
}

ICONS = {
    "dir"       : "[D]",
    "file"      : "[f]",
    "symlink"   : "[l]",
    "exec"      : "[e]"
}


############################################################################


def get_save_path() -> Path:
    return CONFIG_FILE


def init():
    """Init config."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        CONFIG_FILE.touch()
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=4))


def load_config() -> dict:
    """Loads the config file from disk. If this fails, returns the default configuration."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
            return {**DEFAULT_CONFIG, **data}

        return DEFAULT_CONFIG.copy()
    except OSError:
        return DEFAULT_CONFIG.copy()

def save_config(cfg: dict) -> None:
    """Saves the config file to disk."""

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        CONFIG_FILE.touch()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=4))


def theme(cfg: dict) -> dict:
    """Returns the current theme/styling"""
    return THEMES.get(cfg.get("color_theme", "default"), THEMES["default"])

