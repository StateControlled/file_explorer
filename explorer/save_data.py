import configparser
import json
from pathlib import Path
from typing import Any, Dict, List, NamedTuple

from explorer import __APP_PREF__,SUCCESS, DIR_ERROR, FILE_ERROR, JSON_ERROR, DB_WRITE_ERROR, DB_READ_ERROR

DEFAULT_DATA_STORE_PATH: Path = Path.home().joinpath(".exp_save_data.json")


def get_database_path() -> Path:
    """Returns the current path to the database file"""
    config_parser = configparser.ConfigParser()
    config_parser.read(DEFAULT_DATA_STORE_PATH)
    return Path(config_parser["General"]["cwd"])

def init_database() -> int:
    """Creates the (empty) database file"""
    try:
        DEFAULT_DATA_STORE_PATH.write_text("[]") # empty list
        return SUCCESS
    except OSError:
        return DB_WRITE_ERROR

class DBResponse(NamedTuple):
    # A list of dictionaries representing to-dos
    history: List[Dict[str, Any]]
    # The return or error code
    error: int

class DatabaseHandler:
    """Handles reading and writing data to the database using the standard JSON library"""
    def __init__(self) -> None:
        self._db_path = DEFAULT_DATA_STORE_PATH

    def read_save_data(self) -> DBResponse:
        """Reads the to-do list from the database and deserializes it"""
        try:
            with self._db_path.open(mode="r") as db:
                try:
                    return DBResponse(json.load(db), SUCCESS)
                except json.JSONDecodeError:
                    return DBResponse([], JSON_ERROR)
        except OSError:
            return DBResponse([], DB_READ_ERROR)

    def write_todos(self, todo_list: List[Dict[str, Any]]) -> DBResponse:
        """Takes a list of to-do dictionaries and writes it to the database"""
        try:
            with self._db_path.open(mode="w") as db:
                json.dump(todo_list, db, indent=4)
            return DBResponse(todo_list, SUCCESS)
        except OSError:
            return DBResponse(todo_list, DB_WRITE_ERROR)




