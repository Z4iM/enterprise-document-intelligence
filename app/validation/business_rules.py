from decimal import Decimal, InvalidOperation

# Baseline rules from our employee policy.
# Later these should come from versioned policy configuration.
MEAL_LIMIT = Decimal("100.00")
RECEIPT_THRESHOLD = Decimal("25.00")


def parse_money(value) -> Decimal | None:
    """
    Convert monetary values into Decimal.

    Examples:
        "$175"    -> Decimal("175")
        "$15.06"  -> Decimal("15.06")
        100       -> Decimal("100")
    """

    if value is None or isinstance(value, bool):
        return None

    cleaned = (
        str(value)
        .replace("$", "")
        .replace(",", "")
        .strip()
    )

    try:
        amount = Decimal(cleaned)

        if not amount.is_finite() or amount < 0:
            return None

        return amount

    except InvalidOperation:
        return None


def evaluate_expense_rules(
    structured_data: dict
) -> dict:

    amount = parse_money(
        structured_data.get("total")
    )

    category = str(
        structured_data.get("expense_category") or ""
    ).strip().lower()

    if amount is None:
        return {
            "status": "needs_review",
            "summary": "Missing or invalid expense amount.",
            "violations": [],
            "required_actions": [],
            "checks": []
        }

    checks = []
    required_actions = []

    # ------------------------------------------
    # RULE 1: Meal reimbursement
    # ------------------------------------------

    if category == "meal":

        exceeds_limit = amount > MEAL_LIMIT

        checks.append({
            "rule": "4.1 Meals",
            "amount": str(amount),
            "limit": str(MEAL_LIMIT),
            "exceeds_limit": exceeds_limit
        })

        if exceeds_limit:
            required_actions.append(
                "Manager approval required before "
                "meal reimbursement."
            )

    # ------------------------------------------
    # RULE 2: Receipt documentation
    # ------------------------------------------

    receipt_required = (
        amount >= RECEIPT_THRESHOLD
    )

    checks.append({
        "rule": "4.4 Receipts and Missing Documentation",
        "amount": str(amount),
        "threshold": str(RECEIPT_THRESHOLD),
        "receipt_required": receipt_required
    })

    # Important:
    # Receipt required does NOT mean receipt missing.
    # We cannot assume documentation is missing.

    # ------------------------------------------
    # Determine decision
    # ------------------------------------------

    if category != "meal":
        status = "needs_review"
        summary = (
            "Receipt threshold checked, but category-specific "
            "reimbursement rules have not been evaluated."
        )

    elif required_actions:
        status = "requires_approval"
        summary = (
            "Meal expense exceeds the standard "
            "reimbursement limit."
        )

    else:
        status = "compliant"
        summary = (
            "Meal expense is within the standard "
            "reimbursement limit. Any required receipt "
            "documentation must still be verified."
        )

    return {
        "status": status,
        "summary": summary,
        "violations": [],
        "required_actions": required_actions,
        "checks": checks
    }