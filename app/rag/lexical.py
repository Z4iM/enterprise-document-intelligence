"""Small-corpus BM25; normalization never changes persisted source quotations."""

import math
import re
import unicodedata
from collections import Counter

ARABIC = re.compile(r"[\u0621-\u064a]")
STOP = frozenset(
    [
        "a",
        "an",
        "the",
        "is",
        "are",
        "of",
        "to",
        "for",
        "in",
        "on",
        "and",
        "or",
        "with",
        "what",
        "when",
        "which",
        "how",
        "do",
        "does",
        "can",
        "must",
        "be",
        "all",
        "i",
        "my",
        "we",
        "our",
        "this",
        "that",
        "at",
        "it",
        "from",
        "by",
        "as",
        "not",
        "if",
        "في",
        "من",
        "على",
        "إلى",
        "الى",
        "عن",
        "هل",
        "ما",
        "متى",
        "كيف",
        "أو",
        "او",
        "و",
        "لا",
        "أن",
        "ان",
        "يتم",
        "يجب",
        "هذا",
        "هذه",
        "عند",
        "كل",
        "التي",
        "الذي",
        "مع",
        "هو",
        "هي",
    ]
)
TRANSLATE = str.maketrans("أإآٱى٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "ااااي01234567890123456789")


def tokens(text: str) -> list[str]:
    normalized = "".join(
        c
        for c in unicodedata.normalize("NFKC", text.casefold())
        if not unicodedata.combining(c) and c != "ـ"
    ).translate(TRANSLATE)
    result = []
    for token in re.findall(r"[^\W_]+", normalized, re.UNICODE):
        if token in STOP or len(token) < 2:
            continue
        if ARABIC.search(token):
            # Conservative article normalization only; retain original text for citations.
            if token.startswith("وال") and len(token) > 5:
                token = token[3:]
            elif token.startswith("ال") and len(token) > 4:
                token = token[2:]
        elif token.endswith("s") and len(token) > 4 and not token.endswith("ss"):
            token = token[:-1]
        result.append(token)
    return result


def bm25(query: str, texts: list[str]) -> list[float]:
    documents = [Counter(tokens(text)) for text in texts]
    if not documents:
        return []
    average = sum(sum(doc.values()) for doc in documents) / len(documents) or 1
    terms = set(tokens(query))
    df = {term: sum(term in doc for doc in documents) for term in terms}
    scores = []
    for document in documents:
        length = sum(document.values())
        score = 0.0
        for term in terms:
            tf = document[term]
            idf = math.log(1 + (len(documents) - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / average))
        scores.append(score)
    return scores
