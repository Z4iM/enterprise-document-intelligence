from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".pptx": "pptx",
    ".txt": "txt"
}


def detect_file_type(filename: str) -> str:
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        return "unsupported"

    return SUPPORTED_EXTENSIONS[extension]