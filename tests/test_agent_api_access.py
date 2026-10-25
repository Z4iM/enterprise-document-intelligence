
from unittest.mock import MagicMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents import api as agent_api

URL = "/agent/investigate"

VALID_HEADERS = {
    "x-edi-agent-token": "synthetic-agent-token",
}


@pytest.fixture(autouse=True)
def clear_agent_environment(monkeypatch):
    """Keep tests independent of the developer's .env."""
    for name in (
        "EDI_ENABLE_DEV_AGENT",
        "EDI_DEV_AGENT_TOKEN",
        "EDI_DEV_AGENT_DOCUMENT_IDS",
        "EDI_DEV_AGENT_POLICY_IDS",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def api_app():
    """Register the agent router in an isolated test app."""
    app = FastAPI()
    app.include_router(agent_api.router)
    return app


@pytest.fixture
def configured_env(monkeypatch):
    monkeypatch.setenv("EDI_ENABLE_DEV_AGENT", "true")
    monkeypatch.setenv(
        "EDI_DEV_AGENT_TOKEN",
        "synthetic-agent-token",
    )
    monkeypatch.setenv(
        "EDI_DEV_AGENT_DOCUMENT_IDS",
        "doc-001",
    )
    monkeypatch.setenv(
        "EDI_DEV_AGENT_POLICY_IDS",
        "policy-001",
    )
    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "synthetic-key-not-used",
    )
    monkeypatch.setenv(
        "GEMINI_MODEL",
        "synthetic-model",
    )


def make_request(
    app,
    *,
    headers=None,
    host="127.0.0.1",
    payload=None,
):
    with TestClient(
        app,
        client=(host, 50000),
    ) as client:
        return client.post(
            URL,
            json=(
                {"question": "Can I reimburse this receipt?"}
                if payload is None
                else payload
            ),
            headers=headers or {},
        )


def test_agent_is_disabled_by_default(api_app):
    response = make_request(
        api_app,
        headers=VALID_HEADERS,
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"x-edi-agent-token": "wrong-token"},
    ],
)
def test_missing_or_invalid_token_is_rejected(
    api_app,
    configured_env,
    headers,
):
    response = make_request(
        api_app,
        headers=headers,
    )

    assert response.status_code == 403


def test_remote_requests_are_rejected(
    api_app,
    configured_env,
):
    response = make_request(
        api_app,
        headers=VALID_HEADERS,
        host="192.0.2.10",
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "environment_variable",
    [
        "EDI_DEV_AGENT_DOCUMENT_IDS",
        "EDI_DEV_AGENT_POLICY_IDS",
    ],
)
def test_missing_resource_scope_is_rejected(
    api_app,
    configured_env,
    monkeypatch,
    environment_variable,
):
    monkeypatch.setenv(environment_variable, "")

    response = make_request(
        api_app,
        headers=VALID_HEADERS,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Investigation scope is not configured."
    )


def test_missing_gemini_key_is_rejected(
    api_app,
    configured_env,
    monkeypatch,
):
    monkeypatch.delenv("GEMINI_API_KEY")

    response = make_request(
        api_app,
        headers=VALID_HEADERS,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Gemini is not configured."
    )


@pytest.mark.parametrize(
    "question",
    ["   ", "x" * 1501],
)
def test_invalid_questions_are_rejected(
    api_app,
    configured_env,
    question,
):
    response = make_request(
        api_app,
        headers=VALID_HEADERS,
        payload={"question": question},
    )

    assert response.status_code == 422


def test_successful_request_uses_server_permissions(
    api_app,
    configured_env,
    monkeypatch,
):
    """The caller cannot override authorization with JSON."""

    fake_db = Mock()

    db_context = MagicMock()
    db_context.__enter__.return_value = fake_db

    monkeypatch.setattr(
        agent_api,
        "SessionLocal",
        Mock(return_value=db_context),
    )

    fake_gemini = Mock()
    client_factory = Mock(return_value=fake_gemini)

    monkeypatch.setattr(
        agent_api.genai,
        "Client",
        client_factory,
    )

    expected_result = {
        "status": "ready",
        "answer": {
            "status": "ready",
            "policy_outcome": "requires_approval",
        },
        "tool_trace": [
            {
                "tool": "evaluate_document_policy",
                "status": "requires_approval",
            }
        ],
    }

    investigation = Mock(return_value=expected_result)

    monkeypatch.setattr(
        agent_api,
        "run_verified_investigation",
        investigation,
    )

    response = make_request(
        api_app,
        headers=VALID_HEADERS,
        payload={
            "question": "  Can I reimburse this receipt?  ",
            "allowed_document_ids": ["private-document"],
            "allowed_policy_ids": ["private-policy"],
        },
    )

    assert response.status_code == 200
    assert response.json() == expected_result

    investigation.assert_called_once_with(
        question="Can I reimburse this receipt?",
        client=fake_gemini,
        model="synthetic-model",
        allowed_document_ids={"doc-001"},
        allowed_policy_ids={"policy-001"},
        db=fake_db,
    )

    client_factory.assert_called_once_with(
        api_key="synthetic-key-not-used",
    )

    fake_gemini.close.assert_called_once()


def test_internal_errors_do_not_expose_details(
    api_app,
    configured_env,
    monkeypatch,
):
    fake_db = Mock()

    db_context = MagicMock()
    db_context.__enter__.return_value = fake_db

    monkeypatch.setattr(
        agent_api,
        "SessionLocal",
        Mock(return_value=db_context),
    )

    fake_gemini = Mock()

    monkeypatch.setattr(
        agent_api.genai,
        "Client",
        Mock(return_value=fake_gemini),
    )

    monkeypatch.setattr(
        agent_api,
        "run_verified_investigation",
        Mock(
            side_effect=RuntimeError(
                "Sensitive internal service detail"
            )
        ),
    )

    response = make_request(
        api_app,
        headers=VALID_HEADERS,
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Investigation service unavailable."
    )

    assert "Sensitive internal" not in response.text

    fake_gemini.close.assert_called_once()
