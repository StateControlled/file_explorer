# evaluation: corpus stats, 2x2 ablation, grid search, qualitative cases.
# Run with:
#     python -m evaluation.evaluate --corpus data/corpus
# What it does
# ------------
# 1.  Builds (and caches) the index over the downloaded corpus.
# 2.  Turns the provenance 'manifest.json' into binary relevance judgements
#     (qrels): a document is relevant to a query iff its provenance theme is one
#     of the query's relevant themes.
# 3.  Runs the four ablation variants (baseline / +boost / +PRF / full) and reports
#     P@10, MAP and NDCG@10 -- the 2x2 table the brief asks for.
# 4.  Grid-searches the hyper-parameters (PRF k, PRF beta, boost gamma) and reports
#     the effect of each, plus the best configuration.
# 5.  Saves everything to 'data/eval_results.json' for the write-up and prints
#     qualitative success/failure examples.

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from explorer.ir import intent as intent_mod
from explorer.ir.index import Index, buildIndex
from explorer.ir.preprocess import analyze
from explorer.ir.rank import SearchParams
from explorer.ir.search import rankedDocIds, search
from evaluation import metrics
from evaluation.queries import QUERIES, Query

CUTOFF = 100   # depth at which rankings are scored (MAP@100 etc.)
K = 10         # cutoff for P@k / NDCG@k


# ---------------------------------------------------------------------------
# Corpus / index / qrels
# ---------------------------------------------------------------------------
def load_index(corpus_dir: Path, *, rebuild: bool = False) -> Index:
    cache = corpus_dir.parent / "eval_index.json.gz"
    if cache.exists() and not rebuild:
        print(f"Loading cached index from {cache}")
        return Index.load(cache)
    print(f"Building index over {corpus_dir} ...")
    t = time.time()
    idx = buildIndex(corpus_dir, doPrints=True)
    idx.save(cache)
    print(f"Indexed {idx.N} docs in {time.time() - t:.1f}s (cached to {cache})")
    return idx


def load_theme_map(corpus_dir: Path, index: Index) -> dict[str, set[int]]:
    """Map each theme -> set of document ids, joining manifest provenance to the index."""
    records = json.loads((corpus_dir / "manifest.json").read_text())
    path_to_theme = {str(Path(r["path"]).resolve()): r["theme"] for r in records}
    theme_to_docs: dict[str, set[int]] = {}
    matched = 0
    for doc in index.documents:
        theme = path_to_theme.get(str(Path(doc.path).resolve()))
        if theme is None:
            continue
        theme_to_docs.setdefault(theme, set()).add(doc.id)
        matched += 1
    print(f"Joined {matched}/{index.N} indexed docs to provenance themes "
          f"({len(theme_to_docs)} themes)")
    return theme_to_docs


def qrels_for(query: Query, theme_to_docs: dict[str, set[int]]) -> set[int]:
    rel: set[int] = set()
    for theme in query.themes:
        rel |= theme_to_docs.get(theme, set())
    return rel


# ---------------------------------------------------------------------------
# Scoring a configuration across all queries
# ---------------------------------------------------------------------------
def score_config(
    index: Index, theme_to_docs: dict[str, set[int]],
    *, use_prf: bool, use_boost: bool, params: SearchParams,
) -> dict[str, float]:
    per_query = []
    for q in QUERIES:
        relevant = qrels_for(q, theme_to_docs)
        if not relevant:
            continue
        ranked = rankedDocIds(index, q.text, usePrf=use_prf,
                              useBoost=use_boost, params=params, cutoff=CUTOFF)
        per_query.append(metrics.evaluate_query(ranked, relevant, k=K))
    return metrics.mean_metrics(per_query)


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------
def run_ablation(index: Index, theme_to_docs: dict[str, set[int]], params: SearchParams) -> dict:
    variants = {
        "baseline":      dict(use_prf=False, use_boost=False),
        "boost_only":    dict(use_prf=False, use_boost=True),
        "prf_only":      dict(use_prf=True,  use_boost=False),
        "full":          dict(use_prf=True,  use_boost=True),
    }
    return {name: score_config(index, theme_to_docs, params=params, **flags)
            for name, flags in variants.items()}


def grid_search(index: Index, theme_to_docs: dict[str, set[int]]) -> dict:
    """Grid-search PRF and boost hyper-parameters; also produce 1-D sweeps."""
    prf_ks = [5, 10, 15, 20]
    betas = [0.25, 0.5, 0.75, 1.0]
    gammas = [0.0, 0.5, 1.0, 1.5, 2.0]

    best = None
    full_grid = []
    for k in prf_ks:
        for beta in betas:
            for gamma in gammas:
                p = SearchParams(prfK=k, prfBeta=beta, boostGamma=gamma)
                use_prf = beta > 0
                use_boost = gamma > 0
                m = score_config(index, theme_to_docs, use_prf=use_prf,
                                 use_boost=use_boost, params=p)
                row = {"prf_k": k, "prf_beta": beta, "boost_gamma": gamma, **m}
                full_grid.append(row)
                if best is None or m["MAP"] > best["MAP"]:
                    best = row

    # 1-D sweeps (hold the others at their defaults) for the report figures.
    def sweep(param: str, values: list) -> list[dict]:
        out = []
        for v in values:
            kw = dict(prf_k=10, prf_beta=0.75, boost_gamma=1.0)
            kw[param] = v
            p = SearchParams(prfK=kw["prf_k"], prfBeta=kw["prf_beta"], boostGamma=kw["boost_gamma"])
            m = score_config(index, theme_to_docs, use_prf=kw["prf_beta"] > 0,
                             use_boost=kw["boost_gamma"] > 0, params=p)
            out.append({param: v, **m})
        return out

    return {
        "best": best,
        "sweeps": {
            "prf_k": sweep("prf_k", prf_ks),
            "prf_beta": sweep("prf_beta", betas),
            "boost_gamma": sweep("boost_gamma", gammas),
        },
        "full_grid": full_grid,
    }


def intent_report() -> dict:
    """Accuracy of the rule-based intent classifier vs. the expected labels."""
    correct = 0
    confusion: dict[str, Counter] = {}
    for q in QUERIES:
        pred = intent_mod.classify(q.text)
        confusion.setdefault(q.expected_intent, Counter())[pred] += 1
        correct += int(pred == q.expected_intent)
    return {
        "accuracy": correct / len(QUERIES),
        "confusion": {k: dict(v) for k, v in confusion.items()},
    }


def corpus_stats(index: Index, theme_to_docs: dict[str, set[int]]) -> dict:
    by_cat = Counter(d.category for d in index.documents)
    return {
        "n_documents": index.N,
        "n_terms": len(index.df),
        "by_category": dict(by_cat),
        "by_theme": {t: len(s) for t, s in sorted(theme_to_docs.items())},
    }


def qualitative(index: Index, theme_to_docs: dict[str, set[int]],
                params: SearchParams, query_ids: list[str]) -> list[dict]:
    """Show top-5 results for selected queries, baseline vs full system."""
    by_id = {q.id: q for q in QUERIES}
    out = []
    for qid in query_ids:
        q = by_id[qid]
        relevant = qrels_for(q, theme_to_docs)
        entry = {"id": q.id, "text": q.text,
                 "intent": intent_mod.classify(q.text),
                 "n_relevant": len(relevant)}
        for tag, prf, boost in [("baseline", False, False), ("full", True, True)]:
            entry[tag] = [
                {"title": r.title[:48], "category": r.category,
                 "score": round(r.score, 4), "relevant": r.docId in relevant}
                for r in res
            ]
            ]
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------
def _fmt_table(ablation: dict) -> str:
    order = ["baseline", "boost_only", "prf_only", "full"]
    label = {"baseline": "Baseline TF-IDF", "boost_only": "+ File-type boost",
             "prf_only": "+ PRF", "full": "Full (PRF + boost)"}
    lines = [f"  {'Variant':22s} {'P@10':>7s} {'MAP':>7s} {'NDCG@10':>8s}"]
    for name in order:
        m = ablation[name]
        lines.append(f"  {label[name]:22s} {m['P@10']:7.4f} {m['MAP']:7.4f} {m['NDCG@10']:8.4f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the IR system.")
    ap.add_argument("--corpus", default="data/corpus", help="Corpus directory (with manifest.json)")
    ap.add_argument("--rebuild", action="store_true", help="Rebuild the index even if cached")
    ap.add_argument("--out", default="data/eval_results.json", help="Where to write results JSON")
    ap.add_argument("--no-grid", action="store_true", help="Skip the (slower) grid search")
    args = ap.parse_args(argv)

    corpus_dir = Path(args.corpus)
    index = load_index(corpus_dir, rebuild=args.rebuild)
    theme_to_docs = load_theme_map(corpus_dir, index)
    default_params = SearchParams()

    stats = corpus_stats(index, theme_to_docs)
    print("\n=== Corpus ===")
    print(f"  {stats['n_documents']} documents, {stats['n_terms']} unique terms")
    print(f"  by file category: {stats['by_category']}")

    print("\n=== 2x2 Ablation (default hyper-parameters) ===")
    ablation = run_ablation(index, theme_to_docs, default_params)
    print(_fmt_table(ablation))

    intent = intent_report()
    print(f"\n=== Intent classifier ===\n  accuracy = {intent['accuracy']:.3f}")

    grid = None
    if not args.no_grid:
        print("\n=== Grid search (this takes a bit) ===")
        grid = grid_search(index, theme_to_docs)
        b = grid["best"]
        print(f"  best by MAP: prf_k={b['prf_k']} prf_beta={b['prf_beta']} "
              f"boost_gamma={b['boost_gamma']} -> "
              f"P@10={b['P@10']:.4f} MAP={b['MAP']:.4f} NDCG@10={b['NDCG@10']:.4f}")

    qual = qualitative(index, theme_to_docs, default_params,
                       ["q01", "q13", "q20", "q28"])

    results = {
        "config": {"cutoff": CUTOFF, "k": K, "n_queries": len(QUERIES)},
        "corpus": stats,
        "ablation": ablation,
        "intent": intent,
        "grid_search": grid,
        "qualitative": qual,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
