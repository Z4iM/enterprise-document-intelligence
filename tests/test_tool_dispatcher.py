
from unittest.mock import Mock

import pytest

from app.agents import tool_dispatcher as dispatcher


def call_tool(
    name,
    args,
    db=None,
    allowed_documents=None,
    allowed_policies=None,
):
    return dispatcher.dispatch_tool_call(
        name=name,
        args=args,
        allowed_document_ids=(
            {"doc-001"}
            if allowed_documents is None
            else allowed_documents
        ),
        allowed_policy_ids=(
            {"policy-001"}
            if allowed_policies is None
            else allowed_policies
        ),
        db=db if db is not None else Mock(),
    )


def test_unknown_tool_is_rejected():
    db = Mock()

    result = call_tool(
        "delete_document",
        {"document_id": "doc-001"},
        db=db,
    )

    assert result == {"status": "unknown_tool"}
    db.get.assert_not_called()
    db.execute.assert_not_called()


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("inspect_document", {}),
        (
            "inspect_document",
            {"document_id": "doc-001", "extra": True},
        ),
        ("inspect_document", {"document_id": None}),
        ("inspect_document", {"document_id": "   "}),
        ("inspect_document", {"document_id": "x" * 129}),
        ("inspect_document", []),
        ("get_policy_evidence", {}),
        ("get_policy_evidence", {"policy_id": 123}),
        (
            "evaluate_document_policy",
            {"document_id": "doc-001"},
        ),
        (
            "evaluate_document_policy",
            {
                "document_id": "doc-001",
                "policy_id": "policy-001",
                "allowed_document_ids": ["doc-001"],
            },
        ),
    ],
)
def test_invalid_arguments_are_rejected(name, args):
    db = Mock()

    result = call_tool(name, args, db=db)

    assert result == {"status": "invalid_arguments"}

    db.get.assert_not_called()
    db.execute.assert_not_called()


@pytest.mark.parametrize(
    ("name", "args", "allowed_documents", "allowed_policies"),
    [
        (
            "inspect_document",
            {"document_id": "private-doc"},
            {"doc-001"},
            {"policy-001"},
        ),
        (
            "get_policy_evidence",
            {"policy_id": "private-policy"},
            {"doc-001"},
            {"policy-001"},
        ),
        (
            "evaluate_document_policy",
            {
                "document_id": "private-doc",
                "policy_id": "policy-001",
            },
            {"doc-001"},
            {"policy-001"},
        ),
        (
            "evaluate_document_policy",
            {
                "document_id": "doc-001",
                "policy_id": "private-policy",
            },
            {"doc-001"},
            {"policy-001"},
        ),
    ],
)
def test_unauthorized_resources_never_reach_database(
    name,
    args,
    allowed_documents,
    allowed_policies,
):
    db = Mock()

    result = call_tool(
        name,
        args,
        db=db,
        allowed_documents=allowed_documents,
        allowed_policies=allowed_policies,
    )

    assert result == {"status": "access_denied"}

    db.get.assert_not_called()
    db.execute.assert_not_called()


@pytest.mark.parametrize(
    ("name", "args", "function_name"),
    [
        (
            "inspect_document",
            {"document_id": "doc-001"},
            "inspect_document",
        ),
        (
            "get_policy_evidence",
            {"policy_id": "policy-001"},
            "get_policy_evidence",
        ),
        (
            "evaluate_document_policy",
            {
                "document_id": "doc-001",
                "policy_id": "policy-001",
            },
            "evaluate_document_policy",
        ),
    ],
)
def test_dispatcher_routes_to_correct_tool(
    monkeypatch,
    name,
    args,
    function_name,
):
    db = Mock()

    functions = {
        "inspect_document": Mock(
            return_value={"status": "ready"},
        ),
        "get_policy_evidence": Mock(
            return_value={"status": "ready"},
        ),
        "evaluate_document_policy": Mock(
            return_value={"status": "requires_approval"},
        ),
    }

    for function, mock in functions.items():
        monkeypatch.setattr(dispatcher, function, mock)

    result = call_tool(name, args, db=db)

    expected_arguments = {
        **args,
        "db": db,
    }

    if "document_id" in args:
        expected_arguments["allowed_document_ids"] = {"doc-001"}

    if "policy_id" in args:
        expected_arguments["allowed_policy_ids"] = {"policy-001"}

    functions[function_name].assert_called_once_with(
        **expected_arguments
    )

    for function, mock in functions.items():
        if function != function_name:
            mock.assert_not_called()

    assert result == functions[function_name].return_value
