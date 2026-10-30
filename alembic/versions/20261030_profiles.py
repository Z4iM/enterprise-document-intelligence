"""Add names, audit actors and policy extraction state without changing ownership."""

import sqlalchemy as sa

from alembic import op

revision = "20261030_profiles"
down_revision = "20261030_security"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(100), nullable=False, server_default=""),
    )
    op.add_column("audit_events", sa.Column("actor_id", sa.String(), nullable=True))
    op.add_column(
        "policy_documents",
        sa.Column(
            "rule_extraction_status",
            sa.String(),
            nullable=False,
            server_default="not_started",
        ),
    )
    op.add_column(
        "policy_documents",
        sa.Column("rule_extraction_message", sa.Text(), nullable=True),
    )
    # Defaults are application-owned after existing rows have been populated.
    with op.batch_alter_table("users") as batch:
        batch.alter_column("display_name", server_default=None)
    with op.batch_alter_table("policy_documents") as batch:
        batch.alter_column("rule_extraction_status", server_default=None)


def downgrade():
    raise RuntimeError(
        "Restore a reviewed backup to roll back; no automatic data deletion."
    )
