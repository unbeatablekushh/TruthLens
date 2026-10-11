"""
Analysis and Claim models for the TruthLens fact-checking system.

An Analysis represents a user's input to be fact-checked.
A Claim represents an individual factual claim extracted from an Analysis.
"""

from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Text, Float, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.core.database import Base


class AnalysisStatus(str, enum.Enum):
    """Status of an analysis in the pipeline."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class InputType(str, enum.Enum):
    """Type of input for analysis."""
    TEXT = "TEXT"
    CLAIM = "CLAIM"
    URL = "URL"
    IMAGE = "IMAGE"


class ClaimType(str, enum.Enum):
    """Type of claim being analyzed."""
    STATISTICAL = "STATISTICAL"
    POLITICAL = "POLITICAL"
    SCIENTIFIC = "SCIENTIFIC"
    MEDICAL = "MEDICAL"
    FINANCIAL = "FINANCIAL"
    HISTORICAL = "HISTORICAL"
    GEOGRAPHICAL = "GEOGRAPHICAL"
    EVENT = "EVENT"
    QUOTE = "QUOTE"
    OPINION = "OPINION"
    PREDICTION = "PREDICTION"
    OTHER = "OTHER"


class Analysis(Base):
    """
    Represents a single analysis request and tracks its progress through the pipeline.
    
    One Analysis can contain multiple Claims extracted from the input.
    """
    __tablename__ = "analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User who submitted this analysis
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Input metadata
    input_type = Column(Enum(InputType), nullable=False, default=InputType.TEXT)
    original_input = Column(Text, nullable=False)  # Preserve original unchanged
    normalized_text = Column(Text, nullable=False)  # Normalized for processing
    
    # Processing pipeline status
    status = Column(Enum(AnalysisStatus), nullable=False, default=AnalysisStatus.QUEUED)
    
    # Language detection
    language = Column(String(10), nullable=True, default="en")  # ISO 639-1 language code
    
    # Error tracking (only populated if status == FAILED)
    error_message = Column(String(500), nullable=True)
    
    # Timestamps for pipeline tracking
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    claims = relationship("Claim", back_populates="analysis", cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_analysis_user_id', 'user_id'),
        Index('idx_analysis_status', 'status'),
        Index('idx_analysis_created_at', 'created_at'),
    )


class Claim(Base):
    """
    Represents a single factual claim extracted from an Analysis.
    
    The LLM extracts claims and classifies them.
    Later phases will assign verdicts and evidence links.
    """
    __tablename__ = "claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference to parent analysis
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=False)
    
    # Claim content and classification
    text = Column(Text, nullable=False)  # The actual claim text
    claim_type = Column(Enum(ClaimType), nullable=False, default=ClaimType.OTHER)
    
    # Metadata assigned by extraction service
    importance = Column(Float, nullable=False)  # 0.0-1.0 scale
    verifiable = Column(Boolean, nullable=False, default=True)  # Is this factually verifiable?
    
    # Confidence in the extraction/classification (Phase 3 only)
    extraction_confidence = Column(Float, nullable=False, default=1.0)  # How confident is the extraction
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Evidence status and notes
    evidence_status = Column(String(50), nullable=False, default="INSUFFICIENT_EVIDENCE")
    evidence_note = Column(String(500), nullable=True)

    # Verdict (Milestone 4)
    verdict = Column(String(30), nullable=True)  # LIKELY_TRUE, PARTIALLY_TRUE, UNVERIFIED, LIKELY_FALSE, INSUFFICIENT_EVIDENCE
    verdict_explanation = Column(Text, nullable=True)
    verdict_limitations = Column(Text, nullable=True)

    # Relationships
    analysis = relationship("Analysis", back_populates="claims")
    sources = relationship("EvidenceSource", back_populates="claim", cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_claim_analysis_id', 'analysis_id'),
    )


class EvidenceSource(Base):
    """
    Represents an evidence source retrieved from web search for a claim.
    """
    __tablename__ = "evidence_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    
    title = Column(String(500), nullable=False)
    url = Column(String(2048), nullable=False)
    snippet = Column(Text, nullable=True)
    domain = Column(String(255), nullable=True)
    published_date = Column(String(100), nullable=True)

    # Evidence assessment (Milestone 4)
    evidence_assessment = Column(String(20), nullable=True)  # SUPPORTS, CONTRADICTS, MIXED, IRRELEVANT
    assessment_explanation = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    claim = relationship("Claim", back_populates="sources")
    
    __table_args__ = (
        Index('idx_evidence_source_claim_id', 'claim_id'),
    )
