import os
import time
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.filesize import decimal
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table

import explorer.config as config
import explorer.list_dir as list_dir
import explorer.save_data as save_data
from explorer import __app_name__, __APP_PREF__, __author__, __doc__, __last_update__, __version__
from explorer.ir import intent as intent_mod
from explorer.ir.index import buildIndex, Index
from explorer.ir.rank import SearchParams
from explorer.ir.search import search as ir_search
from explorer.save_data import SaveDataHandler

MAX_VIEW_SIZE = 1024 * 1024
"""Files larger than this will be truncated in console view"""
MAX_VIEW_LINES = 350
"""Maximum number of lines of a text file that will be rendered to console"""

DEFAULT_INDEX_PATH: Path = config.CONFIG_DIR / "index.json.gz"
"""Default on-disk location for the search index built by the `index` command."""

app = typer.Typer(name=__APP_PREF__,
                  help="File Explore and Search",
                  no_args_is_help=True,
                  invoke_without_command=True)

config_app = typer.Typer(help="Manage Configuration Settings",
                         no_args_is_help=True)
app.add_typer(config_app, name="config", rich_help_panel="Utility")

dir_app = typer.Typer(help="For manipulating the current working directory",
                      no_args_is_help=True)
app.add_typer(dir_app, name="cwd", rich_help_panel="Utility")

app_console = Console()
save_data_handler: SaveDataHandler = SaveDataHandler()


def _version(value: bool) -> None:
    """Prints current version"""
    if value:
        typer.echo(f"{__app_name__} v{__version__}")
        raise typer.Exit()


def _about(value: bool) -> None:
    """Prints more detail information about the program"""
    if value:
        typer.echo(f"{__app_name__} v{__version__}, Last Updated: {__last_update__}")
        typer.echo(f"{__doc__}")
        typer.echo(f"By {__author__}")
        raise typer.Exit()


# MAIN
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
    if context.invoked_subcommand is None:
        cfg = config.load_config()
        list_dir.list_dir(app_console, Path.cwd(), cfg)


@app.command("index", help="Build the search index over a directory of documents", rich_help_panel="Search")
def index_corpus(root: Optional[str] = typer.Argument(None, help="Directory to index (default: current directory)"),
                 out: Optional[str] = typer.Option(None, "--out", "-o", help="Where to write the index (default: app data dir)")) -> None:
    """Crawl ``root`` for supported files, build the inverted index + TF-IDF
    vectors, and persist them so the `search` command can use them."""
    cfg = config.load_config()
    theme = config.theme(cfg)
    target = Path(root).expanduser().resolve() if root else Path.cwd()
    out_path = Path(out).expanduser().resolve() if out else DEFAULT_INDEX_PATH

    if not target.is_dir():
        app_console.print(f"[{theme['error']}]Not a directory:[/] {target}")
        raise typer.Exit(1)

    app_console.print(f"[{theme['accent']}]Indexing[/] {target} ...")
    start = time.time()
    idx = buildIndex(target, doPrints=True)

    if idx.N == 0:
        app_console.print(f"[{theme['warning']}]No indexable documents found under {target}.[/]")
        raise typer.Exit(1)

    idx.save(out_path)
    elapsed = time.time() - start
    app_console.print(
        f"[{theme['success']}]Indexed {idx.N} documents[/] "
        f"({len(idx.df)} unique terms) in {elapsed:.1f}s\n"
        f"[{theme['date']}]Index saved to[/] {out_path}"
    )


@app.command("search", help="Search the indexed documents for a query", rich_help_panel="Search")
def search_for(query: str = typer.Argument(..., help="Search query string"),
               num: int = typer.Option(10, "--num", "-n", help="Number of results to show. Default=10"),
               prf: bool = typer.Option(False, "--prf", help="Enable Rocchio pseudo-relevance feedback"),
               boost: bool = typer.Option(False, "--boost", help="Enable query-conditioned file-type boosting"),
               index_path: Optional[str] = typer.Option(None, "--index", "-i", help="Path to a saved index")) -> None:
    """Rank indexed documents against ``query`` using the vector-space model,
    optionally with pseudo-relevance feedback (--prf) and file-type boosting
    (--boost)."""
    cfg = config.load_config()
    theme = config.theme(cfg)
    idx_path = Path(index_path).expanduser().resolve() if index_path else DEFAULT_INDEX_PATH

    if not idx_path.exists():
        app_console.print(
            f"[{theme['error']}]No index found at[/] {idx_path}\n"
            f"[{theme['warning']}]Build one first:[/] exp index <directory>"
        )
        raise typer.Exit(1)

    idx = Index.load(idx_path)
    detected = intent_mod.classify(query)
    results: list = ir_search(idx, query, usePrf=prf, useBoost=boost, params=SearchParams(), topN=num)

    flags = []
    if prf:
        flags.append("PRF")
    if boost:
        flags.append("file-type boost")
    mode = " + ".join(flags) if flags else "baseline TF-IDF cosine"
    header = (f"[{theme['header']}]Query:[/] {query}    "
              f"[{theme['date']}]intent={detected} | mode={mode} | {idx.N} docs[/]")
    app_console.print(Panel(header, box=box.ROUNDED, border_style=theme["accent"]))

    if not results:
        app_console.print(f"  [{theme['date']}](no matching documents)[/]")
        _save_history(query, [])
        return

    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style=theme["header"], pad_edge=False)
    table.add_column("#", width=3, justify="right")
    table.add_column("Score", style=theme["size"], justify="right")
    table.add_column("Type", style=theme["date"])
    table.add_column("Title", style=theme["file"])
    table.add_column("Path", style=theme["date"])

    for rank_i, r in enumerate(results, start=1):
        table.add_row(str(rank_i), f"{r.score:.4f}", r.category, r.title, r.path)
    app_console.print(table)

    # save search history and results
    _save_history(query, results)


def _save_history(query: str, results: list):
    cfg = config.load_config()
    max_hist_len: int = cfg["max_history"]
    temp_save_data = save_data_handler.read_save_data()
    hist: list[tuple[str, list]] = temp_save_data.history
    cwd = temp_save_data.current_working_directory

    if results:
        doc_titles = [r.title for r in results]
    else:
        doc_titles = []
    entry = (query, doc_titles)

    if len(hist) >= max_hist_len:
        hist = hist[1:]
    hist.append(entry)
    if cwd is None:
        cwd = os.getcwd()
    save_data_handler.write_data(Path(cwd), hist)


@app.command("ls", help="List the contents of the current working directory", rich_help_panel="File Explorer")
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

@app.command("open", help="Opens a text file in the console", rich_help_panel="File Explorer")
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


@app.command("cd", help="Change the current working directory", rich_help_panel="File Explorer")
def change_directory(path: str = typer.Argument(..., help="The directory to navigate to")) -> None:
    """Change the current working directory"""
    cfg = config.load_config()
    theme = config.theme(cfg)

    temp_save = save_data_handler.read_save_data()
    cwd = temp_save.current_working_directory

    if cwd is None:
        cwd = os.getcwd()

    path0 = Path(cwd).joinpath(path)
    target = path0.expanduser().resolve()

    if not target.exists():
        app_console.print(f"[{theme["error"]}]Path not found:[/] {target}")
        raise typer.Exit(1)
    if not target.is_dir():
        app_console.print(f"[{theme["warning"]}]The path {target} is not a directory.")
        raise typer.Exit(1)

    temp_save_data = save_data_handler.read_save_data()
    hist = temp_save_data.history
    save_data_handler.write_data(target, hist)

    app_console.print(f"[dim]The current working directory is {cwd}.")

    list_dir.list_dir(app_console, target, cfg)


@app.command("search-history", help="Print the most recent searches", rich_help_panel="Search")
def search_history() -> None:
    cfg = config.load_config()
    theme = config.theme(cfg)

    temp_save = save_data_handler.read_save_data()
    hist = reversed(temp_save.history)
    # items: int = cfg["max_history"]

    # TODO
    # app_console.print(f"[{theme["accent"]}]Search history: last {items} searches[/]")
    # for i, (key, item) in enumerate(hist):
    #     print(i, key, item)

    table = Table(title="Search History", box=box.ROUNDED, border_style=theme["accent"], header_style=theme["header"], show_header=True)
    table.add_column("#", style=theme["header"], width=3)
    table.add_column("Search Query", style=theme["file"])
    table.add_column("Results", style=theme["date"], justify="right")

    for i, (key, item) in enumerate(hist):
        table.add_row(str(i + 1), key, str(len(item)))
    app_console.print(table)


###############################################################################


@dir_app.command("set", help="Set the current working directory")
def set_directory(path: str = typer.Argument(..., help="The directory to set as the current directory")) -> None:
    """Change the current working directory"""
    cfg = config.load_config()
    theme = config.theme(cfg)

    temp_save = save_data_handler.read_save_data()
    cwd = temp_save.current_working_directory

    if cwd is None:
        cwd = os.getcwd()

    path0 = Path(cwd).joinpath(path)
    target = path0.expanduser().resolve()

    if not target.exists():
        app_console.print(f"[{theme["error"]}]Path not found:[/] {target}")
        raise typer.Exit(1)
    if not target.is_dir():
        app_console.print(f"[{theme["warning"]}]The path {target} is not a directory.")
        raise typer.Exit(1)

    temp_save_data = save_data_handler.read_save_data()
    hist = temp_save_data.history
    save_data_handler.write_data(target, hist)

    app_console.print(f"[dim]The current working directory is {cwd}.")


@dir_app.command("show", help="Print the current working directory")
def current_directory() -> None:
    """Print the current working directory"""
    temp_save_data = save_data_handler.read_save_data()
    saved_cwd = temp_save_data.current_working_directory
    app_console.print(f"[green]Current directory is[/] {saved_cwd}")


@dir_app.command("reset", help="Returns the current working directory to its original point")
def return_to_cwd() -> None:
    """Returns the current working directory to its original point"""
    temp_save_data = save_data_handler.read_save_data()
    hist = temp_save_data.history
    cwd: Path = Path.cwd()
    save_data_handler.write_data(cwd, hist)
    app_console.print(f"[green]Current directory is now[/] {cwd}")


###############################################################################


@config_app.command("loc", help="Prints the current paths to file for saved data and config file")
def get_save_location() -> None:
    """Prints the paths to the save data"""

    cfg = config.load_config()
    theme = config.theme(cfg)

    path0: Path = save_data.get_save_path()
    path0r = str(path0.resolve())
    app_console.print(f"Save data located at [{theme["symlink"]}]{path0r}[/]")
    path1: Path = config.get_save_path()
    app_console.print(f"Configuration data located at [{theme["symlink"]}]{path1}[/]")


@config_app.command("show", help="Prints the current configuration settings")
def show_config() -> None:
    cfg = config.load_config()
    theme = config.theme(cfg)
    config_save: Path = config.get_save_path()

    table = Table(title="Configuration Settings", box=box.ROUNDED, border_style=theme["accent"], header_style=theme["header"], show_header=True)
    table.add_column("Key", style=theme["header"], width=20)
    table.add_column("Value", style=theme["file"])
    table.add_column("Description", style=theme["date"])

    descriptions = {
        "show_hidden": "Show dotfiles/hidden entries",
        "sort_by": "Sort key: name | size | date | type",
        "sort_reverse": "Reverse sort order",
        "max_history": "Max recent-files entries kept",
        "color_theme": "Color theme: default | minimal | vibrant",
        "date_format": "date.strftime format for timestamps",
    }
    for k, v in cfg.items():
        table.add_row(k, str(v), descriptions.get(k, ""))
    app_console.print(table)
    app_console.print(f"[{theme["dir"]}]Config file:[/] {config_save}")


@config_app.command("set", help="Set a configuration value")
def config_set(key: str = typer.Argument(..., help="Configuration key"),
               value: str = typer.Argument(..., help="New value")) -> None:
    cfg = config.load_config()
    theme = config.theme(cfg)

    if key not in config.DEFAULT_CONFIG:
        app_console.print(f"[{theme["error"]}]Unknown key:[/] {key}")
        app_console.print(f"Valid keys: {', '.join(config.DEFAULT_CONFIG.keys())}")
        raise typer.Exit(1)

    # Type correction
    original = config.DEFAULT_CONFIG[key]
    try:
        if isinstance(original, bool):
            valid_value = value.lower() in ("1", "true", "yes", "on")
        elif isinstance(original, int):
            valid_value = int(value)
        else:
            valid_value = value
    except ValueError:
        app_console.print(f"[{theme["error"]}]Invalid value for {key}:[/] {value}")
        raise typer.Exit(1)

    cfg[key] = valid_value
    config.save_config(cfg)
    app_console.print(f"[{theme["success"]}]Set[/] {key} = {valid_value}")


@config_app.command("reset", help="Resets settings to default configuration")
def config_reset(force: bool = typer.Option(False, "--force", "-f")) -> None:
    """Reset configuration to defaults."""
    cfg = config.load_config()
    theme = config.theme(cfg)
    if not force and not Confirm.ask(f"[{theme["warning"]}]Reset all settings to defaults?[/]"):
        app_console.print("[dim]Aborted.[/]")
        return
    config.save_config(config.DEFAULT_CONFIG.copy())
    app_console.print(f"[{theme["success"]}]Configuration reset to defaults.[/]")

