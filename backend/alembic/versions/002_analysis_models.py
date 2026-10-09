"""Add Analysis and Claim models for claim extraction.

Revision ID: 002_analysis_models
Revises: 001_initial_auth
Create Date: 2026-10-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_analysis_models'
down_revision = '001_initial_auth'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM types
    analysis_status_enum = postgresql.ENUM(
        'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED',
        name='analysisstatus',
        create_type=True
    )
    analysis_status_enum.create(op.get_bind(), checkfirst=True)

    input_type_enum = postgresql.ENUM(
        'TEXT', 'CLAIM', 'URL', 'IMAGE',
        name='inputtype',
        create_type=True
    )
    input_type_enum.create(op.get_bind(), checkfirst=True)

    claim_type_enum = postgresql.ENUM(
        'STATISTICAL', 'POLITICAL', 'SCIENTIFIC', 'MEDICAL', 'FINANCIAL',
        'HISTORICAL', 'GEOGRAPHICAL', 'EVENT', 'QUOTE', 'OPINION',
        'PREDICTION', 'OTHER',
        name='claimtype',
        create_type=True
    )
    claim_type_enum.create(op.get_bind(), checkfirst=True)

    # Create analyses table
    op.create_table(
        'analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('input_type', sa.Enum('TEXT', 'CLAIM', 'URL', 'IMAGE', name='inputtype'), nullable=False),
        sa.Column('original_input', sa.Text(), nullable=False),
        sa.Column('normalized_text', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED', name='analysisstatus'), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('processing_started_at', sa.DateTime(), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_analysis_created_at', 'analyses', ['created_at'], unique=False)
    op.create_index('idx_analysis_status', 'analyses', ['status'], unique=False)
    op.create_index('idx_analysis_user_id', 'analyses', ['user_id'], unique=False)

    # Create claims table
    op.create_table(
        'claims',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('claim_type', sa.Enum('STATISTICAL', 'POLITICAL', 'SCIENTIFIC', 'MEDICAL', 'FINANCIAL', 'HISTORICAL', 'GEOGRAPHICAL', 'EVENT', 'QUOTE', 'OPINION', 'PREDICTION', 'OTHER', name='claimtype'), nullable=False),
        sa.Column('importance', sa.Float(), nullable=False),
        sa.Column('verifiable', sa.Boolean(), nullable=False),
        sa.Column('extraction_confidence', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_claim_analysis_id', 'claims', ['analysis_id'], unique=False)


def downgrade() -> None:
    # Drop claims table and index
    op.drop_index('idx_claim_analysis_id', table_name='claims')
    op.drop_table('claims')

    # Drop analyses table and indexes
    op.drop_index('idx_analysis_created_at', table_name='analyses')
    op.drop_index('idx_analysis_status', table_name='analyses')
    op.drop_index('idx_analysis_user_id', table_name='analyses')
    op.drop_table('analyses')

    # Drop ENUM types
    sa.Enum('QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED', name='analysisstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum('TEXT', 'CLAIM', 'URL', 'IMAGE', name='inputtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum('STATISTICAL', 'POLITICAL', 'SCIENTIFIC', 'MEDICAL', 'FINANCIAL', 'HISTORICAL', 'GEOGRAPHICAL', 'EVENT', 'QUOTE', 'OPINION', 'PREDICTION', 'OTHER', name='claimtype').drop(op.get_bind(), checkfirst=True)
