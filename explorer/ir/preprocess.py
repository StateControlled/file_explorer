from __future__ import annotations

import re

from nltk.stem import PorterStemmer

#compact English stopword list. Removing these high-frequency, low-content
#words shrinks the index and stops them from dominating cosine scores.
STOPWORDS: frozenset[str] = frozenset(
    """
    a about above after again against all am an and any are aren't as at be
    because been before being below between both but by can't cannot could
    couldn't did didn't do does doesn't doing don't down during each few for
    from further had hadn't has hasn't have haven't having he her here hers him
    his how i if in into is it its itself let's me more most my no nor not of off
    on once only or other our out over own same she should so some such than that
    the their them then there these they this those through to too under until up
    very was we were what when where which while who whom why with would you your
    """.split()
)

# Tokens are maximal runs of letters/digits/underscore. Keeping the underscore
# means code identifiers such as 'read_save_dat' survive as one token.
_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_MIN_LEN, _MAX_LEN = 2, 40

_stemmer = PorterStemmer()

#regex and to lower
def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())

#lib stemmer
def stem(token: str) -> str:
    return _stemmer.stem(token)

#tokenize -> remove stopwords -> stem
def analyze(text: str, *, removeStopwords: bool = True, doStem: bool = True) -> list[str]:

    terms: list[str] = []
    for tok in tokenize(text):
        if not (_MIN_LEN <= len(tok) <= _MAX_LEN):
            continue
        if removeStopwords and tok in STOPWORDS:
            continue
        terms.append(_stemmer.stem(tok) if doStem else tok)
    return terms
