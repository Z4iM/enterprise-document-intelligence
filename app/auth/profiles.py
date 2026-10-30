"""Readable identity labels and scoped personal activity; IDs remain authoritative."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    Document,
    HumanReview,
    PolicyDocument,
    PolicyRuleReview,
    StoredPolicyRule,
    User,
)


def user_label(db: Session, user_id: str | None, organization_id: str) -> str:
    user = db.get(User, user_id) if user_id else None
    if user is None or user.organization_id != organization_id:
        return "Unknown user"
    return user.display_name or "Unnamed user"


def personal_stats(db: Session, actor) -> dict[str, int]:
    def count(statement):
        return db.scalar(statement) or 0

    stats = {
        "documents_uploaded": count(
            select(func.count())
            .select_from(Document)
            .where(
                Document.organization_id == actor.organization_id,
                Document.owner_id == actor.id,
            )
        )
    }
    if actor.role in {"reviewer", "admin"}:
        stats.update(
            {
                "documents_reviewed": count(
                    select(func.count(func.distinct(HumanReview.document_id)))
                    .join(Document, Document.id == HumanReview.document_id)
                    .where(
                        Document.organization_id == actor.organization_id,
                        HumanReview.reviewer == actor.id,
                    )
                ),
                "reviews_completed": count(
                    select(func.count())
                    .select_from(HumanReview)
                    .join(Document, Document.id == HumanReview.document_id)
                    .where(
                        Document.organization_id == actor.organization_id,
                        HumanReview.reviewer == actor.id,
                    )
                ),
                "policies_uploaded": count(
                    select(func.count())
                    .select_from(PolicyDocument)
                    .where(
                        PolicyDocument.organization_id == actor.organization_id,
                        PolicyDocument.owner_id == actor.id,
                    )
                ),
                "rules_approved": count(
                    select(func.count())
                    .select_from(PolicyRuleReview)
                    .join(
                        StoredPolicyRule,
                        StoredPolicyRule.id == PolicyRuleReview.stored_rule_id,
                    )
                    .join(
                        PolicyDocument, PolicyDocument.id == StoredPolicyRule.policy_id
                    )
                    .where(
                        PolicyDocument.organization_id == actor.organization_id,
                        PolicyRuleReview.reviewer == actor.id,
                        PolicyRuleReview.decision == "approve",
                    )
                ),
            }
        )
    if actor.role == "admin":
        stats["active_users"] = count(
            select(func.count())
            .select_from(User)
            .where(User.organization_id == actor.organization_id, User.active.is_(True))
        )
    return stats
