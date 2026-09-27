"""Build a reproducible sample-only public deployment; no external LLM calls."""

import json
from doculens.config import Settings
from doculens.onnx_encoder import OnnxEncoder
from doculens.store import Store
from doculens.service import Service
from doculens.evaluation import evaluate

settings = Settings.from_env()
settings.data_dir.mkdir(parents=True, exist_ok=True)
encoder = OnnxEncoder(settings)
encoder.setup()
service = Service(settings, Store(settings.data_dir / "doculens.db"), encoder)
service.load_demo()
report = evaluate(service)
ident = service.store.create_evaluation()
service.store.update_evaluation(ident, "completed", "ONNX public-demo evaluation complete", report)
with service.store.connect() as conn:
    conn.execute("DELETE FROM traces")
print(
    json.dumps(
        {
            "documents": len(service.store.documents()),
            "encoder": encoder.fingerprint,
            "aggregates": report["aggregates"],
        },
        indent=2,
    )
)
