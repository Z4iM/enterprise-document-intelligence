
from copy import deepcopy

import pytest

from app.agents.answer_builder import build_evidence_backed_answer


@pytest.fixture
def investigation():
    """Synthetic completed investigation with verified evidence."""
    return {
        "status": "completed",
        "model_draft_unverified": "Manager approval is required.",
        "policy_result": {
            "status": "requires_approval",
            "document_id": "doc-001",
            "policy_id": "policy-001",
            "coverage": "approved_rules_only",
            "full_compliance_certified": False,
            "evaluation": {
                "status": "requires_approval",
                "required_actions": [
                    {
                        "rule_id": "meal-rule",
                        "action": "requires_approval",
                    },
                    {
                        "rule_id": "receipt-rule",
                        "action": "requires_documentation",
                    },
                ],
            },
            "evidence": [
                {
                    "rule_id": "meal-rule",
                    "source_quote": (
                        "Meals above $100 require manager approval."
                    ),
                    "source_chunk_id": "chunk-001",
                },
                {
                    "rule_id": "receipt-rule",
                    "source_quote": (
                        "Expenses of $25 or more require receipts."
                    ),
                    "source_chunk_id": "chunk-002",
                },
            ],
        },
    }


def test_valid_evidence_produces_correct_answer(investigation):
    result = build_evidence_backed_answer(investigation)

    assert result["status"] == "ready"
    assert result["policy_outcome"] == "requires_approval"
    assert result["document_id"] == "doc-001"
    assert result["policy_id"] == "policy-001"
    assert result["full_compliance_certified"] is False

    actions = result["required_actions"]

    assert len(actions) == 2
    assert actions[0]["requirement"] == "Approval required"
    assert actions[1]["requirement"] == "Documentation required"

    assert actions[0]["source_chunk_id"] == "chunk-001"
    assert actions[1]["source_chunk_id"] == "chunk-002"
    assert "full compliance" in result["notice"]


def test_gemini_hallucination_cannot_override_decision(investigation):
    investigation["model_draft_unverified"] = (
        "Your expense is fully approved and already reimbursed."
    )

    result = build_evidence_backed_answer(investigation)

    assert result["status"] == "ready"
    assert result["policy_outcome"] == "requires_approval"
    assert "approved and already reimbursed" not in str(result)


@pytest.mark.parametrize(
    "status",
    ["blocked", "needs_review", "tool_limit_reached"],
)
def test_incomplete_investigations_are_rejected(
    investigation,
    status,
):
    investigation["status"] = status

    result = build_evidence_backed_answer(investigation)

    assert result == {
        "status": "not_ready",
        "reason": "investigation_incomplete",
    }


def test_missing_policy_result_is_rejected(investigation):
    del investigation["policy_result"]

    result = build_evidence_backed_answer(investigation)

    assert result["status"] == "not_ready"
    assert result["reason"] == "missing_policy_result"


def test_missing_evaluation_is_rejected(investigation):
    del investigation["policy_result"]["evaluation"]

    result = build_evidence_backed_answer(investigation)

    assert result["status"] == "not_ready"
    assert result["reason"] == "missing_evaluation"


def test_contradictory_decision_is_rejected(investigation):
    investigation["policy_result"]["evaluation"]["status"] = "passed"

    result = build_evidence_backed_answer(investigation)

    assert result["status"] == "not_ready"
    assert result["reason"] == "invalid_evaluation"


def test_unsupported_coverage_is_rejected(investigation):
    investigation["policy_result"]["coverage"] = "full_policy"

    result = build_evidence_backed_answer(investigation)

    assert result["status"] == "not_ready"
    assert result["reason"] == "invalid_evaluation"


def test_full_compliance_claim_is_rejected(investigation):
    investigation["policy_result"]["full_compliance_certified"] = True

    result = build_evidence_backed_answer(investigation)

    assert result["status"] == "not_ready"
    assert result["reason"] == "invalid_evaluation"


def test_missing_action_evidence_is_rejected(investigation):
    investigation["policy_result"]["evidence"].pop()

    result = build_evidence_backed_answer(investigation)

    assert result["status"] == "not_ready"
    assert result["reason"] == "missing_action_evidence"


def test_unknown_action_is_rejected(investigation):
    investigation["policy_result"]["evaluation"][
        "required_actions"
    ][0]["action"] = "automatically_reimburse"

    result = build_evidence_backed_answer(investigation)

    assert result["status"] == "not_ready"


def test_missing_required_actions_is_rejected(investigation):
    del investigation["policy_result"]["evaluation"][
        "required_actions"
    ]

    result = build_evidence_backed_answer(investigation)

    assert result["status"] == "not_ready"
    assert result["reason"] == "missing_evidence"


def test_approval_outcome_requires_actions(investigation):
    investigation["policy_result"]["evaluation"][
        "required_actions"
    ] = []

    result = build_evidence_backed_answer(investigation)

    assert result["status"] == "not_ready"
    assert result["reason"] == "missing_required_actions"


def test_passed_means_only_approved_rules_passed(investigation):
    data = deepcopy(investigation)

    data["policy_result"]["status"] = "passed"
    data["policy_result"]["evaluation"]["status"] = "passed"
    data["policy_result"]["evaluation"]["required_actions"] = []

    result = build_evidence_backed_answer(data)

    assert result["status"] == "ready"
    assert result["policy_outcome"] == "passed"
    assert result["required_actions"] == []
    assert result["full_compliance_certified"] is False
    assert result["coverage"] == "approved_rules_only"
