"""Arabic ingestion foundations; no claim of model/OCR accuracy from mocked OCR."""

from io import BytesIO
from unittest.mock import Mock

import pytest
from PIL import Image

from app.ingestion import ocr
from app.ingestion.safety import extract_text_isolated


def test_utf8_arabic_text_survives_real_bounded_parser():
    source = "إيصال تجريبي\nالمجموع: ١٧٥٫٥٠ ج.م\nInvoice رقم ٢٠٢٦"
    assert extract_text_isolated(source.encode("utf-8"), "txt") == (
        source,
        "txt_decoder",
    )


def test_native_arabic_docx_survives_real_bounded_parser():
    from docx import Document

    source = "فاتورة تجريبية من مطعم النيل، الإجمالي ١٧٥٫٥٠ جنيه"
    document = Document()
    document.add_paragraph(source)
    output = BytesIO()
    document.save(output)
    assert extract_text_isolated(output.getvalue(), "docx") == (source, "docx_parser")


def test_arabic_ocr_explicitly_uses_both_languages_and_timeout(monkeypatch):
    monkeypatch.setenv("EDI_OCR_LANGUAGES", "eng+ara")
    monkeypatch.setattr(
        ocr.pytesseract, "get_languages", lambda **kwargs: ["eng", "ara"]
    )
    read = Mock(return_value="إيصال تجريبي ١٧٥")
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", read)
    image = BytesIO()
    Image.new("RGB", (40, 40), "white").save(image, format="PNG")
    assert ocr.extract_image_text(image.getvalue()) == "إيصال تجريبي ١٧٥"
    assert read.call_args.kwargs == {"lang": "eng+ara", "timeout": 5}


def test_missing_arabic_pack_is_explicit_instead_of_silent_english_fallback(
    monkeypatch,
):
    monkeypatch.setenv("EDI_OCR_LANGUAGES", "eng+ara")
    monkeypatch.setattr(ocr.pytesseract, "get_languages", lambda **kwargs: ["eng"])
    with pytest.raises(ValueError, match="language packs"):
        ocr.ocr_languages()
