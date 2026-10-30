"""Finite monetary parsing without currency conversion or ambiguous decimal guessing."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
CURRENCIES = {
    "USD": r"\$|\bUSD\b|دولار\s+أمريكي|دولار\s+امريكي",
    "EUR": r"€|\bEUR\b|يورو",
    "GBP": r"£|\bGBP\b|جنيه\s+إسترليني|جنيه\s+استرليني",
    "EGP": r"\bEGP\b|جنيه\s+مصري|ج\.\s*م\.?",
    "SAR": r"\bSAR\b|ريال\s+سعودي|ر\.\s*س\.?",
    "AED": r"\bAED\b|درهم\s+إماراتي|درهم\s+اماراتي",
}


def semantic_text(text: str) -> str:
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKC", text).casefold()
            if not unicodedata.combining(c) and c != "ـ"
        ).split()
    )


def currency_codes(text: str) -> set[str]:
    return {
        code
        for code, pattern in CURRENCIES.items()
        if re.search(pattern, text, re.IGNORECASE)
    }


def parse_amount(value, expected_currency="USD") -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().translate(DIGITS)
    if len(text) > 100:
        return None
    codes = currency_codes(text)
    if not codes and expected_currency.upper() != "USD":
        return None
    if codes and codes != {expected_currency.upper()}:
        return None
    for pattern in CURRENCIES.values():
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
    # Exactly grouped thousands; decimal comma and unknown currency words abstain.
    if not re.fullmatch(r"[+-]?(?:\d{1,3}(?:[,٬]\d{3})+|\d+)(?:[.٫]\d{1,2})?", text):
        return None
    try:
        number = Decimal(text.replace(",", "").replace("٬", "").replace("٫", "."))
        return number if number.is_finite() and abs(number) < Decimal("1e18") else None
    except InvalidOperation:
        return None
