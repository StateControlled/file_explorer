"""Handles reading a writing of save data: the current (or last referenced) working directory, and TODO search history"""
import json
from pathlib import Path
from typing import Any, NamedTuple
import os
import typer

from explorer import __app_name__, DB_READ_ERROR, DB_WRITE_ERROR, JSON_ERROR, SUCCESS, __version__

DEFAULT_DATA_STORE_PATH: Path = Path(typer.get_app_dir(__app_name__))
DEFAULT_SAVE_FILE_PATH: Path = DEFAULT_DATA_STORE_PATH / "save_data.json"


def init() -> None:
    # Make directory and file and initialize file with empty data
    if not DEFAULT_DATA_STORE_PATH.exists():
        DEFAULT_DATA_STORE_PATH.mkdir(exist_ok=True)
        DEFAULT_SAVE_FILE_PATH.touch(exist_ok=True)

        with DEFAULT_SAVE_FILE_PATH.open(mode="w") as file:
            data = {
                "version": __version__,
                "cwd": os.getcwd(),
                "history": []
            }
            json.dump(data, file, indent=4)


def get_save_data_path() -> Path:
    return DEFAULT_DATA_STORE_PATH


class DataResponse(NamedTuple):
    current_working_directory: Path | None
    # A list of dictionaries representing to-dos
    history: list[dict[str, Any]]
    # The return or error code
    error: int


class SaveDataHandler:
    """Handles reading and writing data to the database using the standard JSON library"""

    def __init__(self) -> None:
        self._db_path = DEFAULT_SAVE_FILE_PATH

    def read_save_data(self) -> DataResponse:
        """Reads the to-do list from the database and deserializes it"""
        try:
            with self._db_path.open(mode="r") as db:
                try:
                    json_data = json.load(db)
                    cwd = json_data["cwd"]
                    history = json_data["history"]

                    return DataResponse(cwd, history, SUCCESS)
                except json.JSONDecodeError:
                    return DataResponse(None, [], JSON_ERROR)
        except OSError:
            return DataResponse(None, [], DB_READ_ERROR)

    def write_data(self, cwd: Path, history: list[dict[str, Any]]) -> DataResponse:
        """write to the database"""
        try:
            with self._db_path.open(mode="w") as db:
                json_data = {
                    "version": __version__,
                    "cwd": cwd,
                    "history": history
                }
                json.dump(json_data, db, indent=4)

            return DataResponse(cwd, history, SUCCESS)
        except OSError:
            return DataResponse(cwd, history, DB_WRITE_ERROR)
