"""Narrow, source-anchored Arabic monetary policy grammar; ambiguity fails closed."""

import re

from app.language.amounts import DIGITS, currency_codes, parse_amount, semantic_text

SCOPES = {
    "meal": r"الوجبات|وجبات|الطعام|المطاعم|وجبة",
    "hotel": r"الفنادق|الفندق|فنادق|الاقامة|الإقامة",
    "ground_transportation": r"النقل البري|سيارات الاجرة|سيارات الأجرة|التاكسي",
    "purchase": r"المشتريات|الشراء|مستلزمات المكتب",
    "all_expenses": r"جميع المصروفات|كل المصروفات|جميع النفقات",
}


def arabic_policy_check(rule):
    text = semantic_text(rule.source_quote).translate(DIGITS)
    assertion = re.sub(r"لا (?:تقل|تزيد) عن", "", text)
    if rule.action == "policy_violation":
        assertion = assertion.replace("غير مسموح", "")
    if re.search(
        r"\b(?:لا|لن|لم|ليس|ليست|غير|دون|بدون|عدم|باستثناء|إلا|الا|عدا|ماعدا|قد|يمكن)\b|(?:لا|لن|لم)\s*(?:تتطلب|تحتاج|يلزم|يجب|يستلزم|يتطلب)",
        assertion,
    ):
        return {
            "verified": False,
            "reason": "Unsupported exception, negation or discretionary wording.",
        }
    patterns = {
        ">=": r"لا تقل عن|على الاقل|على الأقل|او اكثر|أو أكثر",
        ">": r"تتجاوز|تزيد عن|اكثر من|أكثر من|فوق",
        "<=": r"لا تزيد عن|بحد اقصى|بحد أقصى|على الاكثر|على الأكثر",
        "<": r"(?<!لا )(?:تقل عن|اقل من|أقل من)",
    }
    operators = [op for op, pattern in patterns.items() if re.search(pattern, text)]
    # Avoid treating the positive substring of 'لا تزيد عن' as a strict comparison.
    if "لا تزيد عن" in text and ">" in operators:
        operators.remove(">")
    if operators != [rule.operator]:
        return {
            "verified": False,
            "reason": "Ambiguous or mismatched Arabic comparison.",
        }
    values = re.findall(r"\d[\d,٬]*(?:[.٫]\d+)?", text)
    if (
        len(values) != 1
        or parse_amount(values[0] + " " + rule.currency, rule.currency)
        != rule.threshold
        or currency_codes(rule.source_quote) != {rule.currency}
    ):
        return {
            "verified": False,
            "reason": "Threshold/currency not uniquely supported by source.",
        }
    scopes = [scope for scope, pattern in SCOPES.items() if re.search(pattern, text)]
    if scopes != [rule.category] or rule.field != "total":
        return {"verified": False, "reason": "Unsupported Arabic category or field."}
    actions = []
    if re.search(r"(?:تتطلب|تحتاج|يلزم|يجب).{0,60}موافقة", text):
        actions.append("requires_approval")
    if re.search(
        r"(?:الايصالات|الإيصالات|الفواتير|المستندات الداعمة|الوثائق).{0,60}(?:مطلوبة|مطلوب|الزامية|إلزامية)|(?:يلزم|يجب|تتطلب).{0,40}(?:تقديم|ارفاق|إرفاق).{0,30}(?:ايصال|إيصال|فاتورة|مستندات)",
        text,
    ):
        actions.append("requires_documentation")
    if re.search(r"يحظر|ممنوع|غير مسموح", text):
        actions.append("policy_violation")
    if actions != [rule.action]:
        return {"verified": False, "reason": "Ambiguous or unsupported Arabic action."}
    if rule.action == "requires_approval":
        roles = {
            "manager": r"(?:المدير|مدير)",
            "director": r"مدير الادارة|مدير الإدارة|المدير العام",
        }
        role = rule.approval_role or ""
        if re.search(roles["director"], text) and role != "director":
            return {"verified": False, "reason": "Approval role mismatch."}
        pattern = roles.get(role, re.escape(role))
        if not role or not re.search(pattern, text):
            return {
                "verified": False,
                "reason": "Approval role not supported by Arabic source.",
            }
    elif rule.approval_role is not None:
        return {"verified": False, "reason": "Unexpected approval role."}
    return {
        "verified": True,
        "reason": "Rule matches the supported Arabic source grammar.",
    }
