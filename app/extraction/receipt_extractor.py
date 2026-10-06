import re


def extract_receipt_data(text: str) -> dict:
    data = {
        "merchant": None,
        "date": None,
        "total": None,
        "payment_method": None
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if lines:
        data["merchant"] = lines[0]

    date_match = re.search(
        r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b",
        text
    )

    if date_match:
        data["date"] = date_match.group(1)

    total_match = re.search(
        r"(?:total|grand total)\s*[:\-]?\s*[$€£]?\s*([0-9,]+(?:\.[0-9]{2})?)",
        text,
        re.IGNORECASE
    )

    if total_match:
        data["total"] = total_match.group(1)

    lower_text = text.lower()

    if "visa" in lower_text:
        data["payment_method"] = "visa"

    elif "mastercard" in lower_text:
        data["payment_method"] = "mastercard"

    elif "cash" in lower_text:
        data["payment_method"] = "cash"

    return data