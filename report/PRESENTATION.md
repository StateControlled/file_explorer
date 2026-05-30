# Presentation Outline & Script (8–10 min video)

Team *Can't Recall* — William Berthouex & Noah Sleeman. One slide per section
below; speaker notes are the rough script. Target ~10 min. The brief says **show
diagrams and results, avoid showing code**, and mention libraries/tools.
Figures are in `report/figures/`.

---

### Slide 1 — Title (≈20s)
**Content-Based Local File Search across Heterogeneous File Types**
William Berthouex · Noah Sleeman · CSC 575.
> "Hi, we're William and Noah, team Can't Recall. Our project is a search engine
> that ranks the files on your computer by how well their content answers a query
> — across prose, web pages, PDFs, source code, and notebooks."

### Slide 2 — The problem & motivation (≈1 min)
- OS file search = filename / exact-substring matching; no content ranking.
- Real folders mix many file types.
- Key insight: **the relevant file type depends on the query** — "what is a
  binary search tree" (wants prose) vs. "binary search tree insert method"
  (wants code).
> Motivate why ranking by content, and type-awareness, is interesting.

### Slide 3 — Data: examples & statistics (≈1 min)
- Show `fig_corpus.png`. 650 indexed docs, ~68k terms, 6 file categories.
- Sources: Gutenberg (.txt), Wikipedia (.html/.txt), arXiv (.pdf), GitHub code
  (.py/.java/.cpp/.h/.rs) and notebooks (.ipynb) — all public, rebuilt by a
  script. Show one example file of each type.
- Queries + relevance from **provenance themes** (where a file came from).
> Explain the corpus is reproducible and the qrels are independent of the ranker.
> Briefly note: the data-collection script was AI-assisted (disclosed); the IR
> system itself is our own work.

### Slide 4 — Queries & matching (≈40s)
- Free-text keyword queries; three intent classes (code / prose / neutral).
- Matching = cosine similarity in a TF-IDF vector space.
> Give 2–3 concrete example queries from each intent class.

### Slide 5 — Methodology / architecture (≈1.5 min)
- Show `fig_architecture.png`.
- Offline: parse → analyze (tokenize, stopword, **Porter stem**) → inverted index
  + cosine-normalized **TF-IDF**.
- Online: same analyzer → cosine ranking → optional **Rocchio PRF** → optional
  **file-type boost**.
- Name the IIR techniques as they appear.
> Walk the diagram left-to-right, top then bottom.

### Slide 6 — Advanced feature 1: query-conditioned file-type boost (≈1 min)
- Rule-based intent classifier (keywords, code punctuation, identifiers vs.
  question phrases). 96.4% accurate on our queries.
- `score' = score · boost[intent][type]^γ`. Promote code/notebooks for code
  intent, prose/pdf for prose intent.
> This is our answer to "what makes a file *type* relevant."

### Slide 7 — Advanced feature 2: Rocchio PRF (≈1 min)
- Assume top-k are relevant; move query toward their centroid; re-rank.
- `q' = α·q + (β/k)·Σ d`. Reproducible, no human in the loop.
> Contrast with the user-feedback idea we dropped after instructor feedback.

### Slide 8 — Implementation (≈45s)
- We wrote the IR components ourselves: inverted index, TF-IDF, cosine, intent
  classifier, file-type boost, Rocchio feedback, and the evaluation metrics.
- Libraries for plumbing only: `nltk` (Porter stemmer), `BeautifulSoup` (HTML),
  `pypdf` (PDF text), `typer`/`rich` (CLI), `matplotlib` (figures).
- Main entry points: `explorer/ir/{index,rank,search}.py`.
> Mention tools, not code listings.

### Slide 9 — Results: 2×2 ablation (≈1 min)
- Show `fig_ablation.png` / Table 1.
- Baseline MAP 0.604 → +PRF 0.633 → full 0.634; P@10 0.725 → 0.761; NDCG 0.762
  → 0.783. PRF is the big win; boost is small but safe.
> State the headline numbers clearly.

### Slide 10 — Results: hyper-parameters + examples (≈1 min)
- Show `fig_sweeps.png`. Best grid config (k=5, β=0.5, γ=2.0) → MAP 0.638.
- Good example: code query → 5/5 code files. **Bad example: q20 "machine learning
  neural networks"** — PRF drifts (4/5 → 3/5) on a broad query.
> Be honest about the failure; it shows understanding.

### Slide 11 — Conclusion (≈40s)
- From-scratch multi-format retrieval works; PRF strongly helps but can drift;
  type-aware boosting is a gentle, reliable gain.
- Future: selective PRF, learned boost weights, graded relevance, live indexing.
> Wrap up with what we learned.

---

**Recording tips (from the brief):** export an actual video file (not a
PowerPoint recording); keep audio audible and consistent; 8–10 min; H.264 if
>400 MB; submit the video + these slides on D2L.
