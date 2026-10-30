"""Optional local CPU encoder. Request paths never download or execute model code."""

import hashlib
import json
import logging
import math
import os
import threading
from pathlib import Path

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_REPO = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
DIMENSIONS = 384
MODEL_REVISION = "faf4aa4225822f3bc6376869cb1164e8e3feedd0"
_instances = {}
_lock = threading.Lock()


class EmbeddingUnavailable(ValueError):
    pass


def unit_vector(values):
    values = [float(value) for value in values]
    if len(values) != DIMENSIONS or not all(math.isfinite(value) for value in values):
        raise EmbeddingUnavailable("Invalid embedding output.")
    norm = math.sqrt(sum(value * value for value in values))
    if not math.isfinite(norm) or norm <= 0:
        raise EmbeddingUnavailable("Empty embedding output.")
    return [value / norm for value in values]


class LocalEncoder:
    def __init__(self, directory):
        from fastembed import TextEmbedding
        from tokenizers import Tokenizer

        directory = Path(directory).resolve()
        manifest = json.loads(
            (directory / "edi-manifest.json").read_text(encoding="utf-8")
        )
        if (
            manifest["model"] != MODEL_NAME
            or manifest["repository"] != MODEL_REPO
            or manifest["revision"] != MODEL_REVISION
        ):
            raise EmbeddingUnavailable("Unsupported embedding model.")
        required = {
            "model_optimized.onnx",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "config.json",
            "ort_config.json",
            "unigram.json",
        }
        if set(manifest["files"]) != required:
            raise EmbeddingUnavailable("Incomplete model manifest.")
        for filename, expected in manifest["files"].items():
            path = (directory / filename).resolve()
            if not path.is_relative_to(directory) or not path.is_file():
                raise EmbeddingUnavailable("Model files unavailable.")
            with path.open("rb") as file:
                if hashlib.file_digest(file, "sha256").hexdigest() != expected:
                    raise EmbeddingUnavailable("Model integrity check failed.")
        self.identity = (
            MODEL_NAME
            + ":"
            + manifest["revision"]
            + ":"
            + manifest["files"]["model_optimized.onnx"]
        )
        self.model = TextEmbedding(
            model_name=MODEL_NAME,
            specific_model_path=str(directory),
            local_files_only=True,
            threads=1,
            providers=["CPUExecutionProvider"],
            enable_cpu_mem_arena=False,
        )
        self.lock = threading.Lock()
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.no_truncation()

    def spans(self, text):
        offsets = self.tokenizer.encode(text, add_special_tokens=False).offsets
        for position in range(0, len(offsets), 80):
            window = offsets[position : position + 96]
            start, end = window[0][0], window[-1][1]
            if end > start:
                # Rare long unknown-token spans still have a bounded quoted payload.
                for left in range(start, end, 400):
                    yield left, min(left + 400, end)

    def embed(self, texts: list[str]) -> list[list[float]]:
        # No worker pool/GPU; keep inference within the calling process's bounded lease.
        if not self.lock.acquire(timeout=5):
            raise EmbeddingUnavailable("Semantic encoder is busy.")
        try:
            vectors = [
                unit_vector(vector)
                for vector in self.model.embed(texts, batch_size=8, parallel=None)
            ]
            if len(vectors) != len(texts):
                raise EmbeddingUnavailable("Incomplete embedding output.")
            return vectors
        except Exception as error:
            raise EmbeddingUnavailable("Semantic encoding failed.") from error
        finally:
            self.lock.release()


def configured_encoder():
    directory = os.getenv("EDI_RETRIEVAL_MODEL_DIR", "")
    if not directory:
        return None
    try:
        with _lock:
            if directory not in _instances:
                _instances[directory] = LocalEncoder(directory)
            return _instances[directory]
    except Exception as error:
        logging.getLogger(__name__).warning(
            "Semantic encoder unavailable (%s).", type(error).__name__
        )
        raise EmbeddingUnavailable(
            "Semantic model unavailable; configure the verified local model."
        ) from error
