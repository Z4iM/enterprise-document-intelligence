
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import models
from app.main import app
from app.validation.rule_schemas import PolicyRule
from app.workflows import api as workflow_api
from app.workflows import document_policy_graph as workflow
from app.workflows.durable_review_graph import (
    build_durable_review_graph,
)


def test_authorized_workflow_creates_checkpoint(
    tmp_path,
    monkeypatch,
):
    # Isolated database: never use development records.
    db_path = tmp_path / "documents.sqlite"

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    models.Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine)

    try:
        with TestSession() as db:
            db.add(
                models.Document(
                    id="synthetic-api-document",
                    original_filename="synthetic_receipt.docx",
                    stored_file_path="unused-test-path",
                    file_size_bytes=100,
                    file_hash="synthetic-api-hash",
                    processing_status="completed",
                    review_status="needs_review",
                    structured_extraction_method="llm",
                    structured_data={
                        "expense_category": "meal",
                        "total": "$175.00",
                    },
                )
            )

            source_quote = (
                "Meals above $100 require manager approval."
            )

            rule = PolicyRule(
                rule_id="synthetic-meal-rule",
                category="meal",
                field="total",
                operator=">",
                threshold=Decimal("100.00"),
                currency="USD",
                action="requires_approval",
                approval_role="manager",
                source_quote=source_quote,
                source_chunk_id="synthetic-api-chunk",
            )

            db.add_all([
                models.PolicyDocument(
                    id="synthetic-policy",
                    original_filename="synthetic_policy.docx",
                    stored_file_path="unused-policy-path",
                    file_hash="synthetic-api-policy-hash",
                    extracted_text=source_quote,
                ),
                models.PolicyChunk(
                    id="synthetic-api-chunk",
                    policy_id="synthetic-policy",
                    chunk_index=0,
                    text=source_quote,
                ),
                models.StoredPolicyRule(
                    id="synthetic-api-stored-rule",
                    policy_id="synthetic-policy",
                    rule_id=rule.rule_id,
                    rule_data=rule.model_dump(mode="json"),
                    verification_status="verified",
                    approval_status="approved",
                    approved_by="synthetic-policy-reviewer",
                    approved_at=datetime.now(UTC),
                ),
            ])

            db.commit()

        # Redirect workflow database access.
        monkeypatch.setattr(
            workflow,
            "SessionLocal",
            TestSession,
        )

        # Keep checkpoints inside the test directory.
        checkpoint_path = (
            tmp_path / "workflow_checkpoints.sqlite"
        )

        monkeypatch.setattr(
            workflow_api,
            "CHECKPOINT_PATH",
            checkpoint_path,
        )

        # Enable the API only for this test.
        monkeypatch.setenv(
            "EDI_ENABLE_DEV_WORKFLOWS",
            "true",
        )

        monkeypatch.setenv(
            "EDI_DEV_WORKFLOW_TOKEN",
            "synthetic-integration-token",
        )

        # Execute the REAL FastAPI endpoint.
        with TestClient(
            app,
            client=("127.0.0.1", 50000),
        ) as client:
            response = client.post(
                "/workflows/start",
                json={
                    "document_id": "synthetic-api-document",
                    "policy_id": "synthetic-policy",
                },
                headers={
                    "x-edi-workflow-token":
                        "synthetic-integration-token",
                },
            )

        assert response.status_code == 200, response.text

        result = response.json()

        assert result["workflow_id"]
        assert result["status"] == "waiting_for_review"
        assert result["pending_nodes"] == [
            "wait_for_human_review"
        ]
        assert result["required_actions"] == []

        # Test the workflow status API using a NEW HTTP client.
        # This verifies the checkpoint can be retrieved
        # after the original request has completed.
        with TestClient(
            app,
            client=("127.0.0.1", 50000),
        ) as client:

            headers = {
                "x-edi-workflow-token": (
                    "synthetic-integration-token"
                ),
            }

            # 1. Retrieve an existing workflow.
            status_response = client.get(
                f"/workflows/{result['workflow_id']}",
                headers=headers,
            )

            assert status_response.status_code == 200

            status_data = status_response.json()

            assert status_data["workflow_id"] == (
                result["workflow_id"]
            )
            assert status_data["document_id"] == (
                "synthetic-api-document"
            )
            assert status_data["policy_id"] == (
                "synthetic-policy"
            )
            assert status_data["status"] == (
                "waiting_for_review"
            )
            assert status_data["pending_nodes"] == [
                "wait_for_human_review"
            ]
            assert status_data["required_actions"] == []

            # 2. Unknown workflow IDs must return 404.
            missing_response = client.get(
                "/workflows/nonexistent-workflow",
                headers=headers,
            )

            assert missing_response.status_code == 404

            # 3. Status lookup must also require authorization.
            unauthorized_response = client.get(
                f"/workflows/{result['workflow_id']}",
            )

            assert unauthorized_response.status_code == 403


        # Close the API's checkpoint connection,
        # then independently reopen the saved state.
        config = {
            "configurable": {
                "thread_id": result["workflow_id"],
            }
        }

        with SqliteSaver.from_conn_string(
            str(checkpoint_path)
        ) as saver:
            graph = build_durable_review_graph(saver)
            snapshot = graph.get_state(config)

            assert snapshot.next == (
                "wait_for_human_review",
            )

            assert snapshot.values["document_id"] == (
                "synthetic-api-document"
            )

            assert snapshot.values["review_status"] == (
                "needs_review"
            )

            assert "policy_evaluation" not in (
                snapshot.values
            )

        # Redirect the actual human-review API to our test DB.
        monkeypatch.setattr(
            "app.main.SessionLocal",
            TestSession,
        )

        headers = {
            "x-edi-workflow-token": "synthetic-integration-token",
        }

        resume_url = (
            f"/workflows/{result['workflow_id']}/resume"
        )

        with TestClient(
            app,
            client=("127.0.0.1", 50000),
        ) as client:

            # 1. An unauthorized resume must fail.
            unauthorized = client.post(resume_url)
            assert unauthorized.status_code == 403

            # 2. Resuming without a real review must
            #    interrupt again.
            premature = client.post(
                resume_url,
                headers=headers,
            )

            assert premature.status_code == 200, premature.text
            assert premature.json()["status"] == (
                "waiting_for_review"
            )

            # 3. Record extraction review through FastAPI.
            review = client.post(
                "/documents/synthetic-api-document/review",
                json={
                    "decision": "approved",
                    "reviewer": "synthetic-test-reviewer",
                    "notes": "Synthetic extraction verified.",
                },
            )

            assert review.status_code == 200, review.text
            assert review.json()["review_status"] == "approved"

            # 4. Resume after the persisted review.
            resumed = client.post(
                resume_url,
                headers=headers,
            )

            assert resumed.status_code == 200, resumed.text

            data = resumed.json()

            assert data["status"] == "requires_approval"
            assert data["pending_nodes"] == []
            assert data["required_actions"] == [
                "requires_approval"
            ]

            # 5. GET must return the completed status.
            status_response = client.get(
                f"/workflows/{result['workflow_id']}",
                headers=headers,
            )

            assert status_response.status_code == 200
            assert status_response.json()["status"] == (
                "requires_approval"
            )

            # 6. A completed workflow must not resume again.
            repeated = client.post(
                resume_url,
                headers=headers,
            )

            assert repeated.status_code == 409

        # 7. Verify persisted completion and policy evidence.
        with SqliteSaver.from_conn_string(
            str(checkpoint_path)
        ) as saver:
            graph = build_durable_review_graph(saver)
            snapshot = graph.get_state(config)

            assert snapshot.next == ()
            assert snapshot.values["workflow_status"] == (
                "requires_approval"
            )

            evaluation = snapshot.values["policy_evaluation"]

            assert evaluation["rules_evaluated"] == 1
            assert evaluation["applicable_rules"] == 1

            evidence = snapshot.values["policy_evidence"]

            assert len(evidence) == 1
            assert evidence[0]["source_quote"] == (
                "Meals above $100 require manager approval."
            )

    finally:
        engine.dispose()
