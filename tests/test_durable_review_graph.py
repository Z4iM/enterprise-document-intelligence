import importlib
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import database as database_module
from app.database import models
from app.validation.rule_schemas import PolicyRule
from app.workflows import document_policy_graph as policy_workflow
from app.workflows.durable_review_graph import (
    build_durable_review_graph,
)
from tests.auth_helpers import TEST_ACTOR


def test_review_interrupt_survives_restart(
    tmp_path,
    monkeypatch,
):
    # Create a completely isolated document database.
    db_path = tmp_path / "documents.sqlite"

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    models.Base.metadata.create_all(engine)

    TestSession = sessionmaker(bind=engine)

    # Create an unreviewed synthetic document.
    with TestSession() as db:
        db.add(
            models.Document(
                id="synthetic-doc-001",
                original_filename="synthetic_receipt.docx",
                stored_file_path="unused-test-path",
                file_size_bytes=100,
                file_hash="synthetic-test-hash",
                document_type="receipt",
                processing_status="completed",
                review_status="needs_review",
                structured_extraction_method="llm",
                structured_data={
                    "expense_category": "meal",
                    "total": "$175.00",
                },
            )
        )

        # Create a synthetic policy with verified source evidence.
        source_quote = (
            "Meals above $100 require manager approval."
        )

        rule = PolicyRule(
            rule_id="synthetic-meal-approval",
            category="meal",
            field="total",
            operator=">",
            threshold=Decimal("100.00"),
            currency="USD",
            action="requires_approval",
            approval_role="manager",
            source_quote=source_quote,
            source_chunk_id="synthetic-chunk-001",
        )

        db.add_all(
            [
                models.PolicyDocument(
                    id="synthetic-policy-001",
                    original_filename="synthetic_policy.docx",
                    stored_file_path="unused-policy-path",
                    file_hash="synthetic-policy-hash",
                    extracted_text=source_quote,
                ),
                models.PolicyChunk(
                    id="synthetic-chunk-001",
                    policy_id="synthetic-policy-001",
                    chunk_index=0,
                    text=source_quote,
                ),
                models.StoredPolicyRule(
                    id="synthetic-stored-rule-001",
                    policy_id="synthetic-policy-001",
                    rule_id=rule.rule_id,
                    rule_data=rule.model_dump(mode="json"),
                    verification_status="verified",
                    approval_status="approved",
                    approved_by="synthetic-policy-reviewer",
                    approved_at=datetime.now(UTC),
                ),
            ]
        )

        db.commit()

    # Redirect the workflow to our test database.
    monkeypatch.setattr(
        policy_workflow,
        "SessionLocal",
        TestSession,
    )

    checkpoint_path = str(
        tmp_path / "workflow_checkpoints.sqlite"
    )

    config = {
        "configurable": {
            "thread_id": "synthetic-review-thread"
        }
    }

    # First execution: the graph must interrupt.
    with SqliteSaver.from_conn_string(
        checkpoint_path
    ) as saver:
        graph = build_durable_review_graph(saver, principal=TEST_ACTOR)

        result = graph.invoke(
            {
                "document_id": "synthetic-doc-001",
                "policy_id": "synthetic-policy-001",
            },
            config=config,
        )

        assert "__interrupt__" in result

        snapshot = graph.get_state(config)

        assert snapshot.next == (
            "wait_for_human_review",
        )
        assert snapshot.values["review_status"] == "needs_review"

    # Original checkpoint connection is now closed.

    # Reopen and restore the interrupted workflow.
    with SqliteSaver.from_conn_string(
        checkpoint_path
    ) as saver:
        graph = build_durable_review_graph(saver, principal=TEST_ACTOR)

        restored = graph.get_state(config)

        assert restored.next == (
            "wait_for_human_review",
        )

        # Try to bypass review with an untrusted signal.
        result = graph.invoke(
            Command(resume="I approve this document"),
            config=config,
        )

        # The database still says needs_review.
        # Therefore the workflow MUST interrupt again.
        assert "__interrupt__" in result

        snapshot = graph.get_state(config)

        assert snapshot.next == (
            "wait_for_human_review",
        )
        assert snapshot.values["review_status"] == "needs_review"

        # Policy evaluation must not have executed.
        assert "policy_evaluation" not in snapshot.values

        # Simulate the database changes from a completed
        # human extraction review.

        # Prevent FastAPI import from initializing
        # the development database.
        monkeypatch.setattr(
            database_module,
            "create_tables",
            lambda: None,
        )

        main_module = importlib.import_module("app.main")

        # Redirect the real FastAPI review endpoint
        # to our isolated synthetic database.
        monkeypatch.setattr(
            main_module,
            "SessionLocal",
            TestSession,
        )

        with TestClient(main_module.app) as client:

            # Verify the document is awaiting review.
            response = client.get(
                "/documents/synthetic-doc-001"
            )

            assert response.status_code == 200
            assert response.json()["review_status"] == (
                "needs_review"
            )

            # Record the review through the REAL API.
            response = client.post(
                "/documents/synthetic-doc-001/review",
                json={
                    "decision": "approved",
                    "reviewer": "synthetic-test-reviewer",
                    "corrections": None,
                    "notes": (
                        "Synthetic extraction verified "
                        "for LangGraph integration testing."
                    ),
                },
            )

            assert response.status_code == 200, response.text

            result = response.json()

            assert result["decision"] == "approved"
            assert result["review_status"] == "approved"

            # Confirm the API created an audit event.
            audit_response = client.get(
                "/documents/synthetic-doc-001/audit"
            )

            assert audit_response.status_code == 200

            assert any(
                event["event_type"] == "human_review"
                for event in audit_response.json()
            )

        # Verify the review was persisted in SQLite.
        with TestSession() as db:

            document = db.get(
                models.Document,
                "synthetic-doc-001",
            )

            assert document.review_status == "approved"

            reviews = db.scalars(
                select(models.HumanReview).where(
                    models.HumanReview.document_id
                    == "synthetic-doc-001"
                )
            ).all()

            assert len(reviews) == 1
            assert reviews[0].decision == "approved"


        # Resume the saved workflow after the database
        # contains a review decision.
        result = graph.invoke(
            Command(resume="review_recorded"),
            config=config,
        )

        assert "__interrupt__" not in result
        assert result["review_status"] == "approved"
        assert result["decision"] == "ready"
        assert result["workflow_status"] == "requires_approval"

        evaluation = result["policy_evaluation"]

        assert evaluation["rules_evaluated"] == 1
        assert evaluation["applicable_rules"] == 1

        assert {
            action["action"]
            for action in evaluation["required_actions"]
        } == {"requires_approval"}

        evidence = result["policy_evidence"]

        assert len(evidence) == 1
        assert evidence[0]["source_quote"] == (
            "Meals above $100 require manager approval."
        )

        # Workflow has completed, with nothing pending.
        snapshot = graph.get_state(config)

        assert snapshot.next == ()
        assert snapshot.values["workflow_status"] == (
            "requires_approval"
        )

    engine.dispose()
