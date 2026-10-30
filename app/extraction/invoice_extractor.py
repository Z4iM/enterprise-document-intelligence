import re

from app.language.fields import arabic_fields, date_value, labeled, labeled_amount


def extract_invoice_data(text: str) -> dict:
    if re.search(r"(?:رقم الفاتورة|المورد|المبلغ المستحق)\s*[:：]", text):
        return arabic_fields(text, "invoice")
    data = {
        "invoice_number": None,
        "vendor": None,
        "total": None,
        "due_date": None
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    invoice_match = re.search(
        r"^invoice\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Za-z0-9\-]+)\s*$",
        text,
        re.IGNORECASE | re.MULTILINE
    )

    if invoice_match:
        data["invoice_number"] = invoice_match.group(1)

    if lines:
        data["vendor"] = lines[0]

    data["total"] = labeled_amount(text, "total|amount due", retain_usd=False)
    data["invoice_date"] = date_value(labeled(text, "invoice date"))
    data["due_date"] = date_value(labeled(text, "due date"))
    data["expense_category"] = labeled(text, "expense category|category")
    return data
