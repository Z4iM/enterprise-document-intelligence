
from fastapi.testclient import TestClient

from app.main import app


def test_investigation_endpoint_is_registered():
    """Verify the real EDI application exposes the route."""
    paths = app.openapi()["paths"]

    assert "/agent/investigate" in paths
    assert "post" in paths["/agent/investigate"]


def test_investigation_endpoint_disabled_by_default(
    monkeypatch,
):
    """Disabled agent requests must never reach Gemini."""

    monkeypatch.setenv(
        "EDI_ENABLE_DEV_AGENT",
        "false",
    )

    with TestClient(
        app,
        client=("127.0.0.1", 50000),
    ) as client:
        response = client.post(
            "/agent/investigate",
            json={
                "question": (
                    "Can I reimburse my $175 meal receipt?"
                )
            },
        )

    assert response.status_code == 404
