"""Scripted control-flow comparison, explicitly NOT a real-Gemini quality benchmark."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace


class ScriptedClient:
    def __init__(self, steps):
        self.models, self.steps, self.calls = self, iter(steps), 0

    def generate_content(self, **kwargs):
        from google.genai import types

        self.calls += 1
        step = next(self.steps)
        if isinstance(step, str):
            return SimpleNamespace(function_calls=[], text=step)
        name, arguments = step
        call = types.FunctionCall(
            name=name, args=arguments, id=f"synthetic-{self.calls}"
        )
        return SimpleNamespace(
            function_calls=[call],
            candidates=[
                types.Candidate(
                    content=types.Content(
                        role="model", parts=[types.Part(function_call=call)]
                    )
                )
            ],
            text="",
        )

    def close(self):
        pass


def evaluate_case(case):
    from langgraph.checkpoint.memory import InMemorySaver
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.agents.verified_investigation import run_verified_investigation
    from app.database.database import Base
    from app.database.models import (
        Document,
        PolicyChunk,
        PolicyDocument,
        PolicySearchIndex,
        SearchPassage,
        StoredPolicyRule,
        User,
    )
    from app.rag.indexing import source_hash
    from app.specialists.graph import build_graph
    from app.validation.rule_schemas import PolicyRule

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    currency = "EGP" if case["language"] == "ar" else "USD"
    quotes = (
        [
            "مصروفات الوجبات التي تتجاوز ١٠٠ جنيه مصري تتطلب موافقة المدير.",
            "لجميع المصروفات التي لا تقل عن ٢٥ جنيه مصري، الإيصالات مطلوبة.",
        ]
        if case["language"] == "ar"
        else [
            "Meals above $100 require manager approval.",
            "For all expenses of $25 or more, receipts are required.",
        ]
    )
    with sessions() as db:
        db.add(
            User(
                id="employee",
                email="synthetic@eval.test",
                organization_id="synthetic",
                role="employee",
                password_hash="not-an-authentication-fixture",
                active=True,
            )
        )
        db.add(
            Document(
                id="document",
                owner_id="employee",
                organization_id="synthetic",
                original_filename="synthetic.txt",
                file_size_bytes=100,
                stored_file_path="not-a-real-original",
                file_hash="synthetic",
                document_type="receipt",
                processing_status="completed",
                review_status="needs_review"
                if case["variant"] == "unreviewed"
                else "approved",
                structured_extraction_method="llm",
                structured_data={
                    "expense_category": "وجبات" if case["language"] == "ar" else "meal",
                    "total": str(case["amount"]) + " " + currency,
                },
            )
        )
        db.add(
            PolicyDocument(
                id="policy",
                organization_id="synthetic",
                original_filename="synthetic-policy.txt",
                stored_file_path="not-a-real-original",
                file_hash="synthetic",
            )
        )
        db.flush()
        db.add(
            PolicySearchIndex(
                policy_id="policy", enabled=True, state="ready", passage_count=2
            )
        )
        for index, quote in enumerate(quotes):
            chunk_id = f"source-{index}"
            text = (
                "tampered synthetic source"
                if case["variant"] == "tampered" and index == 0
                else quote
            )
            db.add(
                PolicyChunk(
                    id=chunk_id, policy_id="policy", chunk_index=index, text=text
                )
            )
            rule = PolicyRule(
                rule_id=f"rule-{index}",
                category="meal" if index == 0 else "all_expenses",
                field="total",
                operator=">" if index == 0 else ">=",
                threshold="100" if index == 0 else "25",
                currency=currency,
                action="requires_approval" if index == 0 else "requires_documentation",
                approval_role="manager" if index == 0 else None,
                source_chunk_id=chunk_id,
                source_quote=quote,
            )
            db.add(
                StoredPolicyRule(
                    id=f"stored-{index}",
                    policy_id="policy",
                    rule_id=rule.rule_id,
                    rule_data=rule.model_dump(mode="json"),
                    verification_status="verified",
                    approval_status="pending"
                    if case["variant"] == "unapproved"
                    else "approved",
                    approved_by="synthetic-reviewer",
                    approved_at=datetime.now(UTC),
                )
            )
            db.add(
                SearchPassage(
                    id=f"passage-{index}",
                    policy_id="policy",
                    chunk_id=chunk_id,
                    start=0,
                    end=len(quote),
                    source_hash=source_hash(quote),
                    language=case["language"],
                    embedding=None,
                )
            )
        db.commit()
    baseline_client = ScriptedClient(
        [
            ("inspect_document", {"document_id": "document"}),
            ("get_policy_evidence", {"policy_id": "policy"}),
            (
                "evaluate_document_policy",
                {"document_id": "document", "policy_id": "policy"},
            ),
            "Unverified draft ignored.",
        ]
    )
    started = time.perf_counter()
    with sessions() as db:
        baseline = run_verified_investigation(
            "Synthetic requirements question",
            client=baseline_client,
            model="scripted-no-inference",
            allowed_document_ids={"document"},
            allowed_policy_ids={"policy"},
            db=db,
        )
    baseline_ms = round((time.perf_counter() - started) * 1000, 2)
    clients = iter(
        [
            ScriptedClient(
                [
                    ("inspect_document", {"document_id": "document"}),
                    '{"decision":"ready"}',
                ]
            ),
            ScriptedClient(
                [
                    (
                        "search_policy_sources",
                        {
                            "policy_id": "policy",
                            "query": "الوجبات" if case["language"] == "ar" else "meals",
                        },
                    ),
                    ("get_policy_evidence", {"policy_id": "policy"}),
                    '{"decision":"ready"}',
                ]
            ),
        ]
    )
    graph = build_graph(
        InMemorySaver(),
        sessions=sessions,
        actor_id="employee",
        deadline=time.monotonic() + 30,
        client_factory=lambda: next(clients),
    )
    config = {"configurable": {"thread_id": case["id"]}, "recursion_limit": 16}
    started = time.perf_counter()
    graph.invoke(
        {
            "document_id": "document",
            "policy_id": "policy",
            "question": "Synthetic requirements question",
        },
        config,
    )
    values = graph.get_state(config).values
    cooperative_ms = round((time.perf_counter() - started) * 1000, 2)
    baseline_outcome = baseline.get("answer", {}).get("policy_outcome", "needs_review")
    cooperative_outcome = values.get("evaluation", {}).get("status", "needs_review")
    engine.dispose()
    return {
        **case,
        "baseline_outcome": baseline_outcome,
        "specialists_outcome": cooperative_outcome,
        "baseline_correct": baseline_outcome == case["expected"],
        "specialists_correct": cooperative_outcome == case["expected"],
        "baseline_model_calls_scripted": baseline_client.calls,
        "specialist_model_calls_scripted": values.get("model_calls", 0),
        "baseline_control_latency_ms": baseline_ms,
        "specialist_control_latency_ms": cooperative_ms,
        "specialist_checkpoint": values["status"],
        "documentation_unresolved": any(
            item["status"] != "reviewed_satisfied"
            for item in values.get("documentation", {}).get("requirements", [])
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    with tempfile.TemporaryDirectory(prefix="edi-specialist-eval-") as directory:
        os.environ.update(
            PYTHON_DOTENV_DISABLED="1",
            EDI_ENV="development",
            EDI_DATABASE_URL=f"sqlite:///{Path(directory).as_posix()}/unused.db",
            EDI_DATA_ROOT=directory,
            LLM_PROVIDER="disabled",
        )
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("EDI_RETRIEVAL_MODEL_DIR", None)
        cases = [
            {
                "id": f"{language}-{variant}-{amount}",
                "language": language,
                "variant": variant,
                "amount": amount,
                "expected": expected,
            }
            for language in ("en", "ar")
            for variant, amount, expected in [
                ("ready", 20, "passed"),
                ("ready", 100, "requires_documentation"),
                ("ready", 175, "requires_approval"),
                ("unreviewed", 175, "needs_review"),
                ("unapproved", 175, "needs_review"),
                ("tampered", 175, "needs_review"),
            ]
        ]
        rows = [evaluate_case(case) for case in cases]
        report = {
            "version": "scripted-control-flow-v1",
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scope": "Scripted adapters, not Gemini inference. Measures canonical outcomes, safety checkpoints, tool separation and control overhead; establishes no generative quality gain, real-model latency, token or dollar cost.",
            "cases": len(rows),
            "baseline_correct": sum(row["baseline_correct"] for row in rows),
            "specialists_correct": sum(row["specialists_correct"] for row in rows),
            "baseline_model_calls_scripted": sum(
                row["baseline_model_calls_scripted"] for row in rows
            ),
            "specialist_model_calls_scripted": sum(
                row["specialist_model_calls_scripted"] for row in rows
            ),
            "real_provider_tokens": None,
            "real_provider_cost": None,
            "per_case": rows,
        }
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {key: value for key, value in report.items() if key != "per_case"},
                indent=2,
            )
        )
        if report["baseline_correct"] != len(rows) or report[
            "specialists_correct"
        ] != len(rows):
            raise SystemExit("Canonical specialist control-flow regression.")


if __name__ == "__main__":
    main()
