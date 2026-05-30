# Intents:
#     "code"     -- the user wants source code/notebooks
#     "prose"    -- the user wants natural-language explanation/documents
#     "neutral"  -- no strong signal either way

from __future__ import annotations

import re

_CODE_KEYWORDS: frozenset[str] = frozenset("""
    def class import return void public private static const func function lambda
    yield async await struct typedef namespace template include printf println
    cout cin stdin stdout stderr malloc free pointer nullptr null none self this
    int char bool float double string array vector hashmap dict tuple list set
    iterator recursion compile syntax exception throw catch finally regex api sdk
    argv argc args kwargs init main override interface implements extends throws
    boolean integer param parameter variable method constructor inheritance
    algorithm bug debug stacktrace traceback segfault compile runtime
""".split())

_PROSE_PHRASES: tuple[str, ...] = (
    "how to", "how do", "how does", "how can", "what is", "what are", "what was",
    "why is", "why do", "why does", "explain", "definition of", "meaning of",
    "history of", "who is", "who was", "who were", "when did", "when was",
    "tell me about", "introduction to", "overview of", "summary of", "describe",
)

_QUESTION_WORDS: frozenset[str] = frozenset(
    "how what why who when where which whose".split()
)

_CODE_SYMBOL_RE = re.compile(r"[(){}\[\];]|::|->|=>|==|!=|<=|>=|&&|\|\|")
_SNAKE_CASE_RE = re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b")     # read_save_data
_CAMEL_CASE_RE = re.compile(r"\b[a-z]+[A-Z][A-Za-z0-9]*\b")        # readSaveData
_DOTTED_CALL_RE = re.compile(r"\b\w+\.\w+")                         # os.path, np.array
_FILE_EXT_RE = re.compile(r"\.(py|java|cpp|cc|h|hpp|js|ts|go|rs|ipynb)\b")


def _codeScore(query: str, tokens: list[str]) -> int:
    score = sum(1 for t in tokens if t in _CODE_KEYWORDS)
    if _CODE_SYMBOL_RE.search(query):
        score += 2
    score += len(_SNAKE_CASE_RE.findall(query))
    score += len(_CAMEL_CASE_RE.findall(query))
    if _DOTTED_CALL_RE.search(query):
        score += 1
    if _FILE_EXT_RE.search(query.lower()):
        score += 2
    return score


def _proseScore(query: str, tokens: list[str]) -> int:
    low = query.lower()
    score = 2 * sum(1 for phrase in _PROSE_PHRASES if phrase in low)
    if tokens and tokens[0] in _QUESTION_WORDS:
        score += 1
    if low.rstrip().endswith("?"):
        score += 1
    return score


def classify(query: str) -> str:
    """Return the intent label ("code", "prose" or "neutral") for ``query``."""
    tokens = re.findall(r"[A-Za-z_]+", query)
    lowTokens = [t.lower() for t in tokens]
    code = _codeScore(query, lowTokens)
    prose = _proseScore(query, lowTokens)
    if code == 0 and prose == 0:
        return "neutral"
    if code > prose:
        return "code"
    if prose > code:
        return "prose"
    return "neutral"
