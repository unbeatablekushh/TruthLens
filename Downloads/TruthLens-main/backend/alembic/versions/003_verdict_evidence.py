"""Persist evidence sources and claim verdict assessments.

Revision ID: 003_verdict_evidence
Revises: 002_analysis_models
Create Date: 2026-10-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "003_verdict_evidence"
down_revision = "002_analysis_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "claims",
        sa.Column(
            "evidence_status",
            sa.String(length=50),
            nullable=False,
            server_default="INSUFFICIENT_EVIDENCE",
        ),
    )
    op.add_column("claims", sa.Column("evidence_note", sa.String(length=500), nullable=True))
    op.add_column("claims", sa.Column("verdict", sa.String(length=30), nullable=True))
    op.add_column("claims", sa.Column("verdict_explanation", sa.Text(), nullable=True))
    op.add_column("claims", sa.Column("verdict_limitations", sa.Text(), nullable=True))

    op.create_table(
        "evidence_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("published_date", sa.String(length=100), nullable=True),
        sa.Column("evidence_assessment", sa.String(length=20), nullable=True),
        sa.Column("assessment_explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_evidence_source_claim_id",
        "evidence_sources",
        ["claim_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_evidence_source_claim_id", table_name="evidence_sources")
    op.drop_table("evidence_sources")
    op.drop_column("claims", "verdict_limitations")
    op.drop_column("claims", "verdict_explanation")
    op.drop_column("claims", "verdict")
    op.drop_column("claims", "evidence_note")
    op.drop_column("claims", "evidence_status")