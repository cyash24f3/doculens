from dataclasses import dataclass
from pathlib import Path
import os
import math


@dataclass
class Settings:
    data_dir: Path
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    model_revision: str | None = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    embeddings: bool = True
    provider: str = "none"
    llm_model: str = ""
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    aws_region: str = "us-east-1"
    semantic_threshold: float = 0.40
    chunk_size: int = 150
    chunk_overlap: int = 25
    input_usd_per_million: float | None = None
    output_usd_per_million: float | None = None

    @classmethod
    def from_env(cls, data_dir=None):
        provider = os.getenv("DOCULENS_LLM_PROVIDER", "none").lower()
        if provider not in {"none", "openai-compatible", "bedrock"}:
            raise ValueError("DOCULENS_LLM_PROVIDER must be none, openai-compatible, or bedrock")

        def price(name):
            raw = os.getenv(name)
            if raw is None:
                return None
            value = float(raw)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite nonnegative number")
            return value

        return cls(
            input_usd_per_million=price("DOCULENS_INPUT_USD_PER_MILLION"),
            output_usd_per_million=price("DOCULENS_OUTPUT_USD_PER_MILLION"),
            data_dir=Path(data_dir or os.getenv("DOCULENS_DATA_DIR", "data")).resolve(),
            model_name=os.getenv("DOCULENS_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            model_revision=os.getenv("DOCULENS_MODEL_REVISION")
            or (
                "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
                if os.getenv("DOCULENS_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
                == "sentence-transformers/all-MiniLM-L6-v2"
                else None
            ),
            embeddings=os.getenv("DOCULENS_EMBEDDINGS", "on") != "off",
            provider=provider,
            llm_model=os.getenv("DOCULENS_LLM_MODEL", ""),
            base_url=os.getenv("DOCULENS_LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("DOCULENS_LLM_API_KEY", ""),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
        )
