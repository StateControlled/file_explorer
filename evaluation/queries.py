# Test queries with provenance-based relevance labels.

# Each query lists the corpus themes whose documents are considered relevant.
# Themes come from the corpus manifest written by 'corpus/build_corpus.py' and are
# derived from a document's source, not its text. so judging retrieval against
# them does not simply reward the ranker for matching the words it indexed.

# 'expected_intent' records the intent we expect the rule-based classifier to
# assign; it is used only for analysis/reporting, not for scoring.

# The set is deliberately balanced across three situations:
#   * prose-intent queries whose relevant docs are mostly prose/PDF/HTML,
#   * code-intent queries whose relevant docs are mostly source/notebooks,
#   * neutral/mixed queries whose relevant docs span several file types,
# so that the file-type boost can both help and (honestly) sometimes hurt.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Query:
    id: str
    text: str
    themes: tuple[str, ...]
    expected_intent: str  # "code" | "prose" | "neutral" -- for analysis only


QUERIES: list[Query] = [
    # ---- prose-intent: explanatory questions, relevant docs are prose ----
    Query("q01", "what is cryptography and how does encryption work", ("cryptography",), "prose"),
    Query("q02", "how does the human immune system fight infection", ("medicine",), "prose"),
    Query("q03", "what is a volcano and how do volcanoes form", ("geology",), "prose"),
    Query("q04", "explain the solar system and the planets", ("astronomy",), "prose"),
    Query("q05", "what is macroeconomics and what causes inflation", ("economics",), "prose"),
    Query("q06", "history of the ancient roman empire", ("history",), "prose"),
    Query("q07", "what is cell biology and genetics", ("biology",), "prose"),
    Query("q08", "what is epistemology in philosophy", ("philosophy",), "prose"),
    Query("q09", "explain chemical reactions and bonding", ("chemistry",), "prose"),
    Query("q10", "what is music theory and harmony", ("music",), "prose"),
    Query("q11", "classic english literature novels and stories", ("literature",), "prose"),
    Query("q12", "what is natural selection and evolution", ("science",), "prose"),

    # ---- code-intent: code-flavoured wording, relevant docs are code ----
    Query("q13", "flask web framework route function blueprint", ("web_framework",), "code"),
    Query("q14", "python requests http session class get post", ("http_library",), "code"),
    Query("q15", "json parse serialize object class template", ("json_parsing",), "code"),
    Query("q16", "import pandas dataframe data science notebook", ("data_science",), "code"),
    Query("q17", "scikit-learn estimator fit predict method", ("machine_learning",), "code"),
    Query("q18", "sql parser tokenizer abstract syntax tree", ("databases",), "code"),
    Query("q19", "operating system memory allocation pointer malloc", ("operating_systems",), "code"),

    # ---- neutral / mixed: relevant docs span multiple file types ----
    Query("q20", "machine learning neural networks", ("machine_learning",), "neutral"),
    Query("q21", "information retrieval search engine ranking", ("information_retrieval",), "neutral"),
    Query("q22", "database management systems and indexing", ("databases",), "neutral"),
    Query("q23", "operating system process scheduling", ("operating_systems",), "neutral"),
    Query("q24", "natural language processing language models", ("nlp",), "neutral"),
    Query("q25", "computer vision image recognition", ("computer_vision",), "neutral"),
    Query("q26", "sorting algorithms and computational complexity", ("algorithms",), "neutral"),
    Query("q27", "distributed systems consensus and replication", ("distributed_systems",), "neutral"),
    Query("q28", "deep learning for data science", ("machine_learning", "data_science"), "neutral"),
]
