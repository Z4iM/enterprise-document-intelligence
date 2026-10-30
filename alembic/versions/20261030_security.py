"""Adopt legacy SQLite without assigning its records to any account."""

import sqlalchemy as sa

from alembic import op

revision = "20261030_security"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    expected_legacy_columns = {
        "audit_events": ["created_at", "document_id", "event_type", "id", "message"],
        "documents": [
            "classification_confidence",
            "created_at",
            "detected_type",
            "document_type",
            "extracted_text",
            "file_hash",
            "file_size_bytes",
            "id",
            "mime_type",
            "original_filename",
            "processing_status",
            "review_status",
            "stored_file_path",
            "structured_data",
            "structured_extraction_method",
            "text_extraction_method",
            "updated_at",
        ],
        "human_reviews": [
            "after_data",
            "before_data",
            "corrections",
            "created_at",
            "decision",
            "document_id",
            "id",
            "notes",
            "reviewer",
        ],
        "policy_chunks": ["chunk_index", "id", "policy_id", "text"],
        "policy_documents": [
            "created_at",
            "extracted_text",
            "file_hash",
            "id",
            "mime_type",
            "original_filename",
            "stored_file_path",
        ],
        "policy_rule_reviews": [
            "created_at",
            "decision",
            "id",
            "notes",
            "reviewer",
            "stored_rule_id",
        ],
        "policy_validations": [
            "created_at",
            "document_id",
            "id",
            "retrieved_chunks",
            "status",
            "validation_result",
        ],
        "stored_policy_rules": [
            "approval_status",
            "approved_at",
            "approved_by",
            "created_at",
            "id",
            "policy_id",
            "rule_data",
            "rule_id",
            "verification_status",
        ],
    }
    existing_tables = set(sa.inspect(bind).get_table_names())
    for name, expected in expected_legacy_columns.items():
        if name in existing_tables:
            actual = {c["name"] for c in sa.inspect(bind).get_columns(name)}
            if not set(expected) <= actual:
                raise RuntimeError(
                    "Unsupported legacy schema; review a synthetic copy before migration."
                )
    for table in ("documents", "policy_documents"):
        if table in sa.inspect(bind).get_table_names():
            columns = {c["name"] for c in sa.inspect(bind).get_columns(table)}
            if "organization_id" not in columns:
                op.add_column(
                    table,
                    sa.Column(
                        "organization_id",
                        sa.String(),
                        nullable=False,
                        server_default="legacy-unassigned",
                    ),
                )
            if "owner_id" not in columns:
                op.add_column(table, sa.Column("owner_id", sa.String(), nullable=True))

    if "audit_events" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "audit_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("document_id", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "documents" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "documents",
            sa.Column("organization_id", sa.String(), nullable=False),
            sa.Column("owner_id", sa.String(), nullable=True),
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("original_filename", sa.String(), nullable=False),
            sa.Column("stored_file_path", sa.String(), nullable=False),
            sa.Column("mime_type", sa.String(), nullable=True),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False),
            sa.Column("file_hash", sa.String(), nullable=False),
            sa.Column("detected_type", sa.String(), nullable=True),
            sa.Column("text_extraction_method", sa.String(), nullable=True),
            sa.Column("extracted_text", sa.Text(), nullable=True),
            sa.Column("document_type", sa.String(), nullable=True),
            sa.Column("classification_confidence", sa.Float(), nullable=True),
            sa.Column("structured_extraction_method", sa.String(), nullable=True),
            sa.Column("structured_data", sa.JSON(), nullable=True),
            sa.Column("review_status", sa.String(), nullable=False),
            sa.Column("processing_status", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "ix_documents_organization_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("documents")
    }:
        op.create_index(
            op.f("ix_documents_organization_id"),
            "documents",
            ["organization_id"],
            unique=False,
        )
    if "ix_documents_owner_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("documents")
    }:
        op.create_index(
            op.f("ix_documents_owner_id"), "documents", ["owner_id"], unique=False
        )
    if "human_reviews" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "human_reviews",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("document_id", sa.String(), nullable=False),
            sa.Column("decision", sa.String(), nullable=False),
            sa.Column("reviewer", sa.String(), nullable=True),
            sa.Column("before_data", sa.JSON(), nullable=True),
            sa.Column("corrections", sa.JSON(), nullable=True),
            sa.Column("after_data", sa.JSON(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "policy_chunks" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "policy_chunks",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("policy_id", sa.String(), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "policy_documents" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "policy_documents",
            sa.Column("organization_id", sa.String(), nullable=False),
            sa.Column("owner_id", sa.String(), nullable=True),
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("original_filename", sa.String(), nullable=False),
            sa.Column("stored_file_path", sa.String(), nullable=False),
            sa.Column("mime_type", sa.String(), nullable=True),
            sa.Column("file_hash", sa.String(), nullable=False),
            sa.Column("extracted_text", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "ix_policy_documents_organization_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("policy_documents")
    }:
        op.create_index(
            op.f("ix_policy_documents_organization_id"),
            "policy_documents",
            ["organization_id"],
            unique=False,
        )
    if "ix_policy_documents_owner_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("policy_documents")
    }:
        op.create_index(
            op.f("ix_policy_documents_owner_id"),
            "policy_documents",
            ["owner_id"],
            unique=False,
        )
    if "policy_validations" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "policy_validations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("document_id", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("validation_result", sa.JSON(), nullable=False),
            sa.Column("retrieved_chunks", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    if "ix_policy_validations_document_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("policy_validations")
    }:
        op.create_index(
            op.f("ix_policy_validations_document_id"),
            "policy_validations",
            ["document_id"],
            unique=False,
        )
    if "request_limits" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "request_limits",
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("window", sa.Integer(), nullable=False),
            sa.Column("count", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("key"),
        )
    if "security_events" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "security_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("actor_id", sa.String(), nullable=True),
            sa.Column("organization_id", sa.String(), nullable=True),
            sa.Column("resource_id", sa.String(), nullable=True),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "users" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.CheckConstraint(
                "role IN ('employee','reviewer','admin')", name="ck_user_role"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
        )
    if "ix_users_organization_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("users")
    }:
        op.create_index(
            op.f("ix_users_organization_id"), "users", ["organization_id"], unique=False
        )
    if "workflow_runs" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "workflow_runs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("organization_id", sa.String(), nullable=False),
            sa.Column("owner_id", sa.String(), nullable=False),
            sa.Column("document_id", sa.String(), nullable=False),
            sa.Column("policy_id", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "ix_workflow_runs_organization_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("workflow_runs")
    }:
        op.create_index(
            op.f("ix_workflow_runs_organization_id"),
            "workflow_runs",
            ["organization_id"],
            unique=False,
        )
    if "auth_sessions" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "auth_sessions",
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("csrf_hash", sa.String(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("last_seen", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
            ),
            sa.PrimaryKeyConstraint("token_hash"),
        )
    if "ix_auth_sessions_user_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("auth_sessions")
    }:
        op.create_index(
            op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False
        )
    if "stored_policy_rules" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "stored_policy_rules",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("policy_id", sa.String(), nullable=False),
            sa.Column("rule_id", sa.String(), nullable=False),
            sa.Column("rule_data", sa.JSON(), nullable=False),
            sa.Column("verification_status", sa.String(), nullable=False),
            sa.Column("approval_status", sa.String(), nullable=False),
            sa.Column("approved_by", sa.String(), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "approval_status != 'approved' OR verification_status = 'verified'",
                name="ck_approval_requires_verification",
            ),
            sa.CheckConstraint(
                "approval_status IN ('pending', 'approved', 'rejected')",
                name="ck_policy_rule_approval_status",
            ),
            sa.CheckConstraint(
                "verification_status IN ('pending', 'verified', 'rejected')",
                name="ck_policy_rule_verification_status",
            ),
            sa.ForeignKeyConstraint(
                ["policy_id"],
                ["policy_documents.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "policy_id", "rule_id", name="uq_policy_rule_per_policy"
            ),
        )
    if "ix_stored_policy_rules_policy_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("stored_policy_rules")
    }:
        op.create_index(
            op.f("ix_stored_policy_rules_policy_id"),
            "stored_policy_rules",
            ["policy_id"],
            unique=False,
        )
    if "policy_rule_reviews" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "policy_rule_reviews",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("stored_rule_id", sa.String(), nullable=False),
            sa.Column("decision", sa.String(), nullable=False),
            sa.Column("reviewer", sa.String(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["stored_rule_id"],
                ["stored_policy_rules.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    if "ix_policy_rule_reviews_stored_rule_id" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("policy_rule_reviews")
    }:
        op.create_index(
            op.f("ix_policy_rule_reviews_stored_rule_id"),
            "policy_rule_reviews",
            ["stored_rule_id"],
            unique=False,
        )


def downgrade():
    raise RuntimeError(
        "Forward-only security adoption: retain data and restore a reviewed backup explicitly."
    )
