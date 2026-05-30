#!/usr/bin/env python3
"""Reproducible multi-file-type corpus builder.

ATTRIBUTION / AI USE
--------------------
This is a one-time *data-collection* utility -- it downloads a corpus from public
sources so the search engine has something to index and be evaluated on. It is
**not** part of the information-retrieval system itself (the index, weighting,
ranking, intent classifier, boost, feedback and metrics in ``explorer/ir`` and
``evaluation`` are our own work). This script was written with the help of an AI
coding assistant (Anthropic's Claude) and is included here for transparency and
reproducibility. Its purpose is purely to gather and label public documents.

Sources and file types
-----------------------
    Project Gutenberg   .txt              public-domain books (literary prose)
    Wikipedia           .html  +  .txt    encyclopedia articles (web + prose)
    arXiv               .pdf              CS research papers (documents)
    GitHub (code)       .py/.java/.cpp...  source files from popular repos
    GitHub (notebooks)  .ipynb            Jupyter notebooks (outputs stripped)

Every downloaded file is recorded in ``manifest.json`` with provenance metadata,
in particular a ``theme`` label derived from *where the file came from* (not its
text). The evaluation uses these provenance labels to build relevance judgements
(qrels), which keeps the judgements independent of the content-based ranker.
Several themes (machine_learning, cryptography, databases, ...) appear across
multiple sources/file types on purpose, so "which file type is relevant" is
testable.

Usage
-----
    python -m corpus.build_corpus --out data/corpus            # ~45-70 MB
    python -m corpus.build_corpus --out data/corpus --scale 0.5   # smaller
    python -m corpus.build_corpus --only wikipedia,gutenberg   # a subset

Re-running fetches the *current* most-recent arXiv/Wikipedia articles, so the
corpus is equivalent but not byte-identical over time. Only the Python standard
library is required.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

USER_AGENT = "CSC575-FileExplorer-Corpus/1.0 (course project; contact: student@example.edu)"

# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------
# Project Gutenberg: (ebook id, theme, title)
GUTENBERG_BOOKS: list[tuple[int, str, str]] = [
    (1342, "literature", "Pride and Prejudice"),
    (11, "literature", "Alice's Adventures in Wonderland"),
    (84, "literature", "Frankenstein"),
    (1661, "literature", "The Adventures of Sherlock Holmes"),
    (98, "literature", "A Tale of Two Cities"),
    (1400, "literature", "Great Expectations"),
    (345, "literature", "Dracula"),
    (174, "literature", "The Picture of Dorian Gray"),
    (1260, "literature", "Jane Eyre"),
    (5200, "literature", "Metamorphosis"),
    (1080, "philosophy", "A Modest Proposal"),
    (1232, "philosophy", "The Prince"),
    (3207, "philosophy", "Leviathan"),
    (5827, "philosophy", "The Problems of Philosophy"),
    (1228, "science", "On the Origin of Species"),
    (2009, "science", "The Voyage of the Beagle"),
    (21076, "science", "Euclid's Elements (Book I)"),
    (33283, "science", "Relativity: The Special and General Theory"),
]

# Wikipedia: theme -> search query (fetch several articles per theme)
WIKIPEDIA_THEMES: dict[str, str] = {
    "machine_learning": "machine learning",
    "cryptography": "cryptography",
    "databases": "database management system",
    "operating_systems": "operating system",
    "computer_vision": "computer vision",
    "nlp": "natural language processing",
    "algorithms": "algorithm data structure",
    "information_retrieval": "information retrieval search engine",
    "distributed_systems": "distributed computing",
    "astronomy": "planet solar system astronomy",
    "biology": "cell biology genetics",
    "chemistry": "chemical reaction chemistry",
    "history": "ancient rome roman empire",
    "music": "music theory harmony",
    "economics": "macroeconomics inflation",
    "geology": "volcano plate tectonics",
    "medicine": "human immune system",
    "philosophy": "epistemology philosophy",
}

# arXiv: theme -> category (several recent papers per category)
ARXIV_CATEGORIES: dict[str, str] = {
    "information_retrieval": "cs.IR",
    "machine_learning": "cs.LG",
    "nlp": "cs.CL",
    "computer_vision": "cs.CV",
    "cryptography": "cs.CR",
    "databases": "cs.DB",
    "algorithms": "cs.DS",
    "distributed_systems": "cs.DC",
}

# GitHub code: (owner, repo, branch, [extensions], theme)
GITHUB_CODE_REPOS: list[tuple[str, str, str, list[str], str]] = [
    ("pallets", "flask", "main", [".py"], "web_framework"),
    ("psf", "requests", "main", [".py"], "http_library"),
    ("nlohmann", "json", "develop", [".hpp", ".cpp", ".h"], "json_parsing"),
    ("google", "gson", "main", [".java"], "json_parsing"),
    ("scikit-learn", "scikit-learn", "main", [".py"], "machine_learning"),
    ("sqlparser-rs", "sqlparser-rs", "main", [".rs"], "databases"),
    ("python", "cpython", "main", [".c", ".h"], "operating_systems"),
]

# GitHub notebooks: (owner, repo, branch, theme)
GITHUB_NOTEBOOK_REPOS: list[tuple[str, str, str, str]] = [
    ("jakevdp", "PythonDataScienceHandbook", "master", "data_science"),
    ("fchollet", "deep-learning-with-python-notebooks", "master", "machine_learning"),
    ("rasbt", "machine-learning-book", "main", "machine_learning"),
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _get(url: str, *, timeout: int = 30, binary: bool = False, max_bytes: int | None = None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        # Skip oversized downloads (e.g. figure-heavy PDFs) before reading the body.
        if max_bytes is not None:
            clen = resp.headers.get("Content-Length")
            if clen and int(clen) > max_bytes:
                raise ValueError(f"resource too large ({int(clen)} bytes > {max_bytes})")
        data = resp.read(max_bytes + 1 if max_bytes else None)
    if max_bytes is not None and len(data) > max_bytes:
        raise ValueError("resource exceeded size cap during read")
    return data if binary else data.decode("utf-8", errors="replace")


def _safe_name(text: str, maxlen: int = 80) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")
    return slug[:maxlen] or "doc"


def _strip_notebook(path: Path) -> None:
    """Remove cell outputs from a notebook (drops embedded images -> tiny file)."""
    try:
        nb = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        for cell in nb.get("cells", []):
            if "outputs" in cell:
                cell["outputs"] = []
            if "execution_count" in cell:
                cell["execution_count"] = None
        path.write_text(json.dumps(nb), encoding="utf-8")
    except Exception:
        pass


class Manifest:
    """Accumulates provenance records and writes ``manifest.json``."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def add(self, path: Path, *, source: str, theme: str, title: str, url: str) -> None:
        self.records.append({
            "path": str(path.resolve()),
            "source": source,
            "theme": theme,
            "title": title,
            "url": url,
            "ext": path.suffix.lower(),
        })

    def write(self, out_dir: Path) -> None:
        (out_dir / "manifest.json").write_text(json.dumps(self.records, indent=2))


def _scaled(n: int, scale: float) -> int:
    return max(1, int(round(n * scale)))


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------
def collect_gutenberg(out_dir: Path, manifest: Manifest, scale: float) -> int:
    dest = out_dir / "gutenberg"
    dest.mkdir(parents=True, exist_ok=True)
    books = GUTENBERG_BOOKS[: _scaled(len(GUTENBERG_BOOKS), scale)]
    count = 0
    for ebook_id, theme, title in books:
        urls = [
            f"https://www.gutenberg.org/cache/epub/{ebook_id}/pg{ebook_id}.txt",
            f"https://www.gutenberg.org/files/{ebook_id}/{ebook_id}-0.txt",
        ]
        for url in urls:
            try:
                text = _get(url, timeout=45)
                if len(text) < 1000:
                    continue
                fpath = dest / f"{ebook_id}_{_safe_name(title)}.txt"
                fpath.write_text(text, encoding="utf-8")
                manifest.add(fpath, source="gutenberg", theme=theme, title=title, url=url)
                count += 1
                print(f"  [gutenberg] {title}")
                break
            except Exception:
                continue
        time.sleep(0.3)
    return count


def collect_wikipedia(out_dir: Path, manifest: Manifest, scale: float, per_theme: int = 5) -> int:
    dest = out_dir / "wikipedia"
    dest.mkdir(parents=True, exist_ok=True)
    per_theme = _scaled(per_theme, scale)
    count = 0
    for theme, query in WIKIPEDIA_THEMES.items():
        search = ("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json"
                  f"&srlimit={per_theme}&srsearch={urllib.parse.quote(query)}")
        try:
            hits = json.loads(_get(search))["query"]["search"]
        except Exception as exc:
            print(f"  [wikipedia] search failed for {theme}: {exc}")
            continue
        for hit in hits:
            title = hit["title"]
            enc = urllib.parse.quote(title.replace(" ", "_"))
            try:
                ex_url = ("https://en.wikipedia.org/w/api.php?action=query&format=json"
                          "&prop=extracts&explaintext=1&redirects=1"
                          f"&titles={urllib.parse.quote(title)}")
                pages = json.loads(_get(ex_url))["query"]["pages"]
                extract = next(iter(pages.values())).get("extract", "")
                if len(extract) < 400:
                    continue
                base = _safe_name(title)
                tpath = dest / f"{base}.txt"
                tpath.write_text(extract, encoding="utf-8")
                manifest.add(tpath, source="wikipedia", theme=theme, title=title,
                             url=f"https://en.wikipedia.org/wiki/{enc}")
                count += 1
                html = _get(f"https://en.wikipedia.org/api/rest_v1/page/html/{enc}", timeout=30)
                hpath = dest / f"{base}.html"
                hpath.write_text(html, encoding="utf-8")
                manifest.add(hpath, source="wikipedia", theme=theme, title=title,
                             url=f"https://en.wikipedia.org/wiki/{enc}")
                count += 1
                print(f"  [wikipedia/{theme}] {title}")
            except Exception:
                continue
            time.sleep(0.1)
    return count


def collect_arxiv(out_dir: Path, manifest: Manifest, scale: float, per_cat: int = 3) -> int:
    dest = out_dir / "arxiv"
    dest.mkdir(parents=True, exist_ok=True)
    per_cat = _scaled(per_cat, scale)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    import xml.etree.ElementTree as ET
    count = 0
    for theme, cat in ARXIV_CATEGORIES.items():
        api = ("http://export.arxiv.org/api/query?"
               f"search_query=cat:{cat}&start=0&max_results={per_cat}"
               "&sortBy=submittedDate&sortOrder=descending")
        try:
            feed = ET.fromstring(_get(api, timeout=45))
        except Exception as exc:
            print(f"  [arxiv] query failed for {cat}: {exc}")
            continue
        for entry in feed.findall("a:entry", ns):
            arxiv_id = (entry.findtext("a:id", default="", namespaces=ns).rsplit("/", 1)[-1])
            title = " ".join(entry.findtext("a:title", default="", namespaces=ns).split())
            if not arxiv_id:
                continue
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            try:
                # Cap at 3 MB to keep the corpus small and skip figure-heavy outliers.
                data = _get(pdf_url, timeout=60, binary=True, max_bytes=3 * 1024 * 1024)
                if len(data) < 5000 or data[:4] != b"%PDF":
                    continue
                fpath = dest / f"{_safe_name(arxiv_id)}.pdf"
                fpath.write_bytes(data)
                manifest.add(fpath, source="arxiv", theme=theme, title=title or arxiv_id, url=pdf_url)
                count += 1
                print(f"  [arxiv/{theme}] {arxiv_id}  {title[:50]}")
            except Exception:
                continue
            time.sleep(3.0)  # arXiv asks for >=3s between requests
        time.sleep(3.0)
    return count


def _github_tree(owner: str, repo: str, branch: str) -> list[str]:
    """Return all file paths in a repo via a single Git tree API call."""
    api = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    tree = json.loads(_get(api, timeout=45)).get("tree", [])
    return [node["path"] for node in tree if node.get("type") == "blob"]


def _download_raw(owner: str, repo: str, branch: str, path: str, dest: Path) -> Path | None:
    raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{urllib.parse.quote(path)}"
    try:
        data = _get(raw, timeout=30)
        if len(data) < 80:
            return None
        fpath = dest / _safe_name(f"{repo}__{path.replace('/', '_')}")
        fpath.write_text(data, encoding="utf-8")
        return fpath
    except Exception:
        return None


def _sample(paths: list[str], k: int) -> list[str]:
    """Deterministic even sampling so re-runs pick the same files."""
    if len(paths) <= k:
        return paths
    step = len(paths) / k
    return [paths[int(i * step)] for i in range(k)]


def collect_github_code(out_dir: Path, manifest: Manifest, scale: float, per_repo: int = 50) -> int:
    dest = out_dir / "code"
    dest.mkdir(parents=True, exist_ok=True)
    per_repo = _scaled(per_repo, scale)
    count = 0
    for owner, repo, branch, exts, theme in GITHUB_CODE_REPOS:
        try:
            all_paths = _github_tree(owner, repo, branch)
        except Exception as exc:
            print(f"  [code] tree failed for {owner}/{repo}: {exc}")
            continue
        wanted = [p for p in all_paths if Path(p).suffix.lower() in exts
                  and "test" not in p.lower()]
        chosen = _sample(sorted(wanted), per_repo)
        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = {pool.submit(_download_raw, owner, repo, branch, p, dest): p for p in chosen}
            for fut in as_completed(futs):
                fpath = fut.result()
                if fpath:
                    manifest.add(fpath, source=f"github:{owner}/{repo}", theme=theme,
                                 title=Path(futs[fut]).name,
                                 url=f"https://github.com/{owner}/{repo}/blob/{branch}/{futs[fut]}")
                    count += 1
        print(f"  [code/{theme}] {owner}/{repo}: {len(chosen)} files")
    return count


def collect_github_notebooks(out_dir: Path, manifest: Manifest, scale: float, per_repo: int = 15) -> int:
    dest = out_dir / "notebooks"
    dest.mkdir(parents=True, exist_ok=True)
    per_repo = _scaled(per_repo, scale)
    count = 0
    for owner, repo, branch, theme in GITHUB_NOTEBOOK_REPOS:
        try:
            all_paths = _github_tree(owner, repo, branch)
        except Exception as exc:
            print(f"  [notebooks] tree failed for {owner}/{repo}: {exc}")
            continue
        wanted = [p for p in all_paths if p.lower().endswith(".ipynb")]
        chosen = _sample(sorted(wanted), per_repo)
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {pool.submit(_download_raw, owner, repo, branch, p, dest): p for p in chosen}
            for fut in as_completed(futs):
                fpath = fut.result()
                if fpath:
                    _strip_notebook(fpath)  # drop outputs -> keep only source/markdown
                    manifest.add(fpath, source=f"github:{owner}/{repo}", theme=theme,
                                 title=Path(futs[fut]).stem,
                                 url=f"https://github.com/{owner}/{repo}/blob/{branch}/{futs[fut]}")
                    count += 1
        print(f"  [notebooks/{theme}] {owner}/{repo}: {len(chosen)} files")
    return count


COLLECTORS = {
    "gutenberg": collect_gutenberg,
    "wikipedia": collect_wikipedia,
    "arxiv": collect_arxiv,
    "code": collect_github_code,
    "notebooks": collect_github_notebooks,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the multi-file-type IR corpus.")
    ap.add_argument("--out", default="data/corpus", help="Output directory (default: data/corpus)")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="Scale factor on every per-source count (e.g. 0.5 for a smaller build)")
    ap.add_argument("--only", default="", help="Comma-separated subset of: " + ",".join(COLLECTORS))
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest()
    chosen = [s.strip() for s in args.only.split(",") if s.strip()] or list(COLLECTORS)

    print(f"Building corpus into {out_dir.resolve()}  (scale={args.scale})")
    totals: dict[str, int] = {}
    for name in chosen:
        collector = COLLECTORS.get(name)
        if not collector:
            print(f"  (unknown source '{name}', skipping)")
            continue
        print(f"\n== {name} ==")
        start = time.time()
        try:
            totals[name] = collector(out_dir, manifest, args.scale)
        except Exception as exc:
            print(f"  collector '{name}' aborted: {exc}")
            totals[name] = 0
        print(f"  -> {totals[name]} files in {time.time() - start:.0f}s")

    manifest.write(out_dir)
    print("\n=== Summary ===")
    for name, n in totals.items():
        print(f"  {name:12s} {n:5d} files")
    print(f"  {'TOTAL':12s} {sum(totals.values()):5d} files")
    print(f"Manifest written to {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
