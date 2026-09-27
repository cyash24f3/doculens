"""Frozen, inspectable sample benchmark. Automated answer proxies are not human correctness."""

from datetime import datetime, timezone
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version
import hashlib
import json
import time
import uuid
import numpy as np
from .ingest import extract, chunk_segments
from .retrieval import search_rows
from .generation import answer


def installed_versions():
    result = {}
    for package in ["numpy", "sentence-transformers", "onnxruntime", "tokenizers", "pypdf"]:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            pass  # Serving backends intentionally have different optional dependencies.
    return result


def relevant(result, gold):
    return result["filename"] == gold["file"] and gold["contains"].casefold() in result["text"].casefold()


def evaluate(service, progress=lambda message: None):
    folder = Path(__file__).parent / "sample_corpus"
    questions = json.loads((folder / "evaluation.json").read_text())
    manifest = json.loads((folder / "manifest.json").read_text())
    docs = {
        d["filename"]: d for d in service.store.documents() if d["active"] and d["source"] == "sample-corpus"
    }
    for entry in manifest:
        raw = (folder / entry["file"]).read_bytes()
        if entry["file"] not in docs or docs[entry["file"]]["sha256"] != hashlib.sha256(raw).hexdigest():
            raise ValueError(
                "Evaluation needs all 12 original, active demo documents. Restore the demo corpus before evaluating."
            )
    doc_ids = {d["id"] for d in docs.values()}
    current = [r for r in service.store.chunks() if r["document_id"] in doc_ids]
    configs = [
        ("keyword-section", "keyword", current),
        ("semantic-section", "semantic", current),
        ("hybrid-section", "hybrid", current),
    ]
    if not service.settings.embeddings or not service.encoder.ready:
        configs = configs[:1]
    else:
        fixed = []
        for entry in manifest:
            doc = docs[entry["file"]]
            segments, _, _ = extract((folder / entry["file"]).read_bytes(), entry["file"])
            chunks = chunk_segments(segments, 150, 25, strategy="fixed")
            vectors = service.encoder.encode([f"{doc['title']} {c['section']} {c['text']}" for c in chunks])
            for c, v in zip(chunks, vectors):
                fixed.append(
                    {
                        **c,
                        "id": uuid.uuid4().hex,
                        "document_id": doc["id"],
                        "title": doc["title"],
                        "filename": doc["filename"],
                        "version": doc["version"],
                        "category": doc["category"],
                        "active": 1,
                        "source": "sample-corpus",
                        "embedding_model": service.encoder.fingerprint,
                        "embedding": v.tobytes(),
                    }
                )
        configs.append(("hybrid-fixed", "hybrid", fixed))
    detail = []
    for label, mode, rows in configs:
        progress(f"Evaluating {label}: {len(questions)} labeled questions")
        for q in questions:
            started = time.perf_counter()
            results, trace = search_rows(q["question"], rows, service.encoder, mode, 5)
            response = answer(q["question"], results, service.settings, use_llm=False)
            gold = q["gold"]
            recall = sum(any(relevant(r, g) for r in results) for g in gold) / len(gold) if gold else None
            first = next((i for i, r in enumerate(results, 1) if any(relevant(r, g) for g in gold)), None)
            text = " ".join(s["text"] for s in response["statements"])
            terms = q["expected_terms"]
            term_coverage = (
                sum(t.casefold() in text.casefold() for t in terms) / len(terms) if terms else None
            )
            sources = {r["source_id"]: r for r in response["sources"]}
            statements = response["statements"]
            fidelity = [
                any(s["text"] in sources[c]["text"] for c in s["citations"] if c in sources)
                for s in statements
            ]
            detail.append(
                {
                    "id": q["id"],
                    "question": q["question"],
                    "split": q["split"],
                    "answerable": q["answerable"],
                    "configuration": label,
                    "recall_at_5": recall,
                    "reciprocal_rank": 1 / first if first else 0,
                    "abstained": response["abstained"],
                    "answer_term_coverage_proxy": term_coverage,
                    "quote_checks": fidelity,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "expected_evidence": gold,
                    "retrieved": [
                        {
                            "filename": r["filename"],
                            "section": r["section"],
                            "rank": r["rank"],
                            "semantic_score": r["semantic_score"],
                        }
                        for r in results
                    ],
                    "answer_excerpt": text,
                }
            )
    aggregates = []
    for label, _, rows in configs:
        for split in ("dev", "test"):
            group = [r for r in detail if r["configuration"] == label and r["split"] == split]
            ans = [r for r in group if r["answerable"]]
            unans = [r for r in group if not r["answerable"]]
            quotes = [v for r in group for v in r["quote_checks"]]
            aggregates.append(
                {
                    "configuration": label,
                    "split": split,
                    "questions": len(group),
                    "chunks": len(rows),
                    "answerable_questions": len(ans),
                    "unanswerable_questions": len(unans),
                    "recall_at_5": float(np.mean([r["recall_at_5"] for r in ans])),
                    "mrr_at_5": float(np.mean([r["reciprocal_rank"] for r in ans])),
                    "answerable_response_rate": float(np.mean([not r["abstained"] for r in ans])),
                    "unanswerable_abstention_rate": float(np.mean([r["abstained"] for r in unans])),
                    "answer_term_coverage_proxy": float(
                        np.mean([r["answer_term_coverage_proxy"] for r in ans])
                    ),
                    "verbatim_quote_fidelity": float(np.mean(quotes)) if quotes else None,
                    "p50_latency_ms": float(np.median([r["latency_ms"] for r in group])),
                    "p95_latency_ms": float(np.percentile([r["latency_ms"] for r in group], 95)),
                }
            )
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "question_count": len(questions),
        "corpus": "12 original fictional Atlas documents; no user-uploaded documents included",
        "label_note": "Labels authored with the project, not independently human-reviewed. Dev/test splits fixed before running; results are an illustrative benchmark, not production accuracy.",
        "metric_note": "Recall@5 measures gold passage coverage. Answer-term coverage is a lexical proxy, not factual correctness. Quote fidelity checks verbatim source membership, not relevance. Latencies include local warmed/cold cache effects and are not an SLA.",
        "embedding_model": service.encoder.fingerprint,
        "gate_threshold": service.settings.semantic_threshold,
        "versions": installed_versions(),
        "source_hashes": {d["filename"]: d["sha256"] for d in docs.values()},
        "question_set_sha256": hashlib.sha256((folder / "evaluation.json").read_bytes()).hexdigest(),
        "aggregates": aggregates,
        "details": detail,
    }
