"""Parser subprocess; no database, credentials, tools or model access."""

import json
import sys

from app.ingestion.safety import validate_structure
from app.ingestion.text_extractor import extract_text


def main():
    raw = sys.stdin.buffer.read(20 * 1024 * 1024 + 1)
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError("Input budget")
    if sys.argv[2] == "validate":
        sys.stdout.buffer.write(
            json.dumps(validate_structure(raw, sys.argv[1])).encode("utf-8")
        )
        return
    validate_structure(raw, sys.argv[1])
    text, method = extract_text(raw, sys.argv[1])
    if len(text) > 1_000_000:
        raise ValueError("Extracted text budget")
    sys.stdout.buffer.write(json.dumps([text, method]).encode("utf-8"))


if __name__ == "__main__":
    main()
