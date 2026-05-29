from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.filesize import decimal
from rich.panel import Panel
from rich.syntax import Syntax

import explorer.config as config
import explorer.list_dir as list_dir
from explorer import __APP_PREF__, __app_name__, __version__, __author__, __doc__, __last_update__

MAX_VIEW_SIZE = 1024 * 1024
"""Files larger than this will be truncated in console view"""
MAX_VIEW_LINES = 350
"""Maximum number of lines of a text file that will be rendered to console"""

app = typer.Typer(name=__APP_PREF__,
                  help="File Explore and Search",
                  no_args_is_help=True,
                  invoke_without_command=True)

app_console = Console()


def _version(value: bool) -> None:
    if value:
        typer.echo(f"{__app_name__} v{__version__}")
        raise typer.Exit()


def _about(value: bool) -> None:
    if value:
        typer.echo(f"{__app_name__} v{__version__}, Last Updated: {__last_update__}")
        typer.echo(f"{__doc__}")
        typer.echo(f"By {__author__}")
        raise typer.Exit()


# def main(context: typer.Context):
@app.callback(invoke_without_command=True)
def main(context: typer.Context, version: Optional[bool] = typer.Option(
    None,
    "--version",
    "-v",
    help="Show this application's current version and exit.",
    callback=_version,
    is_eager=True),
    about: Optional[bool] = typer.Option(
    None,
    "--about",
    "-a",
    help="Show basic information about this application.",
    callback=_about,
    is_eager=True)) -> None:
    # F:\Programming\python\file_explorer> python -m explorer
    # A command must be entered to trigger main()
    if context.invoked_subcommand is not None:
        cfg = config.load_config()
        list_dir.list_dir(app_console, Path.cwd(), cfg)


@app.command("ls")
def list_directory_contents(path: Optional[str] = typer.Argument(None, help="List information about the files (the current directory by default"),
                            hidden: bool = typer.Option(False, "--hidden", "-h", help="Show hidden files and directories. Default=False"),
                            sort: str = typer.Option("", "--sort", "-s", help="Sort by [name|size|date|type]. Default='name'"),
                            reverse: bool = typer.Option(False, "--reverse", "-r", help="Reverse the sort order. Default=False"),
                            long: bool = typer.Option(False, "--long", "-l", help="List additional details about files. Default=False")) -> None:
    """List directory contents"""
    cfg = config.load_config()
    if hidden:
        cfg["show_hidden"] = True
    if sort:
        cfg["sort_by"] = sort
    if reverse:
        cfg["sort_reverse"] = True

    # TODO check this logic
    target = Path(path) if path else Path.cwd()
    if not target.exists():
        app_console.print(f"[bold red]Path not found:[/] {target}")
        raise typer.Exit(1)
    if not target.is_dir():
        app_console.print(f"[bold red]The path {target} is not a directory.")
        raise typer.Exit(1)

    list_dir.list_dir(app_console, target, cfg, long_listing=long)

@app.command("open")
def open_text_file(path: str = typer.Argument(..., help="The file to be opened"),
                   lines: int = typer.Option(0, "--num_lines", "-n")) -> None:
    """View a text file in the console"""
    target = Path(path).expanduser().resolve()
    if not target.exists():
        app_console.print(f"[bold red]Path not found:[/] {target}")
        raise typer.Exit(1)
    if not target.is_dir():
        app_console.print(f"[bold red]The path {target} is not a directory.")
        raise typer.Exit(1)

    cfg = config.load_config()
    theme = config.theme(cfg)

    size = target.stat().st_size
    if size > MAX_VIEW_SIZE:
        app_console.print(f"[{theme["warning"]}]! File is too large: ({decimal(size)} bytes). Showing first {MAX_VIEW_LINES} lines.[/]")
        lines = lines or MAX_VIEW_LINES

    try:
        text: str = target.read_text(errors="replace")
    except Exception as e:
        app_console.print(f"[bold red]There was an error while reading the file:[/]{e}")
        raise typer.Exit(1)

    if lines:
        text = "\n".join(text.splitlines()[:lines])

    suffix = target.suffix.lstrip(".")
    if suffix:
        syntax = Syntax(text, suffix or "text", line_numbers=True, theme="monokai", word_wrap=True)
    else:
        syntax = Syntax(text, "text", line_numbers=True, theme="monokai", word_wrap=True)

    title = f"{config.ICONS["dir"]} {target.name} [{decimal(size)}]"
    app_console.print(Panel(syntax, title=title, border_style=theme["accent"], box=box.ROUNDED))


@app.command("cd")
def change_directory(path: str = typer.Argument(..., help="Navigate to another directory")) -> None:
    """Change the current working directory"""
    target = Path(path).expanduser().resolve()
    if not target.exists():
        app_console.print(f"[bold red]Path not found:[/] {target}")
        raise typer.Exit(1)
    if not target.is_dir():
        app_console.print(f"[bold red]The path {target} is not a directory.")
        raise typer.Exit(1)

    cfg = config.load_config()
    theme = config.theme(cfg)

    # TODO check this logic
    app_console.print(f"[{theme['success']}] -> [/] {target}")
    app_console.print(f"\n[dim]Tip: to actually change your shell directory, run:[/]")
    app_console.print(f"  [bold]cd \"$({__APP_PREF__} cd {path} 2>/dev/null | tail -1)\"[/]\n")

    list_dir.list_dir(app_console, target, cfg)

