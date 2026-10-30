"""Synthetic conservative Arabic/English extraction and monetary-policy contracts."""

import pytest

from app.classification.classifier import classify_document
from app.extraction.receipt_extractor import extract_receipt_data
from app.language.amounts import parse_amount
from app.language.fields import date_value
from app.validation.rule_schemas import PolicyRule
from app.validation.source_verifier import verify_rule


@pytest.mark.parametrize(
    "raw,currency,expected",
    [
        ("١٬٢٣٤٫٥٠ جنيه مصري", "EGP", "1234.50"),
        ("۱۷۵٫۵۰ SAR", "SAR", "175.50"),
        ("$1,000.25", "USD", "1000.25"),
        ("175,50", "USD", None),
        ("١٧٥ دولار", "USD", None),
        ("175 EUR", "USD", None),
        (True, "USD", None),
        ("1,2,3", "USD", None),
        ("NaN", "USD", None),
    ],
)
def test_money_parser_never_guesses_currency_or_ambiguous_separators(
    raw, currency, expected
):
    value = parse_amount(raw, currency)
    assert (str(value) if value is not None else None) == expected


def test_arabic_receipt_fallback_preserves_merchant_and_abstains_on_duplicates():
    text = "إيصال\nالتاجر: مطعم تجريبي\nالتاريخ: ٢٠٢٦-١٠-٣٠\nالإجمالي: ١٧٥٫٥٠ جنيه مصري\nطريقة الدفع: نقدا\nالفئة: وجبات"
    result = extract_receipt_data(text)
    assert result["merchant"] == "مطعم تجريبي"
    assert result["date"] == "2026-10-30" and result["total"] == "175.50 EGP"
    assert classify_document(text)[0] == "receipt"
    assert extract_receipt_data(text + "\nالإجمالي: ٢٠٠ جنيه مصري")["total"] is None
    assert date_value("٠١/٠٢/٢٠٢٦") is None


def arabic_rule(**changes):
    values = {
        "rule_id": "synthetic",
        "source_chunk_id": "synthetic-chunk",
        "category": "meal",
        "field": "total",
        "operator": ">",
        "threshold": "100",
        "currency": "EGP",
        "action": "requires_approval",
        "approval_role": "manager",
        "source_quote": "مصروفات الوجبات التي تتجاوز ١٠٠ جنيه مصري تتطلب موافقة المدير.",
    }
    values.update(changes)
    return PolicyRule(**values)


def test_arabic_source_verified_without_changing_quotation():
    rule = arabic_rule()
    assert verify_rule(rule, rule.source_quote)["verified"]
    assert "١٠٠" in rule.source_quote


@pytest.mark.parametrize(
    "changes",
    [
        {"currency": "USD"},
        {"threshold": "101"},
        {"operator": ">="},
        {"category": "hotel"},
        {"approval_role": "director"},
        {
            "source_quote": "مصروفات الوجبات التي تتجاوز ١٠٠ جنيه مصري لا تتطلب موافقة المدير."
        },
        {
            "source_quote": "مصروفات الوجبات التي تتجاوز ١٠٠ أو ٢٠٠ جنيه مصري تتطلب موافقة المدير."
        },
        {"source_quote": "الوجبات تتطلب موافقة المدير."},
    ],
)
def test_arabic_mismatches_and_ambiguity_fail_closed(changes):
    rule = arabic_rule(**changes)
    assert not verify_rule(rule, rule.source_quote)["verified"]


@pytest.mark.parametrize(
    "wording", ["لا تحتاج", "لن تحتاج", "لا يلزم", "لاتتطلب", "تحتاج بدون"]
)
def test_arabic_negated_approval_variants_never_become_positive_rules(wording):
    rule = arabic_rule(
        source_quote=f"مصروفات الوجبات التي تتجاوز ١٠٠ جنيه مصري {wording} موافقة المدير."
    )
    assert not verify_rule(rule, rule.source_quote)["verified"]


@pytest.mark.parametrize("phrase,operator", [("لا تقل عن", ">="), ("لا تزيد عن", "<=")])
def test_arabic_negative_comparison_is_distinct_from_negated_requirement(
    phrase, operator
):
    rule = arabic_rule(
        operator=operator,
        source_quote=f"مصروفات الوجبات التي {phrase} ١٠٠ جنيه مصري تتطلب موافقة المدير.",
    )
    assert verify_rule(rule, rule.source_quote)["verified"]


@pytest.mark.parametrize(
    "quote",
    [
        "No meals above $100 require manager approval.",
        "Meals above $100 never require manager approval.",
        "Meals above $1,00 require manager approval.",
        "Meals above $100.0O require manager approval.",
    ],
)
def test_english_negation_and_ambiguous_source_amounts_fail_closed(quote):
    rule = arabic_rule(currency="USD", source_quote=quote)
    assert not verify_rule(rule, quote)["verified"]
