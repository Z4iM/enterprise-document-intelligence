"""Explicit synthetic-only container smoke. Refuses databases containing other accounts/data."""

import argparse
import hashlib
import os
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from sqlalchemy import select

from app.auth.api import passwords
from app.auth.security import Principal
from app.database.database import SessionLocal
from app.database.models import (
    Document,
    HumanReview,
    PolicyChunk,
    PolicyDocument,
    PolicyRuleReview,
    ProcessingJob,
    StoredPolicyRule,
    User,
    WorkflowRun,
)
from app.jobs.queue import enqueue
from app.validation.rule_schemas import PolicyRule
from app.validation.source_verifier import verify_rule
from app.workflows.durable_review_graph import build_durable_review_graph

EMPLOYEE, REVIEWER = "edi-smoke-employee", "edi-smoke-reviewer"
DOCUMENT, POLICY, FLOW = "edi-smoke-document", "edi-smoke-policy", "edi-smoke-flow"
ORG = "edi-smoke-org"


def run_smoke(*, verify=False, sessions=SessionLocal, root=None):
    root = Path(root or os.getenv("EDI_DATA_ROOT", "data"))
    actor = Principal(EMPLOYEE, ORG, "employee")
    with sessions() as db:
        if (
            set(db.scalars(select(User.id))) - {EMPLOYEE, REVIEWER}
            or set(db.scalars(select(Document.id))) - {DOCUMENT}
            or set(db.scalars(select(PolicyDocument.id))) - {POLICY}
        ):
            raise RuntimeError(
                "Synthetic smoke refused: database contains other accounts/resources."
            )
        if not verify and db.get(Document, DOCUMENT) is None:
            for identifier, role in ((EMPLOYEE, "employee"), (REVIEWER, "reviewer")):
                db.add(
                    User(
                        id=identifier,
                        organization_id=ORG,
                        email=identifier + "@synthetic.test",
                        display_name="مستخدم تجريبي",
                        role=role,
                        active=True,
                        password_hash=passwords.hash(secrets.token_urlsafe(32)),
                    )
                )
            receipt = "Receipt\nMerchant: Synthetic Cafe\nإيصال تجريبي\nTotal: $175.00"
            quote = "Meals above $100 require manager approval."
            for identifier, folder, content in (
                (DOCUMENT, "uploads", receipt),
                (POLICY, "policies", quote),
            ):
                path = root / folder / identifier / "synthetic.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as original:
                    original.write(content.encode("utf-8"))
                common = {
                    "id": identifier,
                    "organization_id": ORG,
                    "original_filename": path.name,
                    "stored_file_path": str(path),
                    "mime_type": "text/plain",
                    "file_hash": hashlib.sha256(content.encode()).hexdigest(),
                }
                if folder == "uploads":
                    db.add(
                        Document(
                            **common,
                            owner_id=EMPLOYEE,
                            file_size_bytes=path.stat().st_size,
                            processing_status="queued",
                            review_status="processing",
                        )
                    )
                else:
                    db.add(
                        PolicyDocument(
                            **common, owner_id=REVIEWER, extracted_text=quote
                        )
                    )
            db.flush()
            rule = PolicyRule(
                rule_id="SMOKE-RULE",
                category="meal",
                field="total",
                operator=">",
                threshold="100",
                currency="USD",
                action="requires_approval",
                approval_role="manager",
                source_quote=quote,
                source_chunk_id="edi-smoke-chunk",
            )
            assert verify_rule(rule, quote)["verified"]
            db.add(
                PolicyChunk(
                    id="edi-smoke-chunk", policy_id=POLICY, chunk_index=0, text=quote
                )
            )
            db.add(
                StoredPolicyRule(
                    id="edi-smoke-rule",
                    policy_id=POLICY,
                    rule_id=rule.rule_id,
                    rule_data=rule.model_dump(mode="json"),
                    verification_status="verified",
                    approval_status="approved",
                    approved_by=REVIEWER,
                    approved_at=datetime.now(UTC),
                )
            )
            db.flush()
            db.add(
                PolicyRuleReview(
                    stored_rule_id="edi-smoke-rule",
                    decision="approve",
                    reviewer=REVIEWER,
                    notes="Synthetic fixture only.",
                )
            )
            enqueue(db, "document", DOCUMENT, actor)
            db.add(
                WorkflowRun(
                    id=FLOW,
                    organization_id=ORG,
                    owner_id=EMPLOYEE,
                    document_id=DOCUMENT,
                    policy_id=POLICY,
                )
            )
            db.commit()
    if not verify:
        for _ in range(150):
            with sessions() as db:
                state = db.scalar(
                    select(ProcessingJob.state).where(
                        ProcessingJob.resource_id == DOCUMENT
                    )
                )
            if state == "completed":
                break
            if state == "failed":
                raise RuntimeError("Synthetic processing failed.")
            time.sleep(0.5)
        else:
            raise RuntimeError("Worker did not finish the synthetic job.")
    with sessions() as db:
        document = db.get(Document, DOCUMENT)
        assert document and document.processing_status == "completed"
        assert "إيصال تجريبي" in document.extracted_text
        path = Path(document.stored_file_path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == document.file_hash
    checkpoint = root / "langgraph_checkpoints.sqlite"
    config = {"configurable": {"thread_id": FLOW}}
    with SqliteSaver.from_conn_string(str(checkpoint)) as saver:
        graph = build_durable_review_graph(saver, principal=actor)
        if not verify:
            graph.invoke({"document_id": DOCUMENT, "policy_id": POLICY}, config=config)
            assert graph.get_state(config).next == ("wait_for_human_review",)
        else:
            snapshot = graph.get_state(config)
            if snapshot.next:
                assert snapshot.next == ("wait_for_human_review",)
                # A synthetic human correction fixture; a resume signal alone never grants approval.
                with sessions() as db:
                    document = db.get(Document, DOCUMENT)
                    before = document.structured_data
                    document.structured_data = {
                        "merchant": "Synthetic Cafe",
                        "total": "$175.00",
                        "expense_category": "meal",
                    }
                    document.document_type, document.review_status = (
                        "receipt",
                        "corrected",
                    )
                    db.add(
                        HumanReview(
                            document_id=DOCUMENT,
                            reviewer=REVIEWER,
                            decision="corrected",
                            before_data=before,
                            after_data=document.structured_data,
                            notes="Synthetic restart verification only.",
                        )
                    )
                    db.commit()
                graph.invoke(Command(resume={"review_completed": True}), config=config)
            assert (
                graph.get_state(config).values["workflow_status"] == "requires_approval"
            )
    return {
        "processing": "completed",
        "checkpoint": "resumed" if verify else "waiting_for_review",
        "arabic_text_preserved": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    print(run_smoke(verify=args.verify))


if __name__ == "__main__":
    main()
