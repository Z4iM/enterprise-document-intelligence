
import importlib
from io import BytesIO
from pathlib import Path

from docx import Document as WordDocument
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import database as database_module
from app.database import models
from app.database.storage import file_storage


def create_test_invoice() -> bytes:
    """Create a synthetic DOCX invoice in memory."""

    document = WordDocument()

    lines = [
        "INVOICE",
        "Invoice Number: INV-2026-TEST-001",
        "Vendor: Northstar Office Supplies",
        "Invoice Date: 2026-10-10",
        "Item: Office Keyboard",
        "Quantity: 2",
        "Unit Price: $45.00",
        "Subtotal: $90.00",
        "Tax: $9.00",
        "Total: $99.00",
        "Currency: USD",
    ]

    for line in lines:
        document.add_paragraph(line)

    buffer = BytesIO()
    document.save(buffer)

    return buffer.getvalue()


def test_upload_invoice_end_to_end(tmp_path, monkeypatch):
    # STEP 1: Create an isolated test database.
    test_db_path = tmp_path / "test_database.db"

    test_engine = create_engine(
        f"sqlite:///{test_db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    models.Base.metadata.create_all(bind=test_engine)

    TestSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    # STEP 2: Prevent app.main from creating development
    # database tables when it is imported.
    monkeypatch.setattr(
        database_module,
        "create_tables",
        lambda: None,
    )

    main_module = importlib.import_module("app.main")

    # STEP 3: Redirect endpoint database sessions
    # to our temporary test database.
    monkeypatch.setattr(
        main_module,
        "SessionLocal",
        TestSessionLocal,
    )

    # STEP 4: Redirect uploaded files to a temporary folder.
    test_upload_root = tmp_path / "uploads"
    test_upload_root.mkdir()

    monkeypatch.setattr(
        file_storage,
        "UPLOAD_ROOT",
        test_upload_root,
    )

    # STEP 5: Mock ONLY structured extraction.
    # The real Qwen server is not needed.
    expected_data = {
        "invoice_number": "INV-2026-TEST-001",
        "vendor": "Northstar Office Supplies",
        "invoice_date": "2026-10-10",
        "due_date": None,
        "total": "$99.00",
    }

    def fake_structured_extraction(text, document_type):
        assert document_type == "invoice"
        assert "INV-2026-TEST-001" in text

        return expected_data, "llm", False

    monkeypatch.setattr(
        main_module,
        "extract_structured_data",
        fake_structured_extraction,
    )

    invoice_bytes = create_test_invoice()

    try:
        # STEP 6: Send the real HTTP upload request.
        with TestClient(main_module.app) as client:
            response = client.post(
                "/documents/upload",
                files={
                    "file": (
                        "sample_invoice.docx",
                        invoice_bytes,
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document",
                    )
                },
            )

            assert response.status_code == 200, response.text

            result = response.json()
            document_id = result["document_id"]

            # STEP 7: Verify the API response.
            assert result["processing_status"] == "completed"
            assert result["document_type"] == "invoice"
            assert result["detected_type"] == "docx"
            assert result["extraction_method"] == "docx_parser"
            assert result["structured_data"] == expected_data

            # STEP 8: Verify database persistence.
            with TestSessionLocal() as db:
                saved_document = db.get(
                    models.Document,
                    document_id,
                )

                assert saved_document is not None
                assert saved_document.processing_status == "completed"
                assert saved_document.structured_data == expected_data

                # Verify the original file was saved.
                stored_path = Path(saved_document.stored_file_path)

                assert stored_path.is_file()
                assert stored_path.read_bytes() == invoice_bytes
                assert test_upload_root in stored_path.parents

                # Verify the audit trail.
                audit_events = db.scalars(
                    select(models.AuditEvent).where(
                        models.AuditEvent.document_id == document_id
                    )
                ).all()

                event_types = {
                    event.event_type for event in audit_events
                }

                assert "document_uploaded" in event_types
                assert "processing_completed" in event_types

            # STEP 9: Verify GET retrieves the saved document.
            get_response = client.get(
                f"/documents/{document_id}"
            )

            assert get_response.status_code == 200
            assert get_response.json()["structured_data"] == expected_data

            # STEP 10: Upload identical bytes again.
            duplicate_response = client.post(
                "/documents/upload",
                files={
                    "file": (
                        "sample_invoice.docx",
                        invoice_bytes,
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document",
                    )
                },
            )

            assert duplicate_response.status_code == 409

            duplicate_detail = duplicate_response.json()["detail"]

            assert duplicate_detail["existing_document_id"] == document_id

            # Verify the duplicate attempt was audited.
            with TestSessionLocal() as db:
                duplicate_events = db.scalars(
                    select(models.AuditEvent).where(
                        models.AuditEvent.document_id == document_id,
                        models.AuditEvent.event_type
                        == "duplicate_upload_attempt",
                    )
                ).all()

                assert len(duplicate_events) == 1

    finally:
        test_engine.dispose()
