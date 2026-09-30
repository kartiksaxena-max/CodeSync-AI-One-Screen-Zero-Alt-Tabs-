"""Search across everything in a lesson (transcript, slides, teacher's code).
TF-IDF for now; an on-device embedding model from Qualcomm AI Hub is the
planned upgrade (see docs/ARCHITECTURE.md)."""
from __future__ import annotations

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

_index: dict[str, tuple] = {}


def _norm(text: str) -> str:
    return re.sub(r"[_`]", " ", text).lower()


def _build(lesson: dict):
    docs = []
    for s in lesson["transcript"]:
        docs.append({"source": "transcript", "time": s["start"], "text": s["text"].replace("`", "")})
    for s in lesson["slides"]:
        docs.append({"source": "slide", "time": s["time"], "text": s["text"], "title": s["title"]})
    for e in lesson.get("code_timeline", []):
        docs.append({"source": "code", "time": e["time"], "text": e["text"].strip()})
    vec = TfidfVectorizer(ngram_range=(1, 2), token_pattern=r"[a-z0-9]{2,}", sublinear_tf=True)
    matrix = vec.fit_transform([_norm(d["text"]) for d in docs])
    return docs, vec, matrix


def search(lesson: dict, query: str, limit: int = 6) -> list[dict]:
    key = lesson["id"]
    if key not in _index:
        _index[key] = _build(lesson)
    docs, vec, matrix = _index[key]
    q = vec.transform([_norm(query)])
    scores = linear_kernel(q, matrix).ravel()
    order = scores.argsort()[::-1][:limit]
    return [dict(docs[i], score=round(float(scores[i]), 3)) for i in order if scores[i] > 0.02]
