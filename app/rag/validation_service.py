import traceback

from sqlalchemy.orm import Session

from app.database.models import PolicyValidation
from app.llm.http_provider import HTTPModelProvider
from app.rag.policy_validator import validate_against_policy


def run_policy_validation(
    db: Session,
    document_id: str,
    document_type: str,
    structured_data: dict,
    document_text: str
) -> dict:

    print("\n[1] Initializing Qwen provider")

    provider = HTTPModelProvider()

    print("[2] Running RAG validation")

    try:
        result = validate_against_policy(
            document_type=document_type,
            structured_data=structured_data,
            document_text=document_text,
            provider=provider,
            top_k=3
        )

        print("[3] RAG validation completed")

        validation = result["validation"]
        retrieved_chunks = result["retrieved_chunks"]
        
        print("[4] Saving validation to SQLite")

        record = PolicyValidation(
            document_id=document_id,
            status=validation["status"],
            validation_result=validation,
            retrieved_chunks=retrieved_chunks
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        print("[5] Database save successful")

        return {
            "validation_id": record.id,
            "document_id": document_id,
            "status": record.status,
            "validation": record.validation_result,
            "retrieved_chunks": record.retrieved_chunks
        }

    except Exception:
        db.rollback()

        print("\n========== ACTUAL ERROR ==========")
        traceback.print_exc()
        print("==================================\n")

        raise