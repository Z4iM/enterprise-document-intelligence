"""Resource budgets and sanitized failures; external OCR/model calls are mocked."""

import subprocess
import zipfile
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from PIL import Image
from pypdf import PdfWriter

from app.extraction import router
from app.ingestion import safety

pytestmark = pytest.mark.security


def test_pdf_page_and_image_pixel_budgets():
    output = BytesIO()
    writer = PdfWriter()
    for _ in range(21):
        writer.add_blank_page(width=100, height=100)
    writer.write(output)
    with pytest.raises(ValueError, match="page budget"):
        safety.validate_structure(output.getvalue(), "pdf")
    output = BytesIO()
    Image.new("RGB", (2001, 2000)).save(output, format="PNG")
    with pytest.raises(ValueError, match="Image budget"):
        safety.validate_structure(output.getvalue(), "image")


def test_compressed_office_expansion_is_rejected():
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "x" * 1_000_000)
    with pytest.raises(ValueError, match="Compression ratio"):
        safety.validate_structure(output.getvalue(), "docx")


def test_parser_deadline_kills_only_owned_process_and_releases_slot(monkeypatch):
    child = MagicMock()
    child.pid = 424242
    child.communicate.side_effect = subprocess.TimeoutExpired("synthetic-parser", 45)
    context = MagicMock()
    context.__enter__.return_value = child
    monkeypatch.setattr(safety.subprocess, "Popen", MagicMock(return_value=context))
    kill_tree = MagicMock()
    monkeypatch.setattr(safety.subprocess, "run", kill_tree)
    kill_group = MagicMock()
    monkeypatch.setattr(safety.os, "killpg", kill_group, raising=False)
    with pytest.raises(ValueError, match="deadline"):
        safety.run_worker(b"synthetic", "txt")
    child.kill.assert_called_once()
    if safety.os.name == "nt":
        assert kill_tree.call_args.args[0] == ["taskkill", "/PID", "424242", "/T", "/F"]
    else:
        assert kill_group.call_args.args[0] == 424242
    assert safety.PARSER_SLOTS.acquire(blocking=False)
    assert safety.PARSER_SLOTS.acquire(blocking=False)
    safety.PARSER_SLOTS.release()
    safety.PARSER_SLOTS.release()


def test_fallback_logs_type_without_sensitive_exception_values(monkeypatch, caplog):
    marker = "synthetic-sensitive-source-and-token-marker"
    monkeypatch.setattr(router, "get_llm_provider", lambda: object())

    def failure(**kwargs):
        raise ValueError(marker)

    monkeypatch.setattr(router, "extract_with_llm", failure)
    data, method, failed = router.extract_structured_data(
        "Receipt total $175.00", "receipt"
    )
    assert method == "regex_fallback" and failed and data
    assert marker not in caplog.text
    assert "failure_type=ValueError" in caplog.text


def test_large_text_cannot_trigger_unbounded_model_input(monkeypatch):
    provider = MagicMock()
    monkeypatch.setattr(router, "get_llm_provider", provider)
    _, method, failed = router.extract_structured_data(
        "Receipt " + "x" * 30000, "receipt"
    )
    assert method == "regex_fallback" and failed
    provider.assert_not_called()


def test_disabled_provider_cannot_construct_a_network_client(monkeypatch):
    from app.llm.factory import get_llm_provider

    monkeypatch.setenv("LLM_PROVIDER", "disabled")
    with pytest.raises(ValueError, match="inference is disabled"):
        get_llm_provider()
