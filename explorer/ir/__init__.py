"""Information-retrieval engine for the File Explorer search command.

This sub-package implements, from scratch and using only the Python standard
library, the full vector-space retrieval pipeline used by the ``search``
command:

    preprocess  -> tokenization, stopword removal, Porter stemming
    parsers     -> per-file-type text extraction
    index       -> inverted index + TF-IDF document vectors (+ persistence)
    intent      -> rule-based query intent classifier
    rank        -> cosine ranking, query-conditioned file-type boosting, Rocchio PRF
    search      -> high-level orchestration tying the pieces together

The only third-party dependency is ``pypdf`` (used solely to extract text from
``.pdf`` files); every retrieval technique -- the inverted index, TF-IDF
weighting, cosine similarity, the intent classifier, the file-type boost and the
Rocchio pseudo-relevance-feedback loop -- is implemented here directly so that
the basic and advanced IIR techniques are explicit and inspectable.
"""

__all__ = [
    "preprocess",
    "parsers",
    "index",
    "intent",
    "rank",
    "search",
]
