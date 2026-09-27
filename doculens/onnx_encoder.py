"""Memory-conscious MiniLM serving with the same pinned upstream model in ONNX."""

import json
import threading
import numpy as np


class OnnxEncoder:
    def __init__(self, settings):
        self.settings = settings
        self.path = settings.data_dir / "onnx-model"
        self._session = None
        self._tokenizer = None
        self._lock = threading.Lock()

    @property
    def ready(self):
        return (self.path / "manifest.json").exists()

    @property
    def fingerprint(self):
        return json.loads((self.path / "manifest.json").read_text())["fingerprint"] if self.ready else None

    def setup(self):
        from huggingface_hub import hf_hub_download

        self.path.mkdir(parents=True, exist_ok=True)
        for filename in ["onnx/model.onnx", "tokenizer.json"]:
            hf_hub_download(
                self.settings.model_name, filename, revision=self.settings.model_revision, local_dir=self.path
            )
        manifest = {
            "fingerprint": f"{self.settings.model_name}@{self.settings.model_revision}/onnx-fp32",
            "model_name": self.settings.model_name,
            "revision": self.settings.model_revision,
            "normalized": True,
            "dimension": 384,
        }
        (self.path / "manifest.json").write_text(json.dumps(manifest, indent=2))
        return manifest["fingerprint"]

    def _load(self):
        if self._session is not None:
            return
        import onnxruntime as ort
        from tokenizers import Tokenizer

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        self._session = ort.InferenceSession(
            str(self.path / "onnx/model.onnx"), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self._tokenizer = Tokenizer.from_file(str(self.path / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=256)
        self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

    def encode(self, texts):
        if not self.settings.embeddings:
            return None
        if not self.ready:
            raise ValueError("ONNX model not prepared")
        vectors = []
        with self._lock:
            self._load()
            for start in range(0, len(texts), 8):
                batch = self._tokenizer.encode_batch(texts[start : start + 8])
                inputs = {
                    "input_ids": np.array([x.ids for x in batch], dtype=np.int64),
                    "attention_mask": np.array([x.attention_mask for x in batch], dtype=np.int64),
                    "token_type_ids": np.array([x.type_ids for x in batch], dtype=np.int64),
                }
                allowed = {x.name for x in self._session.get_inputs()}
                hidden = self._session.run(None, {k: v for k, v in inputs.items() if k in allowed})[0]
                mask = inputs["attention_mask"][..., None].astype(np.float32)
                pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1e-9)
                pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)
                vectors.extend(pooled)
        result = np.asarray(vectors, dtype=np.float32)
        if not np.isfinite(result).all():
            raise ValueError("Non-finite embedding")
        return result

    def truncation_count(self, texts):
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(str(self.path / "tokenizer.json"))
        tokenizer.no_truncation()
        tokenizer.no_padding()
        return sum(len(x.ids) > 256 for x in tokenizer.encode_batch(texts))
