"""Configuration options"""
import json
from os import stat_result
from pathlib import Path

import explorer.exp as exp
from explorer import __APP_PREF__, DIR_ERROR, JSON_ERROR, SUCCESS

CONFIG_DIR: Path = Path.home() / ".config" / __APP_PREF__
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


def load_config() -> dict:
    """Loads the config file from disk. If this fails, returns the default configuration."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                return {**DEFAULT_CONFIG, **data}
            except json.JSONDecodeError:
                pass
        return DEFAULT_CONFIG.copy()
    except OSError:
        return DEFAULT_CONFIG.copy()

def save_config(cfg: dict) -> int:
    """Saves the config file to disk."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return DIR_ERROR
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=4))
    except OSError:
        return JSON_ERROR

    return SUCCESS

def theme(cfg: dict) -> dict:
    """Returns the current theme/styling"""
    return THEMES.get(cfg.get("color_theme", "default"), THEMES["default"])

def sort_entries(entries: list[Path], cfg: dict) -> list[Path]:
    key: str = cfg.get("sort_by", "name")
    rev: bool = cfg.get("sort_reverse", False)

    def sort_key(path: Path):
        """A custom key function to determine the sorting order of builtins.sorted()"""
        try:
            stats: stat_result = path.stat(follow_symlinks=False)
        except OSError:
            return "", 0, 0

        if key == "size":
            return 0 if path.is_dir() else 1, stats.st_size
        if key == "date":
            return 0 if path.is_dir() else 1, stats.st_mtime
        if key == "type":
            return 0 if path.is_dir() else 1, path.suffix.lower(), path.name.lower()

        return 0 if path.is_dir() else 1, path.name.lower()

    return sorted(entries, key=sort_key, reverse=rev)

def gather_entries(path: Path, cfg: dict) -> list[Path]:
    """Returns a sorted list of files and directories from the provided directory."""
    show_hidden: bool = cfg.get("show_hidden", False)
    try:
        entries: list[Path] = list(path.iterdir())
    except PermissionError:
        exp.app_console.print(f"[bold red]Permission denied:[/] {path}")
        return []

    if not show_hidden:
        entries = [entry for entry in entries if not entry.name.startswith(".")]
    return sort_entries(entries, cfg)
