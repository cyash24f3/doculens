"""SQLite snapshots: documents and vectors commit together; superseded versions stay archived."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
import uuid
import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, family_id TEXT NOT NULL, title TEXT NOT NULL, filename TEXT NOT NULL,
 category TEXT NOT NULL, version TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
 sha256 TEXT NOT NULL, created_at TEXT NOT NULL, page_count INTEGER NOT NULL,
 chunk_count INTEGER NOT NULL, source TEXT NOT NULL, warnings_json TEXT NOT NULL,
 embedding_model TEXT, byte_size INTEGER NOT NULL, raw BLOB NOT NULL,
 UNIQUE(family_id,version)
);
CREATE TABLE IF NOT EXISTS chunks (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL, page INTEGER NOT NULL, section TEXT NOT NULL, text TEXT NOT NULL,
 word_start INTEGER NOT NULL, word_end INTEGER NOT NULL, embedding BLOB,
 UNIQUE(document_id,ordinal)
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE TABLE IF NOT EXISTS traces (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, question TEXT NOT NULL, body_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evaluations (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL, message TEXT NOT NULL,
 report_json TEXT
);
"""


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def document(row):
        if row is None:
            return None
        d = dict(row)
        d.pop("raw", None)
        d["active"] = bool(d["active"])
        d["warnings"] = json.loads(d.pop("warnings_json"))
        return d

    def documents(self):
        with self.connect() as conn:
            return [
                self.document(r) for r in conn.execute("SELECT * FROM documents ORDER BY created_at DESC")
            ]

    def get_document(self, identity):
        with self.connect() as conn:
            return self.document(conn.execute("SELECT * FROM documents WHERE id=?", (identity,)).fetchone())

    def insert(self, meta, chunks, vectors, raw, replaces=None):
        identity = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if replaces:
                old = conn.execute("SELECT * FROM documents WHERE id=? AND active=1", (replaces,)).fetchone()
                if not old:
                    raise ValueError("Only the current active version can be replaced.")
                family = old["family_id"]
                if conn.execute(
                    "SELECT id FROM documents WHERE family_id=? AND version=?", (family, meta["version"])
                ).fetchone():
                    raise ValueError("This version label already exists in the document family.")
                conn.execute("UPDATE documents SET active=0 WHERE family_id=?", (family,))
            else:
                family = identity
                if conn.execute(
                    "SELECT id FROM documents WHERE sha256=? AND active=1", (meta["sha256"],)
                ).fetchone():
                    raise ValueError(
                        "This exact content is already indexed. Replace its version or upload different content."
                    )
            conn.execute(
                """INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    identity,
                    family,
                    meta["title"],
                    meta["filename"],
                    meta["category"],
                    meta["version"],
                    1,
                    meta["sha256"],
                    now(),
                    meta["page_count"],
                    len(chunks),
                    meta["source"],
                    json.dumps(meta["warnings"]),
                    meta["embedding_model"],
                    len(raw),
                    raw,
                ),
            )
            for i, chunk in enumerate(chunks):
                vector = vectors[i].astype(np.float32).tobytes() if vectors is not None else None
                conn.execute(
                    "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        uuid.uuid4().hex,
                        identity,
                        chunk["ordinal"],
                        chunk["page"],
                        chunk["section"],
                        chunk["text"],
                        chunk["word_start"],
                        chunk["word_end"],
                        vector,
                    ),
                )
        return self.get_document(identity)

    def chunk(self, identity):
        with self.connect() as conn:
            row = conn.execute(
                """SELECT c.*,d.title,d.filename,d.version,d.active,d.category
                             FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.id=?""",
                (identity,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d.pop("embedding", None)
        return d

    def chunks(self, category=None, document_id=None, include_archived=False):
        query = """SELECT c.*, d.title,d.filename,d.version,d.category,d.active,d.source,d.embedding_model
                 FROM chunks c JOIN documents d ON d.id=c.document_id WHERE 1=1"""
        params = []
        if not include_archived:
            query += " AND d.active=1"
        if category:
            query += " AND d.category=?"
            params.append(category)
        if document_id:
            query += " AND d.id=?"
            params.append(document_id)
        query += " ORDER BY d.id,c.ordinal"
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(query, params)]

    def original(self, identity):
        with self.connect() as conn:
            row = conn.execute("SELECT filename,raw FROM documents WHERE id=?", (identity,)).fetchone()
            return (row["filename"], row["raw"]) if row else None

    def delete(self, identity):
        with self.connect() as conn:
            result = conn.execute("DELETE FROM documents WHERE id=?", (identity,))
            if result.rowcount == 0:
                return False
            # Saved answers contain excerpts. Clear traces/evaluations on any corpus deletion
            # so deleted text is not retained in hidden query history or exported evaluations.
            conn.execute("DELETE FROM traces")
            conn.execute("DELETE FROM evaluations")
            return result.rowcount > 0

    def save_trace(self, body):
        identity = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO traces VALUES (?,?,?,?)", (identity, now(), body["question"], json.dumps(body))
            )
            conn.execute(
                "DELETE FROM traces WHERE id NOT IN (SELECT id FROM traces ORDER BY created_at DESC LIMIT 100)"
            )
        return identity

    def traces(self):
        with self.connect() as conn:
            return [
                {
                    "id": r["id"],
                    "created_at": r["created_at"],
                    "question": r["question"],
                    "body": json.loads(r["body_json"]),
                }
                for r in conn.execute("SELECT * FROM traces ORDER BY created_at DESC LIMIT 30")
            ]

    def trace(self, identity):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM traces WHERE id=?", (identity,)).fetchone()
            return (
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "question": row["question"],
                    "body": json.loads(row["body_json"]),
                }
                if row
                else None
            )

    def create_evaluation(self):
        identity = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO evaluations VALUES (?,?,?,?,NULL)",
                (identity, now(), "running", "Evaluating retrieval methods"),
            )
        return identity

    def update_evaluation(self, identity, status, message, report=None):
        with self.connect() as conn:
            conn.execute(
                "UPDATE evaluations SET status=?,message=?,report_json=? WHERE id=?",
                (status, message, json.dumps(report) if report else None, identity),
            )

    def evaluations(self):
        with self.connect() as conn:
            return [
                {
                    "id": r["id"],
                    "created_at": r["created_at"],
                    "status": r["status"],
                    "message": r["message"],
                    "report": json.loads(r["report_json"]) if r["report_json"] else None,
                }
                for r in conn.execute("SELECT * FROM evaluations ORDER BY created_at DESC")
            ]

    def recover(self):
        with self.connect() as conn:
            conn.execute(
                "UPDATE evaluations SET status='failed',message='Server interrupted. Run evaluation again.' WHERE status='running'"
            )
