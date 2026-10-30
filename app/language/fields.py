"""Labeled Arabic fields; duplicates and ambiguous dates abstain, never self-approve."""

import re
from datetime import date

from app.language.amounts import DIGITS, currency_codes, parse_amount


def labeled(text, labels):
    values = [
        match.group(1).strip()
        for match in re.finditer(
            rf"^(?:{labels})\s*[:：]\s*(.+)$", text, re.MULTILINE | re.IGNORECASE
        )
    ]
    return values[0] if len(values) == 1 else None


def date_value(value):
    if not value:
        return None
    value = value.translate(DIGITS)
    match = re.fullmatch(r"(\d{4})[-/](\d{2})[-/](\d{2})", value)
    if match:
        parts = tuple(map(int, match.groups()))
    else:
        match = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", value)
        if not match:
            return None
        first, second, year = map(int, match.groups())
        if first > 12 and second <= 12:
            parts = year, second, first
        elif second > 12 and first <= 12:
            parts = year, first, second
        else:
            return None
    try:
        return date(*parts).isoformat()
    except ValueError:
        return None


def labeled_amount(text, labels, *, retain_usd=True):
    total = labeled(text, labels)
    codes = currency_codes(total or "")
    number = (
        parse_amount(total, next(iter(codes)) if len(codes) == 1 else "USD")
        if total
        else None
    )
    amount = (
        (
            format(number, "f")
            + (
                " " + next(iter(codes))
                if len(codes) == 1 and (codes != {"USD"} or retain_usd)
                else ""
            )
        )
        if number is not None
        else None
    )
    return amount


def arabic_fields(text, document_type):
    amount = labeled_amount(text, "الإجمالي|الاجمالي|المجموع|المبلغ المستحق")
    if document_type == "receipt":
        payment = labeled(text, "طريقة الدفع|الدفع")
        return {
            "merchant": labeled(text, "التاجر|المتجر|المطعم"),
            "date": date_value(labeled(text, "التاريخ|تاريخ الإيصال|تاريخ الايصال")),
            "total": amount,
            "payment_method": {
                "نقدا": "cash",
                "نقدًا": "cash",
                "نقدي": "cash",
                "فيزا": "visa",
                "ماستركارد": "mastercard",
            }.get(payment),
            "expense_category": labeled(text, "فئة المصروف|الفئة"),
        }
    return {
        "vendor": labeled(text, "المورد|البائع"),
        "invoice_number": labeled(text, "رقم الفاتورة"),
        "invoice_date": date_value(labeled(text, "تاريخ الفاتورة")),
        "due_date": date_value(labeled(text, "تاريخ الاستحقاق")),
        "total": amount,
        "expense_category": labeled(text, "فئة المصروف|الفئة"),
    }
