"""Derived policy passages and independently recoverable indexing jobs."""

import sqlalchemy as sa

from alembic import op

revision = "20261030_retrieval"
down_revision = "20261030_jobs"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("processing_jobs") as batch:
        batch.drop_constraint("ck_job_kind", type_="check")
        batch.create_check_constraint(
            "ck_job_kind", "kind IN ('document','policy','policy_index')"
        )
    op.create_table(
        "policy_search_indexes",
        sa.Column(
            "policy_id",
            sa.String(),
            sa.ForeignKey("policy_documents.id"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("source_digest", sa.String(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("passage_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "state IN ('queued','ready','failed','removed')", name="ck_search_state"
        ),
    )
    op.create_table(
        "search_passages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "policy_id",
            sa.String(),
            sa.ForeignKey("policy_documents.id"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id", sa.String(), sa.ForeignKey("policy_chunks.id"), nullable=False
        ),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.CheckConstraint(
            '"start" >= 0 AND "end" > "start"', name="ck_passage_offsets"
        ),
    )
    op.create_index("ix_search_passages_policy_id", "search_passages", ["policy_id"])
    op.create_index("ix_search_passages_chunk_id", "search_passages", ["chunk_id"])


def downgrade():
    raise RuntimeError(
        "Restore a reviewed backup; no automatic deletion of search state."
    )
