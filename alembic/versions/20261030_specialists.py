"""Specialist workflows and explicitly reviewed documentation evidence."""

import sqlalchemy as sa

from alembic import op

revision = "20261030_specialists"
down_revision = "20261030_retrieval"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("processing_jobs") as batch:
        batch.drop_constraint("ck_job_kind", type_="check")
        batch.create_check_constraint(
            "ck_job_kind", "kind IN ('document','policy','policy_index','specialist')"
        )
    op.create_table(
        "specialist_workflows",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column(
            "document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False
        ),
        sa.Column(
            "policy_id",
            sa.String(),
            sa.ForeignKey("policy_documents.id"),
            nullable=False,
        ),
        sa.Column("question", sa.String(), nullable=False),
        sa.Column("request_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("checkpoint_thread", sa.String(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("resumes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "owner_id", "request_key", name="uq_specialist_request"
        ),
    )
    op.create_index(
        "ix_specialist_workflows_organization_id",
        "specialist_workflows",
        ["organization_id"],
    )
    op.create_table(
        "documentation_reviews",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False
        ),
        sa.Column(
            "policy_id",
            sa.String(),
            sa.ForeignKey("policy_documents.id"),
            nullable=False,
        ),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("reviewer_id", sa.String(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("source_digest", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_documentation_reviews_document_id", "documentation_reviews", ["document_id"]
    )


def downgrade():
    raise RuntimeError(
        "Restore a reviewed backup; no automatic deletion of workflow/review history."
    )
