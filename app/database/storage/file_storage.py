import hashlib
import os
import uuid
from pathlib import Path

UPLOAD_ROOT = Path(os.getenv("EDI_DATA_ROOT", "data")) / "uploads"


def generate_document_id() -> str:
    return str(uuid.uuid4())


def calculate_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def save_original_file(
    file_bytes: bytes,
    original_filename: str,
    document_id: str
) -> str:

    document_folder = UPLOAD_ROOT / document_id

    document_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    safe_filename = Path(original_filename).name

    file_path = document_folder / safe_filename

    file_path.write_bytes(file_bytes)

    return str(file_path)
