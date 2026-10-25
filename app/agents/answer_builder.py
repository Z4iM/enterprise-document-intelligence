
ACTION_LABELS = {
    "requires_approval": "Approval required",
    "requires_documentation": "Documentation required",
    "policy_violation": "Policy violation identified",
}

OUTCOME_MESSAGES = {
    "passed": (
        "No additional requirements were triggered "
        "by the evaluated approved rules."
    ),
    "requires_approval": (
        "Approval is required before reimbursement."
    ),
    "requires_documentation": (
        "Supporting documentation is required."
    ),
    "policy_violation": (
        "An evaluated policy rule identified a violation."
    ),
    "needs_review": (
        "Additional review is required."
    ),
}


def build_evidence_backed_answer(investigation: dict) -> dict:
    """
    Construct a user-facing answer from trusted evaluation
    results, never from the unverified Gemini draft.
    """

    if investigation.get("status") != "completed":
        return {
            "status": "not_ready",
            "reason": "investigation_incomplete",
        }

    policy = investigation.get("policy_result")

    if not isinstance(policy, dict):
        return {
            "status": "not_ready",
            "reason": "missing_policy_result",
        }

    evaluation = policy.get("evaluation")

    if not isinstance(evaluation, dict):
        return {
            "status": "not_ready",
            "reason": "missing_evaluation",
        }

    outcome = policy.get("status")

    if (
        outcome not in OUTCOME_MESSAGES
        or evaluation.get("status") != outcome
        or policy.get("coverage") != "approved_rules_only"
        or policy.get("full_compliance_certified") is not False
    ):
        return {
            "status": "not_ready",
            "reason": "invalid_evaluation",
        }

    raw_evidence = policy.get("evidence")
    raw_actions = evaluation.get("required_actions")

    if not isinstance(raw_evidence, list) or not isinstance(
        raw_actions, list
    ):
        return {
            "status": "not_ready",
            "reason": "missing_evidence",
        }

    evidence_by_rule = {}

    for item in raw_evidence:
        if not isinstance(item, dict):
            continue

        rule_id = item.get("rule_id")
        source_quote = item.get("source_quote")

        if (
            isinstance(rule_id, str)
            and isinstance(source_quote, str)
            and source_quote.strip()
        ):
            evidence_by_rule[rule_id] = item

    actions = []

    for item in raw_actions:
        if not isinstance(item, dict):
            return {
                "status": "not_ready",
                "reason": "invalid_action",
            }

        rule_id = item.get("rule_id")
        action = item.get("action")
        source = evidence_by_rule.get(rule_id)

        if action not in ACTION_LABELS or source is None:
            return {
                "status": "not_ready",
                "reason": "missing_action_evidence",
            }

        actions.append({
            "rule_id": rule_id,
            "requirement": ACTION_LABELS[action],
            "source_quote": source["source_quote"],
            "source_chunk_id": source.get("source_chunk_id"),
        })

    if outcome in ACTION_LABELS and not actions:
        return {
            "status": "not_ready",
            "reason": "missing_required_actions",
        }

    return {
        "status": "ready",
        "document_id": policy.get("document_id"),
        "policy_id": policy.get("policy_id"),
        "policy_outcome": outcome,
        "summary": OUTCOME_MESSAGES[outcome],
        "required_actions": actions,
        "coverage": "approved_rules_only",
        "full_compliance_certified": False,
        "notice": (
            "This evaluates only verified, approved policy "
            "rules. It does not certify full compliance "
            "or authorize reimbursement."
        ),
    }
