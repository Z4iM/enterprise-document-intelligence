
import pytest
from fastapi.testclient import TestClient

from app.main import app

URL = "/workflows/start"

PAYLOAD = {
    "document_id": "synthetic-doc-001",
    "policy_id": "synthetic-policy-001",
}

TEST_TOKEN = "synthetic-test-token"


def send_request(host, token=None):
    """Simulate a request from a specified client IP."""

    headers = {}

    if token is not None:
        headers["x-edi-workflow-token"] = token

    with TestClient(
        app,
        client=(host, 50000),
    ) as client:
        return client.post(
            URL,
            json=PAYLOAD,
            headers=headers,
        )


def test_workflow_endpoint_disabled_by_default(monkeypatch):
    monkeypatch.delenv(
        "EDI_ENABLE_DEV_WORKFLOWS",
        raising=False,
    )
    monkeypatch.setenv(
        "EDI_DEV_WORKFLOW_TOKEN",
        TEST_TOKEN,
    )

    response = send_request(
        host="127.0.0.1",
        token=TEST_TOKEN,
    )

    assert response.status_code == 404


def test_remote_access_is_rejected(monkeypatch):
    monkeypatch.setenv(
        "EDI_ENABLE_DEV_WORKFLOWS",
        "true",
    )
    monkeypatch.setenv(
        "EDI_DEV_WORKFLOW_TOKEN",
        TEST_TOKEN,
    )

    response = send_request(
        host="203.0.113.10",
        token=TEST_TOKEN,
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "token",
    [None, "incorrect-token"],
)
def test_missing_or_invalid_token_is_rejected(
    monkeypatch,
    token,
):
    monkeypatch.setenv(
        "EDI_ENABLE_DEV_WORKFLOWS",
        "true",
    )
    monkeypatch.setenv(
        "EDI_DEV_WORKFLOW_TOKEN",
        TEST_TOKEN,
    )

    response = send_request(
        host="127.0.0.1",
        token=token,
    )

    assert response.status_code == 403
