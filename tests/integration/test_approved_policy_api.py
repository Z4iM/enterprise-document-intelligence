
import importlib

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import database as database_module
from app.database.database import Base
from app.database.models import (
    Document,
    PolicyDocument,
    PolicyValidation,
)


def test_approved_policy_api(tmp_path, monkeypatch):

    # Create isolated database.
    db_path = tmp_path / "api_policy_test.db"

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    try:
        # Create a processed document.
        with TestSession() as db:
            db.add(
                Document(
                    id="meal-001",
                    original_filename="meal_receipt.pdf",
                    stored_file_path="test/meal_receipt.pdf",
                    file_size_bytes=100,
                    file_hash="test-meal-hash",
                    detected_type="pdf",
                    document_type="receipt",
                    processing_status="completed",
                    review_status="approved",
                    structured_extraction_method="llm",
                    structured_data={
                        "expense_category": "meal",
                        "total": "$175.00",
                    },
                )
            )

            db.add(
                PolicyDocument(
                    id="policy-v1",
                    original_filename="company_policy.docx",
                    stored_file_path="test/company_policy.docx",
                    file_hash="test-policy-hash",
                )
            )

            db.commit()

        # Prevent app.main from initializing development
        # database tables during its initial import.
        monkeypatch.setattr(
            database_module,
            "create_tables",
            lambda: None,
        )

        main_module = importlib.import_module("app.main")

        # Replace development database session factory.
        monkeypatch.setattr(
            main_module,
            "SessionLocal",
            TestSession,
        )

        with TestClient(main_module.app) as client:

            # Check nonexistent document.
            missing_document = client.post(
                "/documents/nonexistent/validate-approved-policy",
                json={"policy_id": "policy-v1"},
            )

            assert missing_document.status_code == 404

            # Check nonexistent policy.
            missing_policy = client.post(
                "/documents/meal-001/validate-approved-policy",
                json={"policy_id": "nonexistent"},
            )

            assert missing_policy.status_code == 404

            # Evaluate against a policy with NO approved rules.
            response = client.post(
                "/documents/meal-001/validate-approved-policy",
                json={"policy_id": "policy-v1"},
            )

            assert response.status_code == 200, response.text

            result = response.json()

            # No approved rules must NOT imply compliance.
            assert result["status"] == "needs_review"
            assert result["policy_id"] == "policy-v1"
            assert result["document_id"] == "meal-001"

            assert result["validation"]["rules_evaluated"] == 0
            assert result["validation"]["applicable_rules"] == 0

        # Verify that the API persisted its result.
        with TestSession() as db:
            saved = db.scalar(
                select(PolicyValidation).where(
                    PolicyValidation.document_id == "meal-001"
                )
            )

            assert saved is not None
            assert saved.status == "needs_review"

    finally:
        engine.dispose()
