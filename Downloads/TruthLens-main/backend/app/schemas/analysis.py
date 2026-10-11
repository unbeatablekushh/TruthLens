"""
Pydantic schemas for analysis and claims.

These schemas validate API requests and responses.
"""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import List, Optional
from app.models.analysis import ClaimType, AnalysisStatus, InputType


class ClaimExtractResponse(BaseModel):
    """Response format from LLM claim extraction."""
    claims: List['ClaimExtract'] = Field(..., description="List of extracted claims")


class ClaimExtract(BaseModel):
    """Single claim extracted by LLM."""
    text: str = Field(..., min_length=5, description="Claim text")
    claim_type: ClaimType = Field(default=ClaimType.OTHER, description="Type of claim")
    importance: float = Field(..., ge=0.0, le=1.0, description="Importance score 0-1")
    verifiable: bool = Field(..., description="Is claim factually verifiable")


class EvidenceSourceResponse(BaseModel):
    """Response schema for a retrieved evidence source."""
    id: UUID
    claim_id: UUID
    title: str
    url: str
    snippet: Optional[str] = None
    domain: Optional[str] = None
    published_date: Optional[str] = None
    evidence_assessment: Optional[str] = None  # SUPPORTS, CONTRADICTS, MIXED, IRRELEVANT
    assessment_explanation: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClaimResponse(BaseModel):
    """Response schema for a claim."""
    id: UUID
    analysis_id: UUID
    text: str
    claim_type: ClaimType
    importance: float
    verifiable: bool
    extraction_confidence: float
    evidence_status: str = "INSUFFICIENT_EVIDENCE"
    evidence_note: Optional[str] = None
    sources: List[EvidenceSourceResponse] = Field(default_factory=list)
    verdict: Optional[str] = None
    verdict_explanation: Optional[str] = None
    verdict_limitations: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisRequest(BaseModel):
    """Request to start a new analysis."""
    input_text: str = Field(..., description="Text to analyze")
    input_type: InputType = Field(default=InputType.TEXT, description="Type of input")


class AnalysisResponse(BaseModel):
    """Response schema for a completed analysis."""
    id: UUID
    user_id: UUID
    input_type: InputType
    original_input: str
    normalized_text: str
    status: AnalysisStatus
    language: str
    error_message: Optional[str] = None
    claims: List[ClaimResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class AnalysisHistoryItem(BaseModel):
    """Compact summary of a saved analysis owned by the current user."""
    id: UUID
    created_at: datetime
    input_summary: str
    status: AnalysisStatus
    verdict_summary: Optional[str] = None


class AnalysisHistoryResponse(BaseModel):
    """Paginated page of the current user's saved analyses."""
    analyses: List[AnalysisHistoryItem]
    total_count: int
    limit: int
    offset: int


class AnalysisListResponse(BaseModel):
    """Response schema for listing analyses."""
    analyses: List[AnalysisResponse]
    total_count: int
    page: int
    page_size: int


class DeleteAnalysisResponse(BaseModel):
    """Response after deleting an analysis."""
    success: bool
    message: str
