import argparse
import json
import logging
from pathlib import Path
from .config import Settings
from .embeddings import Encoder
from .store import Store
from .service import Service
from .evaluation import evaluate


def main():
    parser = argparse.ArgumentParser(description="DocuLens — search and understand your documents")
    parser.add_argument("--data-dir", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="Explicitly download and pin the local embedding model")
    sub.add_parser("demo", help="Index the original fictional document corpus")
    sub.add_parser("reindex", help="Re-embed all documents with the installed model")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8010)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("file", type=Path)
    ingest.add_argument("--title", required=True)
    ingest.add_argument("--category", default="General")
    ingest.add_argument("--version", default="1.0")
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="hybrid")
    ask.add_argument("--generate", action="store_true", help="Send retrieved passages to the configured LLM")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env(args.data_dir)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    encoder = Encoder(settings)
    if args.command == "setup":
        print(encoder.setup())
        return
    if args.command == "serve":
        import uvicorn
        from .api import create_app

        uvicorn.run(create_app(settings=settings, encoder=encoder), host=args.host, port=args.port)
        return
    service = Service(settings, Store(settings.data_dir / "doculens.db"), encoder)
    try:
        if args.command == "demo":
            print(
                json.dumps(
                    {"added": len(service.load_demo()), "documents": len(service.store.documents())}, indent=2
                )
            )
        elif args.command == "reindex":
            print(json.dumps({"reindexed_chunks": service.reindex()}))
        elif args.command == "ingest":
            print(
                json.dumps(
                    service.ingest(
                        args.file.read_bytes(), args.file.name, args.title, args.category, args.version
                    ),
                    indent=2,
                )
            )
        elif args.command == "ask":
            print(json.dumps(service.ask(args.question, mode=args.mode, use_llm=args.generate), indent=2))
        elif args.command == "evaluate":
            identity = service.store.create_evaluation()
            try:
                report = evaluate(service)
                service.store.update_evaluation(identity, "completed", "Evaluation complete", report)
            except Exception:
                service.store.update_evaluation(
                    identity, "failed", "CLI evaluation failed; see terminal error"
                )
                raise
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2))
            print(json.dumps({"id": identity, "aggregates": report["aggregates"]}, indent=2))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
