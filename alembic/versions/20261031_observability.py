"""Content-free operational spans and trusted queued trace linkage."""

import sqlalchemy as sa

from alembic import op

revision = "20261031_observability"
down_revision = "20261030_specialists"
branch_labels = depends_on = None


def upgrade():
    op.add_column("processing_jobs", sa.Column("trace_id", sa.String(), nullable=True))
    op.add_column(
        "processing_jobs", sa.Column("parent_span_id", sa.String(), nullable=True)
    )
    op.create_table(
        "telemetry_spans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("span_id", sa.String(), nullable=False),
        sa.Column("parent_span_id", sa.String(), nullable=True),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("measurements", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ("organization_id", "trace_id", "created_at"):
        op.create_index("ix_telemetry_spans_" + column, "telemetry_spans", [column])


def downgrade():
    raise RuntimeError(
        "Restore a reviewed backup; operational history is not automatically deleted."
    )
