import logging

from app.extraction.contract_extractor import extract_contract_data
from app.extraction.cv_extractor import extract_cv_data
from app.extraction.invoice_extractor import extract_invoice_data
from app.extraction.llm_extractor import extract_with_llm
from app.extraction.receipt_extractor import extract_receipt_data
from app.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)


def extract_with_rules(text: str, document_type: str):

    if document_type == "cv":
        return extract_cv_data(text)

    if document_type == "invoice":
        return extract_invoice_data(text)

    if document_type == "receipt":
        return extract_receipt_data(text)

    if document_type == "contract":
        return extract_contract_data(text)

    return None


def extract_structured_data(
    text: str,
    document_type: str
) -> tuple[dict | None, str, bool]:

    supported_types = {
        "cv",
        "invoice",
        "receipt",
        "contract"
    }

    if document_type not in supported_types:
        return None, "none", True

    try:
        provider = get_llm_provider()

        structured_data = extract_with_llm(
            text=text,
            document_type=document_type,
            provider=provider
        )

        return structured_data, "llm", False

    except Exception:
        logger.exception(
            "LLM extraction failed for document type '%s'; "
            "using rule-based fallback.",
            document_type,
        )

        fallback_data = extract_with_rules(
            text=text,
            document_type=document_type,
        )

        return fallback_data, "regex_fallback", True