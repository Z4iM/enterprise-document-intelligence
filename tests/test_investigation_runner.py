
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import types

from app.agents import investigation_runner as runner


def tool_reply(name, args):
    """Simulate Gemini requesting one function."""
    part = types.Part.from_function_call(
        name=name,
        args=args,
    )

    return SimpleNamespace(
        function_calls=[part.function_call],
        candidates=[
            SimpleNamespace(
                content=types.Content(
                    role="model",
                    parts=[part],
                )
            )
        ],
        text=None,
    )


def text_reply(answer):
    """Simulate Gemini answering without requesting tools."""
    return SimpleNamespace(
        function_calls=[],
        candidates=[],
        text=answer,
    )


def fake_client(*responses):
    client = Mock()
    client.models.generate_content.side_effect = list(responses)
    return client


def investigate(
    client,
    *,
    question="Can I reimburse this receipt?",
    documents=None,
    policies=None,
    db=None,
):
    return runner.run_investigation(
        question=question,
        client=client,
        model="synthetic-test-model",
        allowed_document_ids=(
            {"doc-001"} if documents is None else documents
        ),
        allowed_policy_ids=(
            {"policy-001"} if policies is None else policies
        ),
        db=Mock() if db is None else db,
    )


@pytest.mark.parametrize(
    "question",
    ["", "   ", "x" * 1501],
)
def test_invalid_questions_are_rejected(question):
    client = Mock()

    with pytest.raises(ValueError):
        investigate(client, question=question)

    client.models.generate_content.assert_not_called()


@pytest.mark.parametrize(
    ("documents", "policies"),
    [
        (set(), {"policy-001"}),
        ({"doc-001"}, set()),
    ],
)
def test_empty_authorized_scope_blocks_execution(
    documents,
    policies,
):
    client = Mock()

    result = investigate(
        client,
        documents=documents,
        policies=policies,
    )

    assert result == {"status": "no_authorized_scope"}
    client.models.generate_content.assert_not_called()


def test_model_answer_without_evaluation_is_not_verified():
    client = fake_client(
        text_reply("Everything is approved!")
    )

    result = investigate(client)

    assert result["status"] == "insufficient_evidence"
    assert result["tool_trace"] == []
    assert "policy_result" not in result
    assert "model_draft_unverified" not in result


def test_successful_evaluation_returns_authoritative_result(
    monkeypatch,
):
    policy_result = {
        "status": "requires_approval",
        "evaluation": {
            "status": "requires_approval",
            "rules_evaluated": 2,
        },
        "evidence": [
            {
                "rule_id": "meal-rule",
                "source_quote": (
                    "Meals above $100 require manager approval."
                ),
            }
        ],
        "coverage": "approved_rules_only",
        "full_compliance_certified": False,
    }

    dispatcher = Mock(return_value=policy_result)

    monkeypatch.setattr(
        runner,
        "dispatch_tool_call",
        dispatcher,
    )

    client = fake_client(
        tool_reply(
            "evaluate_document_policy",
            {
                "document_id": "doc-001",
                "policy_id": "policy-001",
            },
        ),
        text_reply(
            "Manager approval and receipt documentation "
            "are required."
        ),
    )

    db = Mock()
    result = investigate(client, db=db)

    assert result["status"] == "completed"
    assert result["policy_result"] == policy_result

    assert result["model_draft_unverified"].startswith(
        "Manager approval"
    )

    assert result["tool_trace"] == [
        {
            "tool": "evaluate_document_policy",
            "status": "requires_approval",
        }
    ]

    dispatcher.assert_called_once_with(
        name="evaluate_document_policy",
        args={
            "document_id": "doc-001",
            "policy_id": "policy-001",
        },
        allowed_document_ids={"doc-001"},
        allowed_policy_ids={"policy-001"},
        db=db,
    )

    assert client.models.generate_content.call_count == 2

    first_request = (
        client.models.generate_content.call_args_list[0]
    )

    config = first_request.kwargs["config"]

    assert config.automatic_function_calling.disable is True

    second_request = (
        client.models.generate_content.call_args_list[1]
    )

    history = second_request.kwargs["contents"]

    assert history[-1].role == "user"

    function_result = history[-1].parts[0].function_response

    assert function_result.name == "evaluate_document_policy"
    assert function_result.response["result"] == policy_result


def test_unauthorized_document_blocks_investigation():
    db = Mock()

    client = fake_client(
        tool_reply(
            "inspect_document",
            {"document_id": "private-document"},
        )
    )

    result = investigate(client, db=db)

    assert result["status"] == "blocked"
    assert result["tool_trace"][0]["status"] == (
        "access_denied"
    )

    db.get.assert_not_called()
    db.execute.assert_not_called()

    assert client.models.generate_content.call_count == 1


@pytest.mark.parametrize(
    ("name", "args", "expected_status"),
    [
        (
            "delete_document",
            {"document_id": "doc-001"},
            "unknown_tool",
        ),
        (
            "inspect_document",
            {
                "document_id": "doc-001",
                "allowed_document_ids": ["doc-001"],
            },
            "invalid_arguments",
        ),
    ],
)
def test_unsafe_tool_requests_are_rejected(
    name,
    args,
    expected_status,
):
    db = Mock()

    client = fake_client(tool_reply(name, args))

    result = investigate(client, db=db)

    assert result["status"] == "blocked"
    assert result["tool_trace"][0]["status"] == (
        expected_status
    )

    db.get.assert_not_called()
    db.execute.assert_not_called()


def test_human_review_requirement_stops_agent(monkeypatch):
    dispatcher = Mock(
        return_value={
            "status": "needs_review",
            "reason": "document_not_verified",
        }
    )

    monkeypatch.setattr(
        runner,
        "dispatch_tool_call",
        dispatcher,
    )

    client = fake_client(
        tool_reply(
            "inspect_document",
            {"document_id": "doc-001"},
        )
    )

    result = investigate(client)

    assert result["status"] == "needs_review"
    assert client.models.generate_content.call_count == 1


def test_excessive_tool_requests_are_rejected():
    parts = [
        types.Part.from_function_call(
            name="inspect_document",
            args={"document_id": "doc-001"},
        )
        for _ in range(runner.MAX_TOOL_CALLS + 1)
    ]

    response = SimpleNamespace(
        function_calls=[
            part.function_call for part in parts
        ],
        candidates=[
            SimpleNamespace(
                content=types.Content(
                    role="model",
                    parts=parts,
                )
            )
        ],
        text=None,
    )

    client = fake_client(response)
    db = Mock()

    result = investigate(client, db=db)

    assert result["status"] == "tool_limit_reached"
    assert result["tool_trace"] == []

    db.get.assert_not_called()


def test_oversized_tool_results_are_rejected(monkeypatch):
    dispatcher = Mock(
        return_value={
            "status": "ready",
            "data": "x" * 15000,
        }
    )

    monkeypatch.setattr(
        runner,
        "dispatch_tool_call",
        dispatcher,
    )

    client = fake_client(
        tool_reply(
            "inspect_document",
            {"document_id": "doc-001"},
        )
    )

    result = investigate(client)

    assert result["status"] == "tool_result_too_large"
    assert client.models.generate_content.call_count == 1


def test_missing_model_content_is_rejected():
    response = SimpleNamespace(
        function_calls=[
            types.FunctionCall(
                name="inspect_document",
                args={"document_id": "doc-001"},
            )
        ],
        candidates=[],
        text=None,
    )

    client = fake_client(response)

    result = investigate(client)

    assert result["status"] == "invalid_model_response"

def test_function_call_id_is_preserved(monkeypatch):
    policy_result = {
        "status": "requires_approval",
        "evaluation": {"status": "requires_approval"},
    }

    monkeypatch.setattr(
        runner,
        "dispatch_tool_call",
        Mock(return_value=policy_result),
    )

    tool_request = tool_reply(
        "evaluate_document_policy",
        {
            "document_id": "doc-001",
            "policy_id": "policy-001",
        },
    )

    tool_request.function_calls[0].id = "call-001"

    client = fake_client(
        tool_request,
        text_reply("Manager approval required."),
    )

    result = investigate(client)

    assert result["status"] == "completed"

    history = (
        client.models.generate_content
        .call_args_list[1]
        .kwargs["contents"]
    )

    function_response = (
        history[-1].parts[0].function_response
    )

    assert function_response.id == "call-001"
