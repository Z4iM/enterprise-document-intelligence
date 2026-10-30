"""Real-session profile and automatic policy flows with synthetic model responses."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import main
from app.database.models import (
    AuditEvent,
    AuthSession,
    HumanReview,
    PolicyDocument,
    PolicyRuleReview,
    StoredPolicyRule,
)
from app.validation import policy_extraction
from tests.test_security import PASSWORD, hashed_password, secured, sign_in
from tests.test_verified_investigation_integration import DOCUMENT_ID, POLICY_ID

pytestmark = pytest.mark.security
# Reuse the isolated database fixtures, never the workspace database.
__all__ = ["hashed_password", "secured"]


class SyntheticModel:
    def __init__(self, invalid=False):
        self.calls = 0
        self.invalid = invalid

    def generate(self, prompt):
        self.calls += 1
        sources = json.loads(prompt.split("SOURCE CHUNKS (JSON):\n", 1)[1])
        chunk_id = next(iter(sources))
        rules = [
            {
                "category": "meal",
                "field": "total",
                "operator": ">",
                "threshold": "100",
                "currency": "USD",
                "action": "requires_approval",
                "approval_role": "manager",
                "source_quote": "Meals above $100 require manager approval.",
                "source_chunk_id": chunk_id,
            },
            {
                "category": "all_expenses",
                "field": "total",
                "operator": ">=",
                "threshold": "25",
                "currency": "USD",
                "action": "requires_documentation",
                "approval_role": None,
                "source_quote": "For all expenses of $25 or more, receipts are required.",
                "source_chunk_id": chunk_id,
            },
        ]
        if self.invalid:
            rules.append({**rules[0], "threshold": "9999"})
            rules.append({**rules[0], "source_chunk_id": "outside-policy"})
        return json.dumps(rules)


def upload_policy(client):
    return client.post(
        "/policies/upload",
        files={
            "file": (
                "synthetic-policy.txt",
                b"Meals above $100 require manager approval.\nFor all expenses of $25 or more, receipts are required.",
                "text/plain",
            )
        },
    )


def test_upload_automatically_extracts_all_rules_and_bulk_requires_confirmation(
    secured, monkeypatch
):
    client, sessions = secured
    sign_in(client, "reviewer")
    model = SyntheticModel(invalid=True)
    monkeypatch.setattr(policy_extraction, "get_llm_provider", lambda: model)
    response = upload_policy(client)
    assert response.status_code == 200, response.text
    policy_id = response.json()["policy_id"]
    listing = client.get(f"/policies/{policy_id}/rules").json()
    assert model.calls == 1
    assert listing["extraction_status"] == "completed_with_rejections"
    assert listing["total_rules"] == 2
    assert {r["approval_status"] for r in listing["rules"]} == {"pending"}
    ids = [r["id"] for r in listing["rules"]]
    assert (
        client.post(f"/policies/{policy_id}/rules/approve-all", json={}).status_code
        == 422
    )
    approved = client.post(
        f"/policies/{policy_id}/rules/approve-all", json={"rule_ids": ids}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["approved_count"] == 2
    assert (
        client.post(
            f"/policies/{policy_id}/rules/approve-all", json={"rule_ids": ids}
        ).status_code
        == 409
    )
    # Re-extraction never overwrites approved rules or adds duplicate reviews.
    assert client.post(f"/policies/{policy_id}/rules/extract-all").status_code == 200
    with sessions() as db:
        assert (
            len(
                db.scalars(
                    select(StoredPolicyRule).where(
                        StoredPolicyRule.policy_id == policy_id
                    )
                ).all()
            )
            == 2
        )
        reviews = db.scalars(
            select(PolicyRuleReview).where(PolicyRuleReview.stored_rule_id.in_(ids))
        ).all()
        assert len(reviews) == 2 and {r.reviewer for r in reviews} == {"reviewer"}


def test_model_failure_retains_policy_for_retry_and_redacts_error(
    secured, monkeypatch, caplog
):
    client, sessions = secured
    sign_in(client, "admin")

    def unavailable():
        raise RuntimeError("private-provider-secret")

    monkeypatch.setattr(policy_extraction, "get_llm_provider", unavailable)
    response = upload_policy(client)
    assert response.status_code == 200
    policy_id = response.json()["policy_id"]
    assert response.json()["rule_extraction"]["status"] == "failed"
    assert "private-provider-secret" not in response.text + caplog.text
    with sessions() as db:
        assert db.get(PolicyDocument, policy_id).extracted_text
    monkeypatch.setattr(policy_extraction, "get_llm_provider", SyntheticModel)
    assert (
        client.post(f"/policies/{policy_id}/rules/extract-all").json()["status"]
        == "completed"
    )


@pytest.mark.parametrize(
    "target", ["missing", "unverified", "reviewed", "other-policy"]
)
def test_batch_approval_is_atomic_on_invalid_or_conflicting_rule(secured, target):
    client, sessions = secured
    sign_in(client, "reviewer")
    with sessions() as db:
        valid = db.get(StoredPolicyRule, "stored-meal-rule")
        valid.approval_status, valid.approved_by, valid.approved_at = (
            "pending",
            None,
            None,
        )
        invalid = StoredPolicyRule(
            id="invalid-candidate",
            policy_id=POLICY_ID,
            rule_id="invalid",
            rule_data=valid.rule_data,
            verification_status="verified",
            approval_status="pending",
        )
        if target == "unverified":
            invalid.verification_status = "pending"
        elif target == "reviewed":
            invalid.approval_status = "rejected"
        elif target == "other-policy":
            invalid.policy_id = "other-policy"
        db.add(invalid)
        db.commit()
    ids = [
        "stored-meal-rule",
        "missing" if target == "missing" else "invalid-candidate",
    ]
    response = client.post(
        f"/policies/{POLICY_ID}/rules/approve-all", json={"rule_ids": ids}
    )
    assert response.status_code in {404, 409}
    with sessions() as db:
        assert db.get(StoredPolicyRule, "stored-meal-rule").approval_status == "pending"
        assert not db.scalars(select(PolicyRuleReview)).all()


def test_policy_new_routes_deny_employees_and_other_organizations(secured):
    client, _ = secured
    sign_in(client)
    for action in ("extract-all", "approve-all"):
        assert (
            client.post(
                f"/policies/{POLICY_ID}/rules/{action}",
                json={"rule_ids": ["stored-meal-rule"]},
            ).status_code
            == 403
        )
    sign_in(client, "outsider")
    assert client.post(f"/policies/{POLICY_ID}/rules/extract-all").status_code == 404
    assert (
        client.post(
            f"/policies/{POLICY_ID}/rules/approve-all",
            json={"rule_ids": ["stored-meal-rule"]},
        ).status_code
        == 404
    )


@pytest.mark.parametrize("who", ["alice", "reviewer", "admin"])
def test_profile_names_and_role_specific_stats_are_scoped(secured, who):
    client, sessions = secured
    sign_in(client, "admin")
    assert (
        client.post(
            f"/admin/users/{who}/profile", json={"display_name": "Assigned Person"}
        ).status_code
        == 200
    )
    sign_in(client, who)
    response = client.post(
        "/auth/profile", json={"display_name": "  Self-changed Person  "}
    )
    assert response.status_code == (200 if who == "admin" else 403)
    assert "password_hash" not in response.text
    for payload in [
        {"display_name": "Fake", "role": "admin"},
        {"display_name": "  "},
        {"display_name": "A\nB"},
    ]:
        assert client.post("/auth/profile", json=payload).status_code == (
            422 if who == "admin" else 403
        )
    if who != "admin":
        assert (
            client.post(
                f"/admin/users/{who}/profile", json={"display_name": "Forged name"}
            ).status_code
            == 403
        )
    with sessions() as db:
        db.add(HumanReview(document_id=DOCUMENT_ID, reviewer=who, decision="approved"))
        db.add(HumanReview(document_id="other-doc", reviewer=who, decision="approved"))
        db.commit()
    profile = client.get("/auth/profile").json()
    assert profile["user"]["display_name"] == (
        "Self-changed Person" if who == "admin" else "Assigned Person"
    )
    stats = profile["stats"]
    assert stats["documents_uploaded"] == (1 if who == "alice" else 0)
    assert ("documents_reviewed" in stats) == (who != "alice")
    if who != "alice":
        assert stats["documents_reviewed"] == stats["reviews_completed"] == 1
    assert ("active_users" in stats) == (who == "admin")
    if who == "admin":
        assert stats["active_users"] == 4


def test_names_resolve_for_audit_and_reviews_without_exposing_foreign_identity(secured):
    client, sessions = secured
    sign_in(client, "admin")
    assert (
        client.post(
            "/admin/users/reviewer/profile", json={"display_name": "Named Reviewer"}
        ).status_code
        == 200
    )
    sign_in(client, "reviewer")
    assert (
        client.post(
            f"/documents/{DOCUMENT_ID}/review",
            json={"decision": "approved", "reviewer": "spoofed"},
        ).status_code
        == 200
    )
    with sessions() as db:
        db.add(
            AuditEvent(
                document_id=DOCUMENT_ID,
                event_type="human_review",
                message="Document was approved by reviewer",
            )
        )
        db.add(
            AuditEvent(
                document_id=DOCUMENT_ID,
                event_type="human_review",
                actor_id="outsider",
                message="Document was approved",
            )
        )
        db.commit()
    events = client.get(f"/documents/{DOCUMENT_ID}/audit").json()
    assert sum(e.get("actor_name") == "Named Reviewer" for e in events) == 2
    assert any(e.get("actor_name") == "Unknown user" for e in events)
    reviews = client.get(f"/documents/{DOCUMENT_ID}/reviews").json()
    assert (
        reviews[-1]["reviewer"] == "reviewer"
        and reviews[-1]["reviewer_name"] == "Named Reviewer"
    )


def test_admin_can_name_existing_users_only_in_own_org(secured):
    client, _ = secured
    sign_in(client, "admin")
    assert (
        client.post(
            "/admin/users/alice/profile", json={"display_name": "Alice"}
        ).json()["display_name"]
        == "Alice"
    )
    assert (
        client.post(
            "/admin/users/outsider/profile", json={"display_name": "No"}
        ).status_code
        == 404
    )
    sign_in(client, "reviewer")
    assert (
        client.post(
            "/admin/users/alice/profile", json={"display_name": "No"}
        ).status_code
        == 403
    )


def test_password_change_checks_current_password_rotates_and_revokes_all_sessions(
    secured,
):
    client, sessions = secured
    sign_in(client)
    old_cookie = dict(client.cookies)
    with TestClient(main.app, base_url="http://127.0.0.1:8000") as second:
        sign_in(second)
        assert (
            client.post(
                "/auth/change-password",
                json={
                    "current_password": "wrong",
                    "new_password": "synthetic-new-password",
                },
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/auth/change-password",
                json={"current_password": PASSWORD, "new_password": "short"},
            ).status_code
            == 422
        )
        response = client.post(
            "/auth/change-password",
            json={
                "current_password": PASSWORD,
                "new_password": "synthetic-new-password",
            },
        )
        assert response.status_code == 200, response.text
        client.headers.update({"x-csrf-token": response.json()["csrf_token"]})
        assert dict(client.cookies) != old_cookie
        assert client.get("/auth/me").status_code == 200
        assert second.get("/auth/me").status_code == 401
    with sessions() as db:
        assert (
            len(
                db.scalars(
                    select(AuthSession).where(AuthSession.user_id == "alice")
                ).all()
            )
            == 1
        )
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/auth/login",
        headers={"x-csrf-token": csrf},
        json={"email": "alice@synthetic.test", "password": PASSWORD},
    )
    assert response.status_code == 401
    response = client.post(
        "/auth/login",
        headers={"x-csrf-token": csrf},
        json={"email": "alice@synthetic.test", "password": "synthetic-new-password"},
    )
    assert response.status_code == 200


def test_profile_and_password_changes_require_csrf(secured):
    client, _ = secured
    sign_in(client)
    client.headers.pop("x-csrf-token")
    for route, payload in [
        ("profile", {"display_name": "No"}),
        (
            "change-password",
            {"current_password": PASSWORD, "new_password": "synthetic-new-password"},
        ),
    ]:
        assert client.post(f"/auth/{route}", json=payload).status_code == 403


@pytest.mark.parametrize("raw", ["{}", "not json", "[{}]", json.dumps([{}] * 101)])
def test_invalid_model_output_never_becomes_approved_rules(secured, monkeypatch, raw):
    client, _ = secured
    sign_in(client, "reviewer")

    class InvalidModel:
        def generate(self, prompt):
            return raw

    monkeypatch.setattr(policy_extraction, "get_llm_provider", InvalidModel)
    response = upload_policy(client)
    assert response.status_code == 200
    listing = client.get(f"/policies/{response.json()['policy_id']}/rules").json()
    assert listing["total_rules"] == 0
    assert listing["extraction_status"] in {"failed", "completed_with_rejections"}


def test_whole_policy_budget_and_duplicate_processing_guard_precede_model_calls(
    secured, monkeypatch
):
    from app.database.models import PolicyChunk

    client, sessions = secured
    sign_in(client, "reviewer")
    model = SyntheticModel()
    monkeypatch.setattr(policy_extraction, "get_llm_provider", lambda: model)
    with sessions() as db:
        chunk = db.scalar(select(PolicyChunk).where(PolicyChunk.policy_id == POLICY_ID))
        chunk.text = "x" * 30_001
        db.commit()
    assert (
        client.post(f"/policies/{POLICY_ID}/rules/extract-all").json()["status"]
        == "failed"
    )
    assert model.calls == 0
    with sessions() as db:
        db.get(PolicyDocument, POLICY_ID).rule_extraction_status = "processing"
        db.commit()
    assert (
        client.post(f"/policies/{POLICY_ID}/rules/extract-all").json()["status"]
        == "processing"
    )
    assert model.calls == 0


def test_password_change_attempts_are_rate_limited(secured):
    client, _ = secured
    sign_in(client)
    payload = {"current_password": "wrong", "new_password": "synthetic-new-password"}
    for _ in range(5):
        assert client.post("/auth/change-password", json=payload).status_code == 400
    assert client.post("/auth/change-password", json=payload).status_code == 429


@pytest.mark.parametrize(
    "method,route,payload",
    [
        ("GET", "/auth/profile", None),
        ("POST", "/auth/profile", {"display_name": "No"}),
        (
            "POST",
            "/auth/change-password",
            {"current_password": PASSWORD, "new_password": "synthetic-new-password"},
        ),
        ("POST", f"/policies/{POLICY_ID}/rules/extract-all", None),
        (
            "POST",
            f"/policies/{POLICY_ID}/rules/approve-all",
            {"rule_ids": ["stored-meal-rule"]},
        ),
    ],
)
def test_new_routes_require_real_session(secured, method, route, payload):
    client, _ = secured
    assert client.request(method, route, json=payload).status_code == 401
