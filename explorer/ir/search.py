"""High-level search orchestration.

Ties the pieces together into a single call and exposes the two advanced
components as independent on/off switches so the four ablation variants

    baseline            (no PRF, no boost)
    + boost only
    + PRF only
    + PRF and boost     (full system)

are produced by the *same* code path with different flags -- there is no
separate "baseline implementation", which keeps the comparison honest.

Pipeline:
    1. analyze + vectorize the query            (basic model)
    2. classify query intent                    (advanced: intent)
    3. initial cosine ranking
    4. if PRF:  Rocchio-expand using the top-k of the *initial* ranking, re-score
    5. if boost: multiply scores by the intent-conditioned file-type matrix
    6. sort, return top results
"""
from __future__ import annotations

from explorer.ir import intent as intentMod
from explorer.ir import rank
from explorer.ir.index import Index
from explorer.ir.preprocess import analyze
from explorer.ir.rank import SearchParams, SearchResult


def search(index: Index, query: str, *, usePrf: bool = False, useBoost: bool = False, params: SearchParams | None = None, topN: int = 10) -> list[SearchResult]:
    params = params or SearchParams()

    qvec = index.vectorizeQuery(analyze(query))
    if not qvec:
        return []

    queryIntent = intentMod.classify(query)

    #initial ranking
    scores = rank.cosineScores(index, qvec)

    #pseudo-relevance feedback, re-using the initial ranking to pick the top-k docs
    if usePrf:
        initialOrder = sorted(scores, key=lambda d: scores[d], reverse=True)
        qvec = rank.rocchioExpand(index, qvec, initialOrder, params)
        scores = rank.cosineScores(index, qvec)

    #query-conditioned file-type boost
    if useBoost:
        scores = rank.applyBoost(scores, index, queryIntent, params)

    #rank 
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:topN]
    results: list[SearchResult] = []
    for docId, score in ordered:
        meta = index.documents[docId]
        results.append(
            SearchResult(
                docId=docId, score=score, title=meta.title,
                path=meta.path, category=meta.category,
            )
        )
    return results


def rankedDocIds(index: Index, query: str, *, usePrf: bool = False, useBoost: bool = False, params: SearchParams | None = None, cutoff: int = 100) -> list[int]:
    results = search(
        index, query, usePrf=usePrf, useBoost=useBoost,
        params=params, topN=cutoff,
    )
    return [r.docId for r in results]
