from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
import csv
import io
import json
import logging
import threading
import time
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ConfigDict
from .config import Settings
from .store import Store
from .embeddings import Encoder
from .service import Service
from .ingest import MAX_BYTES
from .evaluation import evaluate

logger = logging.getLogger(__name__)


class Query(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=3, max_length=1500)
    mode: Literal["keyword", "semantic", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=10)
    category: str | None = Field(default=None, max_length=50)
    document_id: str | None = None
    include_archived: bool = False
    use_llm: bool = False


def create_app(data_dir=None, settings=None, encoder=None):
    settings = settings or Settings.from_env(data_dir)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    store = Store(settings.data_dir / "doculens.db")
    encoder = encoder or Encoder(settings)
    service = Service(settings, store, encoder)
    eval_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield

    app = FastAPI(
        title="DocuLens API",
        version="1.0.0",
        lifespan=lifespan,
        description="Document ingestion, local hybrid retrieval, cited answers, and inspectable evaluation.",
    )
    app.state.service = service

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        identity = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        # Prevent browser cross-origin writes to the unauthenticated loopback application.
        origin = request.headers.get("origin")
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and origin
            and origin != str(request.base_url).rstrip("/")
        ):
            return JSONResponse({"detail": "Cross-origin write requests are not permitted."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Request-ID"] = identity
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        # The OpenAPI explorer uses an external CDN; this is the only route with that exception.
        if request.url.path in {"/docs", "/redoc"}:
            del response.headers["Content-Security-Policy"]
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            identity,
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.get("/api/health")
    def health():
        try:
            with store.connect() as conn:
                conn.execute("SELECT 1")
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/api/status")
    def status():
        docs = store.documents()
        active = [d for d in docs if d["active"]]
        return {
            "documents": len(active),
            "versions": len(docs),
            "chunks": sum(d["chunk_count"] for d in active),
            "categories": sorted({d["category"] for d in active}),
            "semantic_ready": settings.embeddings and encoder.ready,
            "embedding_model": encoder.fingerprint,
            "provider": settings.provider,
            "llm_configured": settings.provider != "none" and bool(settings.llm_model),
            "answer_mode": "Local evidence excerpts"
            if settings.provider == "none"
            else "Optional generated answers",
            "privacy": "Document text stays local unless you explicitly select generated answers with a configured external provider.",
        }

    @app.get("/api/documents")
    def documents():
        return store.documents()

    @app.post("/api/demo", status_code=201)
    def demo():
        added = service.load_demo()
        return {"added": len(added), "documents": store.documents()}

    @app.post("/api/documents", status_code=201)
    async def upload(
        file: UploadFile = File(...),
        title: str = Form(...),
        category: str = Form("General"),
        version: str = Form("1.0"),
    ):
        raw = await file.read(MAX_BYTES + 1)
        filename = file.filename or "upload.txt"
        await file.close()
        return await run_in_threadpool(service.ingest, raw, filename, title, category, version)

    @app.post("/api/documents/{identity}/replace", status_code=201)
    async def replace(identity: str, file: UploadFile = File(...), version: str = Form(...)):
        old = store.get_document(identity)
        if not old:
            raise HTTPException(404, "Document not found")
        raw = await file.read(MAX_BYTES + 1)
        filename = file.filename or old["filename"]
        await file.close()
        return await run_in_threadpool(
            service.ingest, raw, filename, old["title"], old["category"], version, "user-upload", identity
        )

    @app.get("/api/documents/export")
    def export_documents():
        out = io.StringIO()
        columns = [
            "id",
            "title",
            "filename",
            "category",
            "version",
            "active",
            "sha256",
            "created_at",
            "page_count",
            "chunk_count",
        ]
        writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for d in store.documents():
            # Guard spreadsheet formula interpretation in user-supplied metadata exports.
            safe = {
                k: ("'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v)
                for k, v in d.items()
            }
            writer.writerow(safe)
        return Response(
            out.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=doculens-documents.csv"},
        )

    @app.get("/api/documents/{identity}")
    def document(identity: str):
        item = store.get_document(identity)
        if not item:
            raise HTTPException(404, "Document not found")
        chunks = store.chunks(document_id=identity, include_archived=True)
        return {**item, "chunks": [{k: v for k, v in c.items() if k != "embedding"} for c in chunks]}

    @app.get("/api/documents/{identity}/download")
    def original(identity: str):
        item = store.original(identity)
        if not item:
            raise HTTPException(404, "Document not found")
        # Safe generated filename; original user filename stays in document metadata.
        suffix = Path(item[0]).suffix.lower()
        return Response(
            item[1],
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=doculens-{identity}{suffix}"},
        )

    @app.delete("/api/documents/{identity}")
    def delete(identity: str):
        with service.mutation_lock:
            if not store.delete(identity):
                raise HTTPException(404, "Document not found")
        return {
            "deleted": identity,
            "note": "Document and chunks deleted. Query traces and evaluation reports cleared to remove retained excerpts. Archived versions are not automatically promoted.",
        }

    @app.get("/api/chunks/{identity}")
    def chunk(identity: str):
        row = store.chunk(identity)
        if not row:
            raise HTTPException(404, "Passage not found; the document may have been deleted")
        return row

    @app.post("/api/search")
    def search(body: Query):
        options = body.model_dump(exclude={"use_llm"})
        results, trace = service.search(**options)
        return {"question": body.question, "results": results, "trace": trace}

    @app.post("/api/ask")
    def ask(body: Query):
        return service.ask(**body.model_dump())

    @app.get("/api/traces")
    def traces():
        return store.traces()

    @app.get("/api/traces/{identity}/download")
    def trace_download(identity: str):
        trace = store.trace(identity)
        if not trace:
            raise HTTPException(404, "Trace not found")
        return Response(
            json.dumps(trace, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=doculens-trace-{identity[:8]}.json"},
        )

    @app.get("/api/evaluations")
    def evaluations():
        return store.evaluations()

    @app.post("/api/evaluations", status_code=202)
    def start_evaluation(background: BackgroundTasks):
        if not eval_lock.acquire(blocking=False):
            raise HTTPException(409, "An evaluation is already running")
        identity = store.create_evaluation()

        def task():
            try:
                with service.mutation_lock:
                    report = evaluate(service, lambda msg: store.update_evaluation(identity, "running", msg))
                    store.update_evaluation(identity, "completed", "Evaluation complete", report)
            except ValueError as exc:
                store.update_evaluation(identity, "failed", str(exc))
            except Exception:
                logger.exception("Evaluation failed")
                store.update_evaluation(identity, "failed", "Evaluation failed. Check server logs.")
            finally:
                eval_lock.release()

        background.add_task(task)
        return {"id": identity, "status": "running"}

    @app.get("/api/evaluations/{identity}/download")
    def eval_download(identity: str):
        item = next((e for e in store.evaluations() if e["id"] == identity), None)
        if not item:
            raise HTTPException(404, "Evaluation not found")
        if item["status"] != "completed":
            raise HTTPException(409, "Evaluation is not complete")
        return Response(
            json.dumps(item, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=doculens-evaluation-{identity[:8]}.json"},
        )

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(static / "index.html")

    return app
