# CSC575 Intelligent Information Retrieval — Final Project

**A content-based local file search engine**
William Berthouex · Noah Sleeman · Team *Can't Recall*

A command-line tool that indexes a directory of heterogeneous files (prose,
web pages, PDFs, source code, Jupyter notebooks) and retrieves the most relevant
ones for a free-text query using a vector-space model. On top of the classic
TF-IDF / cosine baseline it adds two advanced components — **query-conditioned
file-type boosting** and **Rocchio pseudo-relevance feedback** — each of which
can be toggled independently so their contribution can be measured.

The **core retrieval algorithms** — the inverted index, TF-IDF weighting, cosine
similarity, the query-intent classifier, the file-type boost, the Rocchio
feedback loop and the evaluation metrics — are implemented from scratch.
Standard libraries are used only for routine text handling: `nltk` for Porter
stemming, `BeautifulSoup` for stripping HTML, and `pypdf` for extracting text
from PDFs.

---

## 1. Setup

```bash
python -m pip install -r requirements.txt
```

Requires **Python 3.12+** (the code uses modern f-string syntax). No virtual
environment is bundled.

---

## 2. Quick start

```bash
# 1. Build the corpus from public sources (see §4), or use any folder you like
python -m corpus.build_corpus --out data/corpus

# 2. Build the search index over it
python -m explorer index data/corpus

# 3. Search
python -m explorer search "what is cryptography and how does encryption work"
python -m explorer search "flask web framework route function" --boost
python -m explorer search "machine learning neural networks" --prf --boost
```

`index` works on any directory — point it at your own folder of files.

---

## 3. Usage

Run the application with `python -m explorer`. It is both an interactive file
explorer (its original purpose) and a search engine.

### Global options

| Option            | Description                        |
|-------------------|------------------------------------|
| `--version` `-v`  | Display version information        |
| `--about` `-a`    | Display more detailed information  |
| `--help`          | Show the list of commands          |

### Commands

| Command        | Description                                                    |
|----------------|---------------------------------------------------------------|
| `cfg`          | Print the current configuration                               |
| `loc`          | Print the paths to saved data                                 |
| `return-cwd`   | Return the working directory to its original point            |
| `ls`           | List directory contents                                       |
| `open`         | Open a text file in the console                                |
| `cd`           | Change the current working directory                          |
| **`index`**    | **Build the search index over a directory of documents**      |
| **`search`**   | **Search the indexed documents for a query**                  |

### `index`

```
python -m explorer index [ROOT] [--out PATH]
```
Crawls `ROOT` (default: current directory) for every supported file, builds the
inverted index and TF-IDF vectors, and saves them (default: the application data
directory). Supported extensions: `.txt .md .rst .html .htm .pdf .ipynb` and
source code (`.py .java .c .h .cpp .cc .hpp .cs .js .ts .go .rs .rkt .hs`).

### `search`

```
python -m explorer search "QUERY" [--prf] [--boost] [-n N] [--index PATH]
```

| Flag            | Effect                                                            |
|-----------------|------------------------------------------------------------------|
| `--prf`         | Enable Rocchio pseudo-relevance feedback                         |
| `--boost`       | Enable query-conditioned file-type boosting                     |
| `-n`, `--num`   | Number of results to display (default 10)                       |
| `-i`, `--index` | Use a specific index file                                       |

With neither flag the system is the **baseline** TF-IDF cosine ranker; the two
flags add the two advanced components, which is exactly the 2×2 ablation used in
the evaluation (§6).

---

## 4. Dataset

The corpus is assembled from **public sources** by
[`corpus/build_corpus.py`](corpus/build_corpus.py), so it is reproducible and is
*not* committed to this repository (the submission stays lightweight).

```bash
python -m corpus.build_corpus --out data/corpus            # ~45-70 MB
python -m corpus.build_corpus --out data/corpus --scale 0.5   # smaller/faster
python -m corpus.build_corpus --only wikipedia,gutenberg   # a subset of sources
```

| Source            | File types          | What we gathered                                  |
|-------------------|---------------------|---------------------------------------------------|
| Project Gutenberg | `.txt`              | public-domain books (literature, philosophy, science) |
| Wikipedia         | `.html`, `.txt`     | articles across ~18 topics (ML, cryptography, biology, …) |
| arXiv             | `.pdf`              | recent CS papers (cs.IR, cs.LG, cs.CR, cs.DB, …)  |
| GitHub repos      | `.py .java .cpp .h .rs` | source files from Flask, requests, nlohmann/json, gson, scikit-learn, sqlparser-rs, CPython |
| GitHub notebooks  | `.ipynb`            | notebooks from data-science / ML repos (outputs stripped) |

> **AI-use disclosure:** `corpus/build_corpus.py` is a one-time data-collection
> utility (it is *not* part of the IR system) and was written with the help of an
> AI coding assistant. It is included for transparency and reproducibility.

Each file is catalogued in `data/corpus/manifest.json` with a `theme` label
derived from **where it came from** (not its text). The evaluation uses those
provenance labels as relevance judgements, so scoring does not simply reward the
ranker for matching indexed words. Several themes (`machine_learning`,
`cryptography`, `databases`, …) span multiple sources and file types on purpose,
so that "which file type is relevant for this query" is genuinely testable.

<!-- CORPUS_STATS -->
The corpus used for the reported results contains **709 files**, of which **650**
held extractable text and were indexed (the rest were empty/scanned PDFs or
near-empty source files), giving **67,610 unique terms**:

| File category | Documents |
|---------------|-----------|
| code (`.py .java .cpp .h .c .rs`) | 359 |
| text (`.txt`)                     | 158 |
| notebook (`.ipynb`)               | 77  |
| html (`.html`)                    | 36  |
| pdf (`.pdf`)                      | 20  |
| **total**                         | **650** |

> **Dataset access:** the exact ~45 MB corpus is shared here:
> `‹ADD GOOGLE-DRIVE/ONEDRIVE LINK›`. Download and unzip it to `data/corpus/`
> (so that `data/corpus/manifest.json` exists), then run §2.

---

## 5. How it works

```
            query                                   documents (mixed file types)
              │                                              │
       ┌──────▼───────┐                          ┌───────────▼───────────┐
       │ analyze:     │                          │ parsers:              │
       │ tokenize →   │                          │ html/ipynb/pdf/code → │
       │ stopword →   │                          │ plain text            │
       │ Porter stem  │                          └───────────┬───────────┘
       └──────┬───────┘                                      │ analyze
              │ query vector (ltc, L2-normalized)            ▼
              │                              inverted index + TF-IDF doc vectors
              │                                              │
       ┌──────▼──────────────────────────────────────────────▼─────────┐
       │ 1. cosine similarity ranking                                   │
       │ 2. [--prf]   Rocchio: move query toward top-k centroid, re-rank│
       │ 3. [--boost] multiply scores by boost[intent][file-type]       │
       └───────────────────────────────┬───────────────────────────────┘
                                        ▼
                                 ranked results
```

* **Preprocessing** (`explorer/ir/preprocess.py`) — tokenization, stopword
  removal and Porter stemming (NLTK), applied identically to documents and
  queries.
* **Indexing** (`explorer/ir/index.py`) — an inverted index plus cosine-
  normalized TF-IDF document vectors (SMART `ltc`). With both sides normalized,
  cosine similarity is a dot product.
* **Intent classifier** (`explorer/ir/intent.py`) — a transparent rule-based
  classifier labelling each query `code`, `prose` or `neutral`.
* **File-type boost** (`explorer/ir/rank.py`) — multiplies each document's score
  by a factor depending on (query intent × file category); the concrete answer
  to "what makes a file *type* relevant to a query".
* **Rocchio PRF** (`explorer/ir/rank.py`) — assumes the top-k results are
  relevant, moves the query vector toward their centroid, and re-ranks.

---

## 6. Evaluation

```bash
python -m evaluation.evaluate --corpus data/corpus
```

This builds qrels from the manifest, runs the four ablation variants over the
test queries in [`evaluation/queries.py`](evaluation/queries.py), grid-searches
the hyper-parameters, and writes `data/eval_results.json`. Metrics: **P@10,
MAP, NDCG@10**.

<!-- RESULTS_TABLE -->
2×2 ablation over 28 queries (default hyper-parameters):

| Variant              | P@10   | MAP    | NDCG@10 |
|----------------------|--------|--------|---------|
| Baseline TF-IDF      | 0.7250 | 0.6044 | 0.7618  |
| + File-type boost    | 0.7393 | 0.6089 | 0.7728  |
| + PRF                | 0.7571 | 0.6329 | 0.7758  |
| Full (PRF + boost)   | 0.7607 | 0.6342 | 0.7833  |

Grid search best (prf_k=5, β=0.5, γ=2.0): **P@10 0.7893, MAP 0.6382, NDCG@10
0.8011**. Both components improve every metric; PRF is the larger contributor and
the file-type boost adds a smaller, consistent gain. The rule-based intent
classifier matches the expected label on 27/28 queries (96.4%).

---

## 7. Project layout

```
explorer/            file-explorer CLI + IR engine
  ir/
    preprocess.py    tokenizer, stopwords, stemming (NLTK)
    parsers.py       per-file-type text extraction (bs4, pypdf)
    index.py         inverted index + TF-IDF (+ persistence)
    intent.py        rule-based query intent classifier
    rank.py          cosine, file-type boost, Rocchio PRF
    search.py        high-level search orchestration
  exp.py             Typer commands (incl. `index`, `search`)
corpus/
  build_corpus.py    one-time public-source corpus downloader (AI-assisted)
evaluation/
  metrics.py         P@k, AP/MAP, NDCG@k
  queries.py         test queries + provenance-based relevance themes
  evaluate.py        ablation + grid search harness
report/
  make_figures.py    builds the report figures from the results
documents/           a few sample text documents
```

## Built With

Python 3.12+ · [Typer](https://typer.tiangolo.com/) (CLI) ·
[Rich](https://rich.readthedocs.io/) (terminal formatting) ·
[NLTK](https://www.nltk.org/) (Porter stemmer) ·
[BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) (HTML) ·
[pypdf](https://pypdf.readthedocs.io/) (PDF text). The index, TF-IDF, cosine
ranking, intent classifier, file-type boost, Rocchio feedback and evaluation
metrics are implemented from scratch.

---

<details>
<summary><strong>Appendix — original proposal &amp; revised roadmap</strong></summary>

### Revised Project Roadmap (incorporating instructor feedback)

Dropped from the proposal: manually compiling a corpus from personal computers,
the GUI stretch goal, and using live user feedback as the main evaluation (not
reproducible). Instead: a public multi-file-type corpus, two concrete advanced
features (query-conditioned file-type boosting and Rocchio pseudo-relevance
feedback), and a 2×2 ablation evaluated with P@10 / MAP / NDCG@10.

|                      | No PRF          | With PRF    |
|----------------------|-----------------|-------------|
| No file-type boost   | baseline TF-IDF | + PRF only  |
| With file-type boost | + boost only    | full system |

### Project Proposal (summary)

Type A project. A file search system that, given a local directory of mixed
document types, returns the most relevant files for a keyword query using an
inverted index with TF-IDF term weighting and cosine ranking, plus document
preprocessing (tokenization, stopword removal, stemming).

References:
- Baeza-Yates, R., & Ribeiro-Neto, B. *Modern Information Retrieval.* Addison-Wesley.
- Soules, C. A. N., & Ganger, G. R. (2005). *Connections: using context to
  enhance file search.* SOSP '05.
- Dinneen, J. D., & Julien, C.-A. (2020). *The ubiquitous digital file: A review
  of file management research.* JASIST, 71.

</details>
