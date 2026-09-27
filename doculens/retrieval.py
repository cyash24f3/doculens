"""Inspectable BM25, cosine semantic retrieval, and reciprocal-rank fusion."""

from collections import Counter
import math
import re
import time
import numpy as np

STOP = set(
    "a an the is are was were be been being do does did how what when where why which who whom can could should would will may must i me my we our you your it its they their this that these those of to for from by with without in on at as and or but not about please tell explain give describe according document documents".split()
)


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in STOP]


def bm25(query, texts):
    counts = [Counter(tokens(t)) for t in texts]
    n = len(counts)
    if not n:
        return np.array([], dtype=float)
    lengths = np.array([sum(c.values()) for c in counts], dtype=float)
    mean_length = max(float(lengths.mean()), 1)
    scores = np.zeros(n)
    for token in set(tokens(query)):
        df = sum(token in c for c in counts)
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        freq = np.array([c.get(token, 0) for c in counts], dtype=float)
        scores += idf * freq * 2.5 / (freq + 1.5 * (0.25 + 0.75 * lengths / mean_length))
    return scores


def search_rows(question, rows, encoder, mode="hybrid", top_k=5):
    if mode not in {"keyword", "semantic", "hybrid"}:
        raise ValueError("Unknown search mode")
    started = time.perf_counter()
    if not rows:
        return [], {"retrieval_ms": 0, "candidate_chunks": 0, "mode": mode}
    texts = [f"{r['title']} {r['section']} {r['text']}" for r in rows]
    lexical = bm25(question, texts)
    semantic = None
    if encoder.settings.embeddings and encoder.ready:
        if any(r["embedding"] is None or r["embedding_model"] != encoder.fingerprint for r in rows):
            if mode != "keyword":
                raise ValueError(
                    "Some documents use a different or missing embedding model. Reindex the corpus before semantic search."
                )
        else:
            q = encoder.encode([question])[0]
            vectors = np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
            if vectors.shape[1] != len(q):
                raise ValueError("Embedding dimensions differ. Reindex the corpus.")
            semantic = vectors @ q
    if mode != "keyword" and semantic is None:
        raise ValueError(
            "Semantic search is unavailable. Run `doculens setup` and index documents, or select Keyword."
        )

    def stable_key(i):
        return (
            rows[i].get("filename", ""),
            rows[i].get("version", ""),
            rows[i].get("ordinal", 0),
            rows[i]["text"],
        )

    lex_order = sorted(
        [i for i in range(len(rows)) if lexical[i] > 0], key=lambda i: (-lexical[i], stable_key(i))
    )
    sem_order = (
        sorted(range(len(rows)), key=lambda i: (-semantic[i], stable_key(i))) if semantic is not None else []
    )
    if mode == "keyword":
        order = lex_order
        rank_scores = {i: float(lexical[i]) for i in order}
    elif mode == "semantic":
        order = sem_order
        rank_scores = {i: float(semantic[i]) for i in order}
    else:
        rank_scores = {}
        for ranking in (lex_order[:30], sem_order[:30]):
            for rank, i in enumerate(ranking, 1):
                rank_scores[i] = rank_scores.get(i, 0) + 1 / (60 + rank)
        order = sorted(rank_scores, key=lambda i: (-rank_scores[i], stable_key(i)))
    results = []
    for rank, i in enumerate(order[:top_k], 1):
        row = {k: v for k, v in rows[i].items() if k not in {"embedding"}}
        row.update(
            rank=rank,
            score=rank_scores[i],
            keyword_score=float(lexical[i]),
            semantic_score=float(semantic[i]) if semantic is not None else None,
        )
        results.append(row)
    return results, {
        "retrieval_ms": round((time.perf_counter() - started) * 1000, 2),
        "candidate_chunks": len(rows),
        "mode": mode,
        "top_k": top_k,
        "ranking_note": "Scores rank passages; they are not probabilities of correctness.",
    }


def supported_candidates(question, results, threshold=0.40):
    query = set(tokens(question))
    candidates = []
    for result in results:
        common = query & set(tokens(result["text"] + " " + result["section"]))
        cosine = result["semantic_score"]
        # A conservative heuristic, not an answerability classifier or proof of entailment.
        supported = cosine is not None and cosine >= threshold and len(common) >= 1
        if cosine is None:
            supported = len(common) >= 2 and len(common) / max(1, len(query)) >= 0.4
        if supported:
            candidates.append(result)
    return candidates
