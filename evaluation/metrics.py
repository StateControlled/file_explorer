"""Standard ranked-retrieval evaluation metrics, implemented from scratch.

All three metrics operate on a single ranked list of document ids and a set of
relevant document ids (binary relevance):

    P@k      Precision at cutoff k -- fraction of the top-k that is relevant.
    AP       Average Precision -- mean of the precision values measured at the
             ranks where a relevant document occurs; MAP is the mean of AP over
             a set of queries.
    NDCG@k   Normalized Discounted Cumulative Gain -- rewards placing relevant
             documents near the top, normalized by the ideal ranking.

These are the metrics the project brief asks for (P@10, MAP, NDCG@10).
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def precision_at_k(ranked: Sequence[int], relevant: set[int], k: int) -> float:
    """Precision at cutoff ``k``."""
    if k <= 0:
        return 0.0
    topk = ranked[:k]
    hits = sum(1 for d in topk if d in relevant)
    return hits / k


def average_precision(ranked: Sequence[int], relevant: set[int]) -> float:
    """Average Precision over the full ranked list.

    AP = (1 / R) * sum over relevant docs retrieved of (precision at the rank
    where that doc appears), with R the total number of relevant documents."""
    if not relevant:
        return 0.0
    hits = 0
    summed = 0.0
    for i, doc_id in enumerate(ranked, start=1):
        if doc_id in relevant:
            hits += 1
            summed += hits / i
    return summed / len(relevant)


def ndcg_at_k(ranked: Sequence[int], relevant: set[int], k: int) -> float:
    """Normalized DCG at cutoff ``k`` with binary gains."""
    if not relevant or k <= 0:
        return 0.0
    dcg = 0.0
    for i, doc_id in enumerate(ranked[:k], start=1):
        if doc_id in relevant:
            dcg += 1.0 / math.log2(i + 1)
    # Ideal DCG: as many relevant docs as possible packed at the top.
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_query(ranked: Sequence[int], relevant: set[int], k: int = 10) -> dict[str, float]:
    """Compute P@k, AP and NDCG@k for one query."""
    return {
        f"P@{k}": precision_at_k(ranked, relevant, k),
        "AP": average_precision(ranked, relevant),
        f"NDCG@{k}": ndcg_at_k(ranked, relevant, k),
    }


def mean_metrics(per_query: Iterable[dict[str, float]]) -> dict[str, float]:
    """Average a sequence of per-query metric dicts into mean metrics (MAP etc.)."""
    rows = list(per_query)
    if not rows:
        return {}
    keys = rows[0].keys()
    out = {key: sum(r[key] for r in rows) / len(rows) for key in keys}
    # By convention the mean of AP is reported as MAP.
    if "AP" in out:
        out["MAP"] = out.pop("AP")
    return out
