import mimetypes
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.filesize import decimal
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import explorer.config as config


def list_dir(console: Console, path: Path, cfg: dict, long_listing: bool = False) -> None:
    """List directory contents"""
    theme: dict = config.theme(cfg)
    entries: list[Path] = config.gather_entries(path, cfg)

    header = Text()
    header.append("[D] ")
    header.append(str(path.resolve()), style=theme["header"])
    header.append(f"  ({len(entries)} items)", style=theme["date"])
    console.print(Panel(header, box=box.ROUNDED, border_style=theme["accent"]))

    if not entries:
        console.print(f"  [{theme["date"]}](empty)[/]")
        return

    if long_listing:
        _long_listing(console, entries, cfg)
    else:
        _short_listing(console, entries, cfg)


def _short_listing(console: Console, entries: list[Path], cfg: dict) -> None:
    theme: dict = config.theme(cfg)
    renderables: list = []
    for e in entries:
        icon, style = _style_icon_for(e, theme)
        renderables.append(Text(f"{icon} {e.name}", style=style))

    console.print(Columns(renderables, equal=False, expand=False, padding=(0, 2)))
    console.print()


def _long_listing(console: Console, entries: list[Path], cfg: dict) -> None:
    theme: dict = config.theme(cfg)
    dt_format: str = cfg.get("date_format", "%Y-%m-%d %H:%M")

    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style=theme["header"], pad_edge=False)
    table.add_column("", width=2)
    table.add_column("Name", style=theme["file"])
    table.add_column("Size", style=theme["size"], justify="right")
    table.add_column("Modified", style=theme["date"])
    table.add_column("Type", style=theme["date"])
    table.add_column("Permissions", style="dim white")

    for e in entries:
        try:
            estat = e.stat(follow_symlinks=False)
        except OSError:
            continue

        icon, style = _style_icon_for(e, theme)

        size_str = "" if e.is_dir() else decimal(estat.st_size)
        m_time = datetime.fromtimestamp(estat.st_mtime).strftime(dt_format)
        permissions = stat.filemode(estat.st_mode)
        file_type = _file_type_label(e)

        table.add_row(icon, Text(e.name, style=style), size_str, m_time, file_type, permissions)

    console.print(table)


def _style_icon_for(path: Path, theme: dict) -> tuple[str, Any]:
    if path.is_symlink():
        style, icon = theme["symlink"], config.ICONS["symlink"]
    elif path.is_dir():
        style, icon = theme["dir"], config.ICONS["dir"]
    elif os.access(path, os.X_OK):
        style, icon = theme["exec"], config.ICONS["exec"]
    else:
        style, icon = theme["file"], config.ICONS["file"]
    return icon, style


def _file_type_label(path: Path) -> str:
    """Returns the file type."""
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "directory"
    mime, _ = mimetypes.guess_type(str(path))
    if mime:
        return mime
    if os.access(path, os.X_OK):
        return "executable"
    return path.suffix.lstrip(".").upper() or "file"
