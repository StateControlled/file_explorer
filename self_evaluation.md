# Self-Evaluation — Content-Based Local File Search

**Team *Can't Recall*: William Berthouex, Noah Sleeman**
CSC 575 — Final Project

> Draft to convert to `self_evaluation.pdf`. **Fill in the real per-member
> contribution split in §2** — only the two of you know who did what; the text
> below is a starting point, not a record.

## 1. How the project fulfills each evaluation criterion

**Code submission.** A complete, runnable prototype is included. The search
engine runs with `python -m explorer index <dir>` followed by
`python -m explorer search "<query>" [--prf] [--boost]`. The corpus downloader
(`python -m corpus.build_corpus`) and the evaluation harness
(`python -m evaluation.evaluate`) are also runnable.

**Code documentation.** The `README.md` gives setup, a quick start, every
command and flag, the dataset instructions, an architecture diagram, the results,
and the project layout. Every module carries a docstring explaining its role and
the IIR technique it implements, and non-obvious steps (e.g. the `ltc` weighting,
the boost matrix, the Rocchio update) are commented inline.

**Usage of basic IIR techniques.** Tokenization, stopword removal, Porter
stemming, an inverted index, TF-IDF (`ltc`) weighting, cosine similarity ranking,
and the standard evaluation metrics (P@k, MAP, NDCG@k). The index, weighting,
cosine and metrics are our own code; stemming uses NLTK's Porter stemmer.

**Usage of advanced IIR techniques.** Two advanced components on top of the
baseline, both written by us: (1) a query-intent classifier driving a
query-conditioned file-type boost, and (2) Rocchio pseudo-relevance feedback.
Both are independently toggleable, and a 2×2 ablation quantifies each one's
contribution.

**Model complexity.** The retrieval algorithms are our own code: the inverted
index, TF-IDF weighting, cosine ranking, the intent classifier, the file-type
boost, the Rocchio feedback loop, and all evaluation metrics. We use established
libraries only for routine, non-IR plumbing: `nltk` for Porter stemming and
`BeautifulSoup`/`pypdf` for HTML/PDF text extraction (`typer`/`rich` for the CLI,
`matplotlib` for figures). In other words, the parts that *are* information
retrieval are implemented from scratch; the parts that are file/format handling
reuse standard tools.

**Usage of good data.** A heterogeneous corpus of 650 indexed documents (67,610
unique terms) across six file categories (code, text, notebook, html, pdf),
collected from public sources (Gutenberg, Wikipedia, arXiv, GitHub) — far larger
than the assignment examples but runnable on one laptop. A manifest records each
document's provenance, which doubles as the relevance labels for evaluation.

**Good experiments and evaluation.** We report P@10, MAP, and NDCG@10 over 28
queries; run the full 2×2 ablation; and grid-search the hyper-parameters
(`prf_k`, `beta`, `gamma`), reporting both the best configuration and
one-dimensional sweeps showing each parameter's effect. We include qualitative
success and failure cases, including an honest PRF query-drift failure (q20).

**Project objectives (as revised with instructor feedback).** We dropped the
manually-compiled corpus, the GUI stretch goal, and live-user-feedback
evaluation, and instead delivered: a public multi-file-type corpus; the two
concrete advanced features the instructor asked for (file-type relevance via
query-conditioned boosting, and reproducible feedback via Rocchio PRF); and a
2×2 ablation evaluated with P@10/MAP/NDCG@10. The objective that "different file
types may be more or less relevant depending on the query" is operationalized by
the intent classifier + boost and measured directly.

## 2. Team member contributions

> Replace the bracketed text with the actual split.

**Noah Sleeman** — [e.g., file-explorer CLI foundation and `index`/`search`
command wiring; corpus builder (sources, manifest); … ].

**William Berthouex** — [e.g., retrieval core (inverted index, TF-IDF, cosine);
advanced features (intent classifier, boost, Rocchio PRF); … ].

**Shared** — evaluation design (queries, qrels methodology, metrics), the report,
and the presentation.

## 3. Evidence pointers

- Basic IIR: `explorer/ir/preprocess.py`, `explorer/ir/index.py`,
  `explorer/ir/rank.py` (`cosine_scores`).
- Advanced IIR: `explorer/ir/intent.py`, `explorer/ir/rank.py`
  (`apply_boost`, `rocchio_expand`), `explorer/ir/search.py`.
- Experiments: `evaluation/` and `data/eval_results.json`; figures in
  `report/figures/`.

## 4. Use of AI

> Confirm this matches your course's AI policy and edit to reflect your actual
> usage before submitting.

The one-time data-collection script (`corpus/build_corpus.py`) was written with
the help of an AI coding assistant; it downloads and labels public documents and
is not part of the information-retrieval system. We disclose this for
transparency. The retrieval components that the project is graded on — the
inverted index, TF-IDF weighting, cosine ranking, intent classifier, file-type
boost, Rocchio feedback and evaluation metrics — are our own work, which we
understand and can explain.
