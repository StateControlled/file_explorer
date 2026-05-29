"""Top-level package for this application."""

__app_name__ = "File Manager CLI"
__version__ = "0.1-alpha"
__author__ = "William Berthouex, Noah Sleeman"
__doc__ = "CSC575 Intelligent Information Retrieval - Final Project"
__last_update__ = "2026-05-26"

__APP_PREF__ = "exp"

# Define a series of return and error codes and assign integer numbers to them using range()
(
    SUCCESS,
    DIR_ERROR,
    FILE_ERROR,
    DB_READ_ERROR,
    DB_WRITE_ERROR,
    JSON_ERROR,
    ID_ERROR
) = range(7)

# ERROR is a dictionary that maps error codes to human-readable error messages.
ERRORS = {
    DIR_ERROR : "config directory error",
    FILE_ERROR : "config file error",
    DB_READ_ERROR : "database read error",
    DB_WRITE_ERROR : "database write error",
    ID_ERROR : "to-do id error"
}
