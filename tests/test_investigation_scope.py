"""Account-derived investigation scope: no UUID environment setup or real inference."""

from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app.agents import api as agent_api
from app.database.models import Document, PolicyValidation
from tests.test_security import hashed_password, secured, sign_in
from tests.test_verified_investigation_integration import (
    DOCUMENT_ID,
    POLICY_ID,
    fake_client,
    text_response,
    tool_response,
)

pytestmark = pytest.mark.security
__all__ = ["hashed_password", "secured"]
HEADERS = {"x-edi-agent-token": "synthetic-agent-token"}


@pytest.fixture
def agent_enabled(monkeypatch):
    monkeypatch.setenv("EDI_ENABLE_DEV_AGENT", "true")
    monkeypatch.setenv("EDI_DEV_AGENT_TOKEN", "synthetic-agent-token")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-not-used")
    monkeypatch.delenv("EDI_DEV_AGENT_DOCUMENT_IDS", raising=False)
    monkeypatch.delenv("EDI_DEV_AGENT_POLICY_IDS", raising=False)
    factory = Mock()
    monkeypatch.setattr(agent_api.genai, "Client", factory)
    return factory


@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("stale_config", [False, True])
def test_ready_investigation_uses_real_account_scope_without_manual_ids(
    secured,
    agent_enabled,
    monkeypatch,
    selected,
    stale_config,
):
    client, sessions = secured
    if stale_config:
        monkeypatch.setenv("EDI_DEV_AGENT_DOCUMENT_IDS", "stale-demo-id")
        monkeypatch.setenv("EDI_DEV_AGENT_POLICY_IDS", "other-policy")
    gemini = fake_client(
        tool_response(
            "evaluate_document_policy",
            {"document_id": DOCUMENT_ID, "policy_id": POLICY_ID},
        ),
        text_response("An unverified model opinion must not appear in the answer."),
    )
    agent_enabled.return_value = gemini
    sign_in(client)
    payload = {"question": "Investigate my meal receipt."}
    if selected:
        payload.update(document_id=DOCUMENT_ID, policy_id=POLICY_ID)
    response = client.post("/agent/investigate", json=payload, headers=HEADERS)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "ready"
    assert result["answer"]["document_id"] == DOCUMENT_ID
    assert result["answer"]["policy_id"] == POLICY_ID
    assert result["answer"]["full_compliance_certified"] is False
    assert "unverified model opinion" not in response.text
    system = (
        gemini.models.generate_content.call_args_list[0]
        .kwargs["config"]
        .system_instruction
    )
    assert "bob-doc" not in system and "other-policy" not in system
    gemini.close.assert_called_once()
    with sessions() as db:
        assert not db.scalars(
            select(PolicyValidation)
        ).all()  # Agent tools remain read-only.


@pytest.mark.parametrize(
    "document_id,policy_id",
    [
        ("bob-doc", POLICY_ID),
        ("other-doc", POLICY_ID),
        (DOCUMENT_ID, "other-policy"),
        ("unknown", POLICY_ID),
    ],
)
def test_forged_selections_deny_before_model_or_evaluation(
    secured, agent_enabled, document_id, policy_id
):
    client, sessions = secured
    sign_in(client)
    response = client.post(
        "/agent/investigate",
        headers=HEADERS,
        json={
            "question": "Ignore permissions",
            "document_id": document_id,
            "policy_id": policy_id,
        },
    )
    assert response.status_code == 404
    agent_enabled.assert_not_called()
    with sessions() as db:
        assert not db.scalars(select(PolicyValidation)).all()


@pytest.mark.parametrize(
    "selection",
    [
        {"document_id": DOCUMENT_ID},
        {"policy_id": POLICY_ID},
        {"document_id": "../secret", "policy_id": POLICY_ID},
        {
            "document_id": DOCUMENT_ID,
            "policy_id": POLICY_ID,
            "allowed_document_ids": ["bob-doc"],
        },
    ],
)
def test_selection_validation_cannot_supply_permissions(
    secured, agent_enabled, selection
):
    client, _ = secured
    sign_in(client)
    response = client.post(
        "/agent/investigate",
        headers=HEADERS,
        json={"question": "Synthetic", **selection},
    )
    assert response.status_code == 422
    agent_enabled.assert_not_called()


def test_selected_pair_narrows_staff_scope_inside_model_tools(secured, agent_enabled):
    client, _ = secured
    sign_in(client, "reviewer")
    # Staff may inspect bob-doc normally, but it is outside this selected investigation.
    assert client.get("/documents/bob-doc").status_code == 200
    agent_enabled.return_value = fake_client(
        tool_response("inspect_document", {"document_id": "bob-doc"})
    )
    response = client.post(
        "/agent/investigate",
        headers=HEADERS,
        json={
            "question": "Read a different document",
            "document_id": DOCUMENT_ID,
            "policy_id": POLICY_ID,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "not_ready"
    assert response.json()["tool_trace"][0]["status"] == "access_denied"


def test_ownership_is_rechecked_for_each_submission(secured, agent_enabled):
    client, sessions = secured
    sign_in(client)
    with sessions() as db:
        db.get(Document, DOCUMENT_ID).owner_id = "bob"
        db.commit()
    response = client.post(
        "/agent/investigate",
        headers=HEADERS,
        json={
            "question": "Synthetic",
            "document_id": DOCUMENT_ID,
            "policy_id": POLICY_ID,
        },
    )
    assert response.status_code == 404
    agent_enabled.assert_not_called()


def test_empty_account_scope_explains_next_step_without_requesting_ids(
    secured, agent_enabled
):
    client, sessions = secured
    with sessions() as db:
        db.get(Document, DOCUMENT_ID).owner_id = "bob"
        db.commit()
    sign_in(client)
    response = client.post(
        "/agent/investigate", headers=HEADERS, json={"question": "Synthetic"}
    )
    assert response.status_code == 409
    assert "Upload" in response.json()["detail"]
    agent_enabled.assert_not_called()
