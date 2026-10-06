import re


def extract_invoice_data(text: str) -> dict:
    data = {
        "invoice_number": None,
        "vendor": None,
        "total": None,
        "due_date": None
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    invoice_match = re.search(
        r"(?:invoice\s*(?:number|no|#)?\s*[:\-]?\s*)([A-Za-z0-9\-]+)",
        text,
        re.IGNORECASE
    )

    if invoice_match:
        data["invoice_number"] = invoice_match.group(1)

    total_match = re.search(
        r"(?:total|amount due)\s*[:\-]?\s*[$€£]?\s*([0-9,]+(?:\.[0-9]{2})?)",
        text,
        re.IGNORECASE
    )

    if total_match:
        data["total"] = total_match.group(1)

    due_date_match = re.search(
        r"(?:due date)\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        text,
        re.IGNORECASE
    )

    if due_date_match:
        data["due_date"] = due_date_match.group(1)

    if lines:
        data["vendor"] = lines[0]

    return data