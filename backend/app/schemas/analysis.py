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


class ClaimResponse(BaseModel):
    """Response schema for a claim."""
    id: UUID
    analysis_id: UUID
    text: str
    claim_type: ClaimType
    importance: float
    verifiable: bool
    extraction_confidence: float
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AnalysisRequest(BaseModel):
    """Request to start a new analysis."""
    input_text: str = Field(..., min_length=10, max_length=50000, description="Text to analyze")
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
