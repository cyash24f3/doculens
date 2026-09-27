"""Local learned embeddings; never silently substitute random/hash vectors."""

import json
import os
import threading
import numpy as np


class Encoder:
    def __init__(self, settings):
        self.settings = settings
        self.path = settings.data_dir / "embedding-model"
        self._model = None
        self._lock = threading.Lock()

    @property
    def ready(self):
        return (self.path / "doculens-model.json").exists()

    @property
    def fingerprint(self):
        if not self.ready:
            return None
        return json.loads((self.path / "doculens-model.json").read_text())["fingerprint"]

    def setup(self):
        """An explicit CLI action downloads only model files, never user documents."""
        if self.ready:
            saved = json.loads((self.path / "doculens-model.json").read_text())
            if saved["model_name"] != self.settings.model_name or (
                self.settings.model_revision and saved["revision"] != self.settings.model_revision
            ):
                raise ValueError(
                    "Installed embedding model differs from configuration. Stop the server, move the embedding-model directory aside, then run setup and reindex before restarting."
                )
            return self.fingerprint
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        from huggingface_hub import HfApi
        from sentence_transformers import SentenceTransformer

        info = HfApi().model_info(self.settings.model_name, revision=self.settings.model_revision)
        revision = info.sha
        cache = self.settings.data_dir / "model-cache"
        model = SentenceTransformer(
            self.settings.model_name,
            revision=revision,
            cache_folder=str(cache),
            device="cpu",
            trust_remote_code=False,
        )
        self.path.mkdir(parents=True, exist_ok=True)
        model.save(str(self.path), safe_serialization=True)
        manifest = {
            "model_name": self.settings.model_name,
            "revision": revision,
            "dimension": (
                model.get_embedding_dimension()
                if hasattr(model, "get_embedding_dimension")
                else model.get_sentence_embedding_dimension()
            ),
            "fingerprint": f"{self.settings.model_name}@{revision}",
            "normalized": True,
        }
        (self.path / "doculens-model.json").write_text(json.dumps(manifest, indent=2))
        self._model = model
        return manifest["fingerprint"]

    def encode(self, texts):
        if not self.settings.embeddings:
            return None
        if not self.ready:
            raise ValueError(
                "Semantic model is not installed. Run `doculens setup` first, or use keyword-only mode."
            )
        with self._lock:
            if self._model is None:
                os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(
                    str(self.path), device="cpu", local_files_only=True, trust_remote_code=False
                )
            vectors = self._model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                batch_size=32,
                show_progress_bar=False,
            )
        vectors = np.asarray(vectors, dtype=np.float32)
        if not np.isfinite(vectors).all():
            raise ValueError("Embedding model returned non-finite values.")
        return vectors

    def truncation_count(self, texts):
        if self._model is None:
            return 0
        with self._lock:
            lengths = [
                len(ids) for ids in self._model.tokenizer(texts, truncation=False, padding=False)["input_ids"]
            ]
            return sum(n > self._model.max_seq_length for n in lengths)
