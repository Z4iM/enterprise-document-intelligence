"""Loopback-only synthetic browser fixture server; real auth, no real model calls."""

import argparse
import os
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8197)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="edi-browser-") as directory:
        root = Path(__file__).resolve().parents[1]
        os.environ.update(
            PYTHON_DOTENV_DISABLED="1",
            EDI_ENV="development",
            EDI_PROCESSING_MODE="embedded",
            EDI_DATA_ROOT="data",
            EDI_DATABASE_URL=f"sqlite:///{(Path(directory) / 'synthetic.db').as_posix()}",
            EDI_ALLOWED_ORIGINS="http://127.0.0.1:3197,http://127.0.0.1:3000",
            LLM_PROVIDER="disabled",
            EDI_ENABLE_DEV_AGENT="true",
            EDI_DEV_AGENT_TOKEN="synthetic-browser-agent-token",
            EDI_ENABLE_DEV_WORKFLOWS="false",
            ENABLE_DEV_POLICY_REVIEW="false",
        )
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("EDI_RETRIEVAL_MODEL_DIR", None)
        os.chdir(directory)
        from alembic.config import Config

        from alembic import command

        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        command.upgrade(config, "head")
        from app import main as application
        from app.auth.api import passwords
        from app.database.database import SessionLocal
        from app.database.models import Document, PolicyDocument, StoredPolicyRule, User
        from tests.test_verified_investigation_integration import (
            DOCUMENT_ID,
            POLICY_ID,
            seed_database,
        )

        with SessionLocal() as db:
            hashed = passwords.hash("synthetic-browser-password")
            for identifier, role in [
                ("employee", "employee"),
                ("reviewer", "reviewer"),
                ("admin", "admin"),
            ]:
                db.add(
                    User(
                        id=identifier,
                        organization_id="browser-org",
                        email=identifier + "@synthetic.test",
                        display_name="Synthetic " + role.title(),
                        password_hash=hashed,
                        role=role,
                        active=True,
                    )
                )
            seed_database(db)
            doc = db.get(Document, DOCUMENT_ID)
            doc.organization_id, doc.owner_id = "browser-org", "employee"
            policy = db.get(PolicyDocument, POLICY_ID)
            policy.organization_id, policy.owner_id = "browser-org", "reviewer"
            from docx import Document as WordDocument

            original = (
                Path(directory)
                / "data"
                / "policies"
                / POLICY_ID
                / "synthetic_policy.docx"
            )
            original.parent.mkdir(parents=True)
            source = WordDocument()
            statements = [
                "Meals above $100 require manager approval.",
                "Expenses of $25 or more require receipts.",
            ]
            for statement in statements:
                source.add_paragraph(statement)
            source.save(original)
            policy.stored_file_path = str(original)
            policy.mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            policy.extracted_text = "\n".join(statements)
            rule = db.get(StoredPolicyRule, "stored-meal-rule")
            rule.approval_status, rule.approved_by, rule.approved_at = (
                "pending",
                None,
                None,
            )
            db.commit()
        # Only model generation is synthetic; upload, verification, review and auth stay real.
        import json

        from app.validation import policy_extraction

        class SyntheticPolicyModel:
            def generate(self, prompt):
                sources = json.loads(prompt.split("SOURCE CHUNKS (JSON):\n", 1)[1])
                rules = []
                for chunk_id, text in sources.items():
                    for quote, category, operator, threshold, action, role in [
                        (
                            "Meals above $100 require manager approval.",
                            "meal",
                            ">",
                            "100",
                            "requires_approval",
                            "manager",
                        ),
                        (
                            "For all expenses of $25 or more, receipts are required.",
                            "all_expenses",
                            ">=",
                            "25",
                            "requires_documentation",
                            None,
                        ),
                    ]:
                        if quote in text:
                            rules.append(
                                {
                                    "category": category,
                                    "field": "total",
                                    "operator": operator,
                                    "threshold": threshold,
                                    "currency": "USD",
                                    "action": action,
                                    "approval_role": role,
                                    "source_quote": quote,
                                    "source_chunk_id": chunk_id,
                                }
                            )
                return json.dumps(rules)

        policy_extraction.get_llm_provider = SyntheticPolicyModel
        from app.agents import api as agent_api
        from tests.test_verified_investigation_integration import (
            text_response,
            tool_response,
        )

        class SyntheticInvestigationModel:
            def __init__(self, **kwargs):
                self.models = self
                self.turn = 0

            def generate_content(self, *, config, **kwargs):
                lines = config.system_instruction.splitlines()
                document_id = json.loads(
                    next(
                        line.split(": ", 1)[1]
                        for line in lines
                        if line.startswith("Authorized document IDs:")
                    )
                )[0]
                policy_id = json.loads(
                    next(
                        line.split(": ", 1)[1]
                        for line in lines
                        if line.startswith("Authorized policy IDs:")
                    )
                )[0]
                steps = [
                    tool_response("inspect_document", {"document_id": document_id}),
                    tool_response("get_policy_evidence", {"policy_id": policy_id}),
                    tool_response(
                        "evaluate_document_policy",
                        {"document_id": document_id, "policy_id": policy_id},
                    ),
                    text_response("Unverified synthetic draft must not be displayed."),
                ]
                response = steps[self.turn]
                self.turn += 1
                return response

            def close(self):
                pass

        agent_api.genai.Client = SyntheticInvestigationModel
        os.environ["GEMINI_API_KEY"] = "synthetic-browser-key-not-used"
        # Obsolete stale settings must not affect account-derived permissions.
        os.environ["EDI_DEV_AGENT_DOCUMENT_IDS"] = "stale-synthetic-document"
        os.environ["EDI_DEV_AGENT_POLICY_IDS"] = "stale-synthetic-policy"
        import uvicorn

        uvicorn.run(
            application.app, host="127.0.0.1", port=args.port, log_level="warning"
        )


if __name__ == "__main__":
    main()
