"""TXT parser startup must not load unrelated, expensive OCR/Office/model stacks."""

import os
import subprocess
import sys
from pathlib import Path

from app.ingestion.safety import extract_text_isolated


def test_txt_worker_has_no_ocr_office_pdf_or_model_imports():
    code = "import app.ingestion.worker,sys; assert not {'pytesseract','pandas','docx','pptx','pypdf','PIL','google.genai','app.database.database'} & set(sys.modules)"
    environment = {
        key: os.environ[key]
        for key in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP")
        if key in os.environ
    }
    environment["PYTHON_DOTENV_DISABLED"] = "1"
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    subprocess.run(
        [sys.executable, "-c", code], env=environment, check=True, timeout=15
    )
    assert extract_text_isolated("إيصال تجريبي ١٧٥".encode(), "txt") == (
        "إيصال تجريبي ١٧٥",
        "txt_decoder",
    )
