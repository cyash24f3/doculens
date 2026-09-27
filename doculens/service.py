from pathlib import Path
import hashlib
import json
import logging
import threading
import time
from .ingest import extract, chunk_segments
from .retrieval import search_rows
from .generation import answer

logger = logging.getLogger(__name__)


class Service:
    def __init__(self, settings, store, encoder):
        self.settings, self.store, self.encoder = settings, store, encoder
        self.mutation_lock = threading.RLock()

    def ingest(self, raw, filename, title, category, version, source="user-upload", replaces=None):
        filename = Path(filename.replace("\\", "/")).name
        for label, value, limit in [
            ("Title", title, 120),
            ("Category", category, 50),
            ("Version", version, 30),
        ]:
            if not value.strip() or len(value) > limit:
                raise ValueError(f"{label} must be between 1 and {limit} characters.")
        segments, pages, warnings = extract(raw, filename)
        chunks = chunk_segments(segments, self.settings.chunk_size, self.settings.chunk_overlap)
        with self.mutation_lock:
            docs = self.store.documents()
            if len(docs) >= 200:
                raise ValueError(
                    "Workspace limit reached: 200 document versions. Delete unneeded versions first."
                )
            if sum(d["chunk_count"] for d in docs) + len(chunks) > 10000:
                raise ValueError("Workspace limit reached: 10,000 chunks. Delete unneeded versions first.")
            vectors = (
                self.encoder.encode([f"{title} {c['section']} {c['text']}" for c in chunks])
                if self.settings.embeddings
                else None
            )
            if vectors is not None:
                truncated = self.encoder.truncation_count(
                    [f"{title} {c['section']} {c['text']}" for c in chunks]
                )
                if truncated:
                    warnings.append(
                        f"{truncated} passages exceed the embedding model token budget. Semantic vectors are truncated; full text remains available to keyword search and citations."
                    )
            meta = {
                "title": title.strip(),
                "filename": filename,
                "category": category.strip(),
                "version": version.strip(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "page_count": pages,
                "warnings": warnings,
                "source": source,
                "embedding_model": self.encoder.fingerprint if vectors is not None else None,
            }
            return self.store.insert(meta, chunks, vectors, raw, replaces)

    def search(
        self, question, mode="hybrid", top_k=5, category=None, document_id=None, include_archived=False
    ):
        rows = self.store.chunks(category, document_id, include_archived)
        return search_rows(question, rows, self.encoder, mode, top_k)

    def ask(
        self,
        question,
        mode="hybrid",
        top_k=5,
        category=None,
        document_id=None,
        include_archived=False,
        use_llm=False,
    ):
        started = time.perf_counter()
        # Serialize corpus mutation with a query so stored traces cannot retain just-deleted text.
        with self.mutation_lock:
            results, trace = self.search(question, mode, top_k, category, document_id, include_archived)
            response = answer(question, results, self.settings, use_llm)
            trace.update(
                total_ms=round((time.perf_counter() - started) * 1000, 2),
                generation_ms=response["generation_ms"],
                embedding_model=self.encoder.fingerprint,
                category=category,
                document_id=document_id,
                include_archived=include_archived,
            )
            payload = {"question": question, "answer": response, "results": results, "trace": trace}
            payload["trace_id"] = self.store.save_trace(payload)
        return payload

    def load_demo(self):
        folder = Path(__file__).parent / "sample_corpus"
        manifest = json.loads((folder / "manifest.json").read_text())
        added = []
        with self.mutation_lock:
            existing = {d["filename"] for d in self.store.documents() if d["source"] == "sample-corpus"}
            for entry in manifest:
                if entry["file"] not in existing:
                    raw = (folder / entry["file"]).read_bytes()
                    added.append(
                        self.ingest(
                            raw,
                            entry["file"],
                            entry["title"],
                            entry["category"],
                            entry["version"],
                            "sample-corpus",
                        )
                    )
        return added

    def reindex(self):
        """Atomic vector refresh; old vectors remain intact if embedding generation fails."""
        if not self.settings.embeddings:
            raise ValueError("Enable embeddings before reindexing.")
        with self.mutation_lock:
            rows = self.store.chunks(include_archived=True)
            if not rows:
                return 0
            vectors = self.encoder.encode([f"{r['title']} {r['section']} {r['text']}" for r in rows])
            with self.store.connect() as conn:
                for row, vector in zip(rows, vectors):
                    conn.execute("UPDATE chunks SET embedding=? WHERE id=?", (vector.tobytes(), row["id"]))
                conn.execute("UPDATE documents SET embedding_model=?", (self.encoder.fingerprint,))
            return len(rows)
