from __future__ import annotations

from dataclasses import dataclass, field

from explorer.ir.index import Index
from explorer.ir.parsers import CATEGORIES


DEFAULT_BOOST: dict[str, dict[str, float]] = {
    "code":    {"code": 1.60, "notebook": 1.40, "markdown": 1.10, "text": 0.85, "html": 0.85, "pdf": 0.90},
    "prose":   {"code": 0.70, "notebook": 0.90, "markdown": 1.10, "text": 1.30, "html": 1.20, "pdf": 1.30},
    "neutral": {cat: 1.0 for cat in CATEGORIES},
}


@dataclass
class SearchParams:
    """Tunable hyper-parameters for a search (the targets of the grid search)."""

    #rocchio PRF
    prfK: int = 10            #number of top docs assumed relevant
    prfAlpha: float = 1.0     #weight kept on the original query
    prfBeta: float = 0.75     #weight given to the relevant centroid
    prfTerms: int = 0         #if > 0, keep only this many heaviest expansion terms

    #file-type boost
    boostGamma: float = 1.0   #exponent applied to the boost matrix (0 = false)
    boostMatrix: dict[str, dict[str, float]] = field(
        default_factory=lambda: {k: dict(v) for k, v in DEFAULT_BOOST.items()}
    )


@dataclass
class SearchResult:
    docId: int
    score: float
    title: str
    path: str
    category: str


def cosineScores(index: Index, qvec: dict[str, float]) -> dict[int, float]:
    scores: dict[int, float] = {}
    for term, wq in qvec.items():
        for docId, wd in index.postings.get(term, {}).items():
            scores[docId] = scores.get(docId, 0.0) + wq * wd
    return scores


#File-type boost
def applyBoost(scores: dict[int, float], index: Index, intent: str, params: SearchParams) -> dict[int, float]:

    if params.boostGamma == 0:
        return scores
    matrix = params.boostMatrix.get(intent, {})
    boosted: dict[int, float] = {}
    for docId, s in scores.items():
        mult = matrix.get(index.documents[docId].category, 1.0)
        boosted[docId] = s * (mult ** params.boostGamma)
    return boosted



#Rocchio pseudo-relevance feedback
def rocchioExpand(index: Index, qvec: dict[str, float],rankedDocIds: list[int], params: SearchParams) -> dict[str, float]:

    top = rankedDocIds[: params.prfK]
    if not top:
        return qvec

    newVec: dict[str, float] = {t: params.prfAlpha * w for t, w in qvec.items()}
    coeff = params.prfBeta / len(top)
    for docId in top:
        for term, wd in index.docVectors[docId].items():
            newVec[term] = newVec.get(term, 0.0) + coeff * wd

    if params.prfTerms and len(newVec) > params.prfTerms:
        kept = sorted(newVec.items(), key=lambda kv: kv[1], reverse=True)[: params.prfTerms]
        newVec = dict(kept)

    norm = sum(w * w for w in newVec.values()) ** 0.5 or 1.0
    return {t: w / norm for t, w in newVec.items()}
