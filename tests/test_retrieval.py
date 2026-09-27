import numpy as np
from types import SimpleNamespace
from doculens.retrieval import bm25, search_rows, supported_candidates


def test_bm25_exact_terms_and_zero_match():
    scores = bm25("HTTP 429 retry", ["HTTP 429 retry after 30 seconds.", "Billing invoices are monthly."])
    assert scores[0] > scores[1] == 0
    assert not bm25("unicorn", ["No match."]).any()


def test_semantic_and_hybrid_use_vectors():
    class Encoder:
        ready = True
        fingerprint = "test"
        settings = SimpleNamespace(embeddings=True)

        def encode(self, texts):
            return np.array([[1.0, 0.0]], dtype=np.float32)

    def row(identity, text, vector):
        return {
            "id": identity,
            "title": "Guide",
            "section": "Procedure",
            "text": text,
            "embedding": np.array(vector, dtype=np.float32).tobytes(),
            "embedding_model": "test",
        }

    rows = [row("a", "unrelated lexical text", [0, 1]), row("b", "matching phrase", [1, 0])]
    semantic, _ = search_rows("different wording", rows, Encoder(), "semantic")
    assert semantic[0]["id"] == "b"
    hybrid, _ = search_rows("matching phrase", rows, Encoder(), "hybrid")
    assert hybrid[0]["id"] == "b"
    assert "embedding" not in hybrid[0]


def test_answerability_gate_is_not_raw_rank_score():
    rows = [
        {"text": "Backup retention is 30 days.", "section": "Retention", "semantic_score": 0.1, "score": 100}
    ]
    assert supported_candidates("What is backup retention?", rows) == []
    rows[0]["semantic_score"] = 0.8
    assert len(supported_candidates("What is backup retention?", rows)) == 1


def test_equal_scores_have_stable_document_order():
    encoder = SimpleNamespace(settings=SimpleNamespace(embeddings=False), ready=False)
    rows = [
        {"id": "random-a", "filename": "b.txt", "title": "Same", "section": "Same", "text": "shared token"},
        {"id": "random-z", "filename": "a.txt", "title": "Same", "section": "Same", "text": "shared token"},
    ]
    first, _ = search_rows("shared token", rows, encoder, "keyword")
    second, _ = search_rows("shared token", list(reversed(rows)), encoder, "keyword")
    assert [r["filename"] for r in first] == [r["filename"] for r in second] == ["a.txt", "b.txt"]
