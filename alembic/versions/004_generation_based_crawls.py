"""Generation-based crawls with atomic visibility swap.

Adds generation_id and generation_active columns to documents table.
Creates partial index and documents_active view. Removes depth column.

This enables atomic crawl visibility:
1. Insert all new docs with generation_active=false
2. Atomic swap: UPDATE SET generation_active = (generation_id = new_gen_id)
3. Cleanup old generations

Revision ID: 004
Revises: 003
Create Date: 2025-12-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove depth column FIRST - before creating the view
    # (depth is ephemeral crawl state, not stored)
    op.drop_column("documents", "depth")

    # Add generation_id column (nullable initially for migration)
    op.add_column(
        "documents",
        sa.Column(
            "generation_id",
            UUID(as_uuid=True),
            nullable=True,  # Will be set NOT NULL after populating
        ),
    )

    # Add generation_active column
    op.add_column(
        "documents",
        sa.Column(
            "generation_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Set generation_id for existing documents and mark them active
    # Each existing document gets its own generation_id (one-doc-per-generation)
    # In practice, all docs for a domain will share a generation_id after next crawl
    op.execute("""
		UPDATE documents
		SET generation_id = gen_random_uuid(),
		    generation_active = true
		WHERE generation_id IS NULL
	""")

    # Now make generation_id NOT NULL
    op.alter_column("documents", "generation_id", nullable=False)

    # Create partial index for active documents per domain
    # This is the hot path - queries only care about active docs
    op.execute("""
		CREATE INDEX idx_documents_domain_active
		ON documents (domain)
		WHERE generation_active = true
	""")

    # Create view for active documents AFTER schema changes
    # Queries should use this view instead of documents table directly
    op.execute("""
		CREATE VIEW documents_active AS
		SELECT * FROM documents WHERE generation_active = true
	""")


def downgrade() -> None:
    # Add depth column back
    op.add_column(
        "documents",
        sa.Column(
            "depth",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Drop view
    op.execute("DROP VIEW IF EXISTS documents_active")

    # Drop partial index
    op.execute("DROP INDEX IF EXISTS idx_documents_domain_active")

    # Remove generation columns
    op.drop_column("documents", "generation_active")
    op.drop_column("documents", "generation_id")
