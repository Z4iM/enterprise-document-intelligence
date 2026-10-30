"""Explicit public model download; no application import, credentials or request-time setup."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    from huggingface_hub import HfApi, hf_hub_download

    parser = argparse.ArgumentParser(
        description="Download the fixed public multilingual ONNX model into a new directory."
    )
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise SystemExit(
            "Use a new empty model directory; existing files are never overwritten."
        )
    repository = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
    info = HfApi(token=False).model_info(
        repository,
        revision="faf4aa4225822f3bc6376869cb1164e8e3feedd0",
        files_metadata=True,
    )
    allowed = {
        "model_optimized.onnx",
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "ort_config.json",
        "unigram.json",
    }
    files = [item for item in info.siblings if item.rfilename in allowed]
    if (
        not {"model_optimized.onnx", "tokenizer.json"}
        <= {item.rfilename for item in files}
        or sum(item.size or 0 for item in files) > 300_000_000
    ):
        raise SystemExit(
            "Model manifest exceeds the 300 MB download budget or is incomplete."
        )
    directory.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for item in files:
        path = Path(
            hf_hub_download(
                repository,
                item.rfilename,
                revision=info.sha,
                local_dir=str(directory),
                token=False,
            )
        )
        with path.open("rb") as file:
            hashes[item.rfilename] = hashlib.file_digest(file, "sha256").hexdigest()
    manifest = {
        "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "repository": repository,
        "revision": info.sha,
        "files": hashes,
    }
    with (directory / "edi-manifest.json").open("x", encoding="utf-8") as output:
        json.dump(manifest, output, indent=2)
    print(
        json.dumps(
            {
                "model_directory": str(directory),
                "revision": info.sha,
                "bytes": sum(item.size or 0 for item in files),
                "files": len(files),
            }
        )
    )


if __name__ == "__main__":
    main()
