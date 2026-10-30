import os
import uuid
from pathlib import Path

POLICY_ROOT = Path(os.getenv("EDI_DATA_ROOT", "data")) / "policies"


def generate_policy_id() -> str:
    return str(uuid.uuid4())


def save_policy_file(
    file_bytes: bytes,
    original_filename: str,
    policy_id: str
) -> str:

    policy_folder = POLICY_ROOT / policy_id

    policy_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    safe_filename = Path(original_filename).name

    file_path = policy_folder / safe_filename

    file_path.write_bytes(file_bytes)

    return str(file_path)
