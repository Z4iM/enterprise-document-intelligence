"""Durable ingestion jobs with bounded attempts and fenced worker leases."""

import sqlalchemy as sa

from alembic import op

revision = "20261030_jobs"
down_revision = "20261030_profiles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
        sa.Column("lease_token", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("kind", "resource_id", name="uq_job_resource"),
        sa.CheckConstraint("kind IN ('document','policy')", name="ck_job_kind"),
        sa.CheckConstraint(
            "state IN ('queued','running','retry_wait','completed','failed')",
            name="ck_job_state",
        ),
    )
    op.create_index(
        "ix_processing_jobs_organization_id", "processing_jobs", ["organization_id"]
    )
    op.create_index("ix_processing_jobs_state", "processing_jobs", ["state"])


def downgrade():
    raise RuntimeError(
        "Restore a reviewed backup; no automatic deletion of processing history."
    )
