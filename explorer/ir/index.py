# Inverted index and TF-IDF vector-space model.
#     tf weight   wTf = 1 + log10(tf)          (logarithmic, dampens repetition)
#     idf weight  idf = log10(N / df)           (collection frequency)
#     weight      w   = wTf * idf
#     normalize   each document/query vector is L2-normalized (the "c" / cosine)
# With both sides L2-normalized, cosine similarity is just the dot product. Using
# the same weighting on both sides also means Rocchio relevance feedback (which
# averages document vectors) operates in exactly the same space as the query.
# On disk we persist only the raw structure. the document list, the document
# frequencies, and the raw term-frequency postings as gzipped JSON. The IDF
# values and the normalized vectors are recomputed at load time. This keeps the
# stored file compact (integers, not floats) and keeps the weighting math visible
# in code rather than baked into the artifact.

from __future__ import annotations

import gzip
import json
import math
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator

from explorer.ir import parsers
from explorer.ir.preprocess import analyze


@dataclass
class DocMeta:
    id: int
    path: str
    category: str
    title: str
    nTerms: int

#tf-idf vector datastructure 
class Index:

    def __init__(self) -> None:
        self.documents: list[DocMeta] = []
        self.df: dict[str, int] = {}
        #term -> {docId: tf}
        self._rawPostings: dict[str, dict[int, int]] = {}
        self.idf: dict[str, float] = {}
        self.postings: dict[str, dict[int, float]] = {}    #term -> {docId: wNorm}
        self.docVectors: dict[int, dict[str, float]] = {}  #docId -> {term: wNorm}

    @property
    #number of documents in the index
    def N(self) -> int:
        return len(self.documents)

    def addDocument(self, path: str, category: str, title: str, terms: list[str]) -> int:
        """Add one already-analyzed document; returns its assigned id."""
        docId = len(self.documents)
        tf = Counter(terms)
        self.documents.append(
            DocMeta(id=docId, path=path, category=category, title=title, nTerms=len(terms))
        )
        for term, count in tf.items():
            self._rawPostings.setdefault(term, {})[docId] = count
            self.df[term] = self.df.get(term, 0) + 1
        return docId

    #normalize and finalize the index
    def finalize(self) -> "Index":
        n = self.N
        if n == 0:
            return self
        # 1) inverse document frequency
        self.idf = {term: math.log10(n / df) for term, df in self.df.items()}

        # 2) un-normalized tf-idf weights + per-document squared norm
        sqNorm: dict[int, float] = {}
        weighted: dict[str, dict[int, float]] = {}
        for term, posting in self._rawPostings.items():
            idf = self.idf[term]
            wt = weighted.setdefault(term, {})
            for docId, tf in posting.items():
                w = (1.0 + math.log10(tf)) * idf
                wt[docId] = w
                sqNorm[docId] = sqNorm.get(docId, 0.0) + w * w

        norms = {docId: math.sqrt(s) or 1.0 for docId, s in sqNorm.items()}

        # 3) normalize -> inverted postings and forward doc vectors
        self.postings = {}
        self.docVectors = {docId: {} for docId in range(n)}
        for term, wt in weighted.items():
            post = self.postings.setdefault(term, {})
            for docId, w in wt.items():
                wn = w / norms[docId]
                post[docId] = wn
                self.docVectors[docId][term] = wn
        return self

    
    def vectorizeQuery(self, terms: Iterable[str]) -> dict[str, float]:
        tf = Counter(t for t in terms if t in self.idf)
        if not tf:
            return {}
        vec = {t: (1.0 + math.log10(c)) * self.idf[t] for t, c in tf.items()}
        norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
        return {t: w / norm for t, w in vec.items()}

    
    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "meta": {"N": self.N, "weighting": "ltc.ltc", "created": time.time()},
            "documents": [asdict(d) for d in self.documents],
            "df": self.df,
            # JSON object keys must be strings; doc ids are restored to int on load.
            "postings": {t: {str(d): tf for d, tf in p.items()} for t, p in self._rawPostings.items()},
        }
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(payload, fh)

    @classmethod
    def load(cls, path: Path | str) -> "Index":
        """Load an index previously written by :meth:`save` and finalize it."""
        with gzip.open(Path(path), "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        idx = cls()
        idx.documents = [DocMeta(**d) for d in payload["documents"]]
        idx.df = payload["df"]
        idx._rawPostings = {
            t: {int(d): tf for d, tf in p.items()} for t, p in payload["postings"].items()
        }
        return idx.finalize()


def iterCorpusFiles(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in parsers.SUPPORTED_EXTENSIONS:
            yield path


def buildIndex(root: Path | str, *, doPrints: bool = False, progressEvery: int = 200) -> Index:
    """Build an :class:`Index` from every supported file under ``root``."""
    root = Path(root)
    idx = Index()
    numSeen = 0
    for path in iterCorpusFiles(root):
        text = parsers.extractText(path)
        terms = analyze(text)
        if not terms:
            continue  #skip unreadable/empty/image-only (PDF) 
        idx.addDocument(
            path=str(path),
            category=parsers.fileCategory(path),
            title=path.stem.replace("_", " "),
            terms=terms,
        )
        numSeen += 1
        if doPrints and numSeen % progressEvery == 0:
            print(f"  indexed {numSeen} documents...")
    if doPrints:
        print(f"  indexed {numSeen} documents, {len(idx.df)} unique terms")
    return idx.finalize()
