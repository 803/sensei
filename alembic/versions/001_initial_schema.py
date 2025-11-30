"""Initial schema with queries, ratings, and documents tables.

Revision ID: 001
Revises:
Create Date: 2025-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	# queries table
	op.create_table(
		"queries",
		sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
		sa.Column("query", sa.Text(), nullable=False),
		sa.Column("language", sa.String(), nullable=True),
		sa.Column("library", sa.String(), nullable=True),
		sa.Column("version", sa.String(), nullable=True),
		sa.Column("output", sa.Text(), nullable=False),
		sa.Column("messages", sa.Text(), nullable=True),
		sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
		sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
		sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
		sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
		sa.PrimaryKeyConstraint("id"),
		sa.ForeignKeyConstraint(["parent_id"], ["queries.id"]),
	)

	# ratings table
	op.create_table(
		"ratings",
		sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
		sa.Column("query_id", UUID(as_uuid=True), nullable=False),
		sa.Column("correctness", sa.Integer(), nullable=False),
		sa.Column("relevance", sa.Integer(), nullable=False),
		sa.Column("usefulness", sa.Integer(), nullable=False),
		sa.Column("reasoning", sa.Text(), nullable=True),
		sa.Column("agent_model", sa.String(), nullable=True),
		sa.Column("agent_system", sa.String(), nullable=True),
		sa.Column("agent_version", sa.String(), nullable=True),
		sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
		sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
		sa.PrimaryKeyConstraint("id"),
		sa.ForeignKeyConstraint(["query_id"], ["queries.id"]),
		sa.CheckConstraint("correctness BETWEEN 1 AND 5", name="correctness_range_check"),
		sa.CheckConstraint("relevance BETWEEN 1 AND 5", name="relevance_range_check"),
		sa.CheckConstraint("usefulness BETWEEN 1 AND 5", name="usefulness_range_check"),
	)

	# documents table
	op.create_table(
		"documents",
		sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
		sa.Column("domain", sa.String(), nullable=False),
		sa.Column("url", sa.String(), nullable=False),
		sa.Column("path", sa.String(), nullable=False),
		sa.Column("content", sa.Text(), nullable=False),
		sa.Column("content_hash", sa.String(), nullable=False),
		sa.Column("content_refreshed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
		sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
		sa.Column("inserted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
		sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
		sa.PrimaryKeyConstraint("id"),
		sa.UniqueConstraint("url"),
	)
	op.create_index("ix_documents_domain", "documents", ["domain"])


def downgrade() -> None:
	op.drop_index("ix_documents_domain", table_name="documents")
	op.drop_table("documents")
	op.drop_table("ratings")
	op.drop_table("queries")
