import re

from app.language.fields import arabic_fields, date_value, labeled, labeled_amount


def extract_receipt_data(text: str) -> dict:
    if re.search(r"(?:الإجمالي|الاجمالي|التاجر|طريقة الدفع)\s*[:：]", text):
        return arabic_fields(text, "receipt")
    data = {
        "merchant": None,
        "date": None,
        "total": None,
        "payment_method": None
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if lines:
        data["merchant"] = lines[0]

    labeled_date = labeled(text, "date|receipt date")
    date_match = re.search(
        r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b",
        text
    )

    if date_match:
        data["date"] = date_value(date_match.group(1))
    if labeled_date:
        data["date"] = date_value(labeled_date)

    lower_text = text.lower()

    if "visa" in lower_text:
        data["payment_method"] = "visa"

    elif "mastercard" in lower_text:
        data["payment_method"] = "mastercard"

    elif "cash" in lower_text:
        data["payment_method"] = "cash"

    data["total"] = labeled_amount(text, "total|grand total", retain_usd=False)
    data["expense_category"] = labeled(text, "expense category|category")
    return data
