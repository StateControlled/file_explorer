
# The retrieval engine works on plain text, but the corpus is deliberately a mix
# of formats (prose, web pages, source code, notebooks, PDFs). Each format needs
# its own extractor so that we index the content rather than the markup or
# container syntax. This module centralizes that logic and also defines the
# coarse file category used later by the query-conditioned file-type boost.

#libraries todo the format-specific heavy lifting: BeautifulSoup
#(bs4) strips HTML, and pypdf extracts PDF text. Notebooks are plain JSON.

from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup


CATEGORY_BY_EXT: dict[str, str] = {
    # prose / plain text
    ".txt": "text", ".text": "text", ".rst": "text",
    # markdown
    ".md": "markdown", ".markdown": "markdown",
    # web
    ".html": "html", ".htm": "html",
    # documents
    ".pdf": "pdf",
    # notebooks
    ".ipynb": "notebook",
    # source code
    ".py": "code", ".java": "code", ".c": "code", ".h": "code",
    ".cpp": "code", ".cc": "code", ".cxx": "code", ".hpp": "code",
    ".cs": "code", ".js": "code", ".ts": "code", ".go": "code",
    ".rb": "code", ".rs": "code", ".rkt": "code", ".hs": "code",
}


CATEGORIES: tuple[str, ...] = ("text", "markdown", "html", "pdf", "notebook", "code")

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(CATEGORY_BY_EXT)


def fileCategory(path: Path | str) -> str:
    return CATEGORY_BY_EXT.get(Path(path).suffix.lower(), "text")



#HTML -> text (BeautifulSoup)
def _parseHtml(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript", "head"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


#Jupyter notebook -> text
def _parseIpynb(raw: str) -> str:
    try:
        nb = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    parts: list[str] = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") in ("markdown", "code"):
            src = cell.get("source", "")
            parts.append("".join(src) if isinstance(src, list) else str(src))
    return "\n".join(parts)



# PDF -> text (pypdf)
def _parsePdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""



def extractText(path: Path | str) -> str:
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _parsePdf(path)

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    if ext in (".html", ".htm"):
        return _parseHtml(raw)
    if ext == ".ipynb":
        return _parseIpynb(raw)
    return raw
