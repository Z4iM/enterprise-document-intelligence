def classify_document(text: str) -> tuple[str, float]:
    text = text.lower()

    keyword_groups = {
        "cv": [
            "education",
            "experience",
            "skills",
            "curriculum vitae",
            "resume",
        ],
        "invoice": [
            "invoice",
            "invoice number",
            "subtotal",
            "amount due",
            "bill to",
        ],
        "receipt": [
            "receipt",
            "total",
            "cash",
            "change",
            "payment",
        ],
        "contract": [
            "agreement",
            "contract",
            "party",
            "terms and conditions",
            "signature",
        ],
    }

    if any("\u0621" <= char <= "\u064a" for char in text):
        keyword_groups["invoice"] = ["فاتورة", "رقم الفاتورة", "المبلغ المستحق", "المورد"]
        keyword_groups["receipt"] = ["إيصال", "ايصال", "التاجر", "طريقة الدفع", "الإجمالي"]

    scores = {
        "cv": 0,
        "invoice": 0,
        "receipt": 0,
        "contract": 0,
    }
    


    for document_type, keywords in keyword_groups.items():
        for keyword in keywords:
            if keyword in text:
                scores[document_type] += 1

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score == 0:
        return "unknown", 0.0

    total_possible = len(keyword_groups[best_type])

    confidence = best_score / total_possible

    return best_type, round(confidence, 2)

def get_review_status(confidence: float) -> str:
    if confidence >= 0.7:
        return "auto_accepted"

    return "needs_review"
