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
import explorer.save_data as save_data
from explorer import __app_name__, __APP_PREF__, __author__, __doc__, __last_update__, __version__
from explorer.save_data import SaveDataHandler

MAX_VIEW_SIZE = 1024 * 1024
"""Files larger than this will be truncated in console view"""
MAX_VIEW_LINES = 350
"""Maximum number of lines of a text file that will be rendered to console"""

app = typer.Typer(name=__APP_PREF__,
                  help="File Explore and Search",
                  no_args_is_help=True,
                  invoke_without_command=True)

app_console = Console()
save_data_handler: SaveDataHandler = SaveDataHandler()


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
    if context.invoked_subcommand is None:
        cfg = config.load_config()
        list_dir.list_dir(app_console, Path.cwd(), cfg)


@app.command("cfg", help="Prints the current configuration")
def show_config() -> None:
    cfg = config.load_config()
    typer.echo(cfg)


@app.command("loc", help="Prints the current paths to saved data")
def get_save_location() -> None:
    """Prints the paths to the save data"""
    path0: Path = save_data.get_save_path()
    app_console.print(f"[green]Save data located at[/] {path0}")
    path1: Path = config.get_save_path()
    app_console.print(f"[green]Save data located at[/] {path1}")


@app.command("return-cwd", help="Returns the current working directory to its original point")
def return_to_cwd() -> None:
    """Returns the current working directory to its original point"""
    temp_save_data = save_data_handler.read_save_data()
    hist = temp_save_data.history
    cwd: Path = Path.cwd()
    save_data_handler.write_data(cwd, hist)
    app_console.print(f"[green]Current directory is now[/] {cwd}")


@app.command("ls")
def list_directory_contents(path: Optional[str] = typer.Argument(None, help="List information about the files (the current directory by default"),
                            hidden: bool = typer.Option(False, "--hidden", "-h", help="Show hidden files and directories. Default=False"),
                            sort: str = typer.Option("", "--sort", "-s", help="Sort by [name|size|date|type]. Default='name'"),
                            reverse: bool = typer.Option(False, "--reverse", "-r", help="Reverse the sort order. Default=False"),
                            long: bool = typer.Option(False, "--long", "-l", help="List additional details about files. Default=False")) -> None:
    """List directory contents"""
    cfg = config.load_config()
    theme = config.theme(cfg)
    temp_save_data = save_data_handler.read_save_data()
    saved_cwd = temp_save_data.current_working_directory

    if hidden:
        cfg["show_hidden"] = True
    if sort:
        cfg["sort_by"] = sort
    if reverse:
        cfg["sort_reverse"] = True

    if path:
        target = Path(path)
    elif saved_cwd:
        target = Path(saved_cwd)
    else:
        target = Path.cwd()
    # target = Path(path) if path else Path.cwd()

    if not target.exists():
        app_console.print(f"[{theme["error"]}]Path not found:[/] {target}")
        raise typer.Exit(1)
    if not target.is_dir():
        app_console.print(f"[{theme["warning"]}]The path {target} is not a directory.")
        raise typer.Exit(1)

    list_dir.list_dir(app_console, target, cfg, long_listing=long)

@app.command("open", help="Opens a text file in the console")
def open_text_file(path: str = typer.Argument(..., help="The file to be opened"),
                   lines: int = typer.Option(0, "--num_lines", "-n")) -> None:
    """View a text file in the console"""

    temp_save_data = save_data_handler.read_save_data()
    saved_cwd = temp_save_data.current_working_directory

    if saved_cwd:
        n_path = str(saved_cwd) + '\\' + path
        target = Path(n_path).expanduser().resolve()
    else:
        target = Path(path).expanduser().resolve()

    cfg = config.load_config()
    theme = config.theme(cfg)

    if not target.exists():
        app_console.print(f"[{theme["error"]}]Path not found:[/] {target}")
        raise typer.Exit(1)
    if target.is_dir():
        app_console.print(f"[{theme["warning"]}]The path {target} is a directory.[/] Make sure you are targeting a file.")
        raise typer.Exit(1)

    size = target.stat().st_size
    if size > MAX_VIEW_SIZE:
        app_console.print(f"[{theme["warning"]}]! File is too large: ({decimal(size)} bytes). Showing first {MAX_VIEW_LINES} lines.[/]")
        lines = lines or MAX_VIEW_LINES

    try:
        text: str = target.read_text(errors="replace")
    except Exception as e:
        app_console.print(f"[{theme["error"]}]There was an error while reading the file:[/]{e}")
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
    cfg = config.load_config()
    theme = config.theme(cfg)
    target = Path(path).expanduser().resolve()

    if not target.exists():
        app_console.print(f"[{theme["error"]}]Path not found:[/] {target}")
        raise typer.Exit(1)
    if not target.is_dir():
        app_console.print(f"[{theme["warning"]}]The path {target} is not a directory.")
        raise typer.Exit(1)

    # TODO check if this is working - remembering cwd
    temp_save_data = save_data_handler.read_save_data()
    hist = temp_save_data.history

    save_data_handler.write_data(target, hist)

    list_dir.list_dir(app_console, target, cfg)


@app.command("search", help="Searches for files in the current directory")
def search_for(query: str = typer.Argument(..., help="Search query string")) -> None:
    # TODO implement search logic
    app_console.print(f"Searching for query: {query}")

