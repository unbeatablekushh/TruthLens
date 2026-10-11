"""
Analysis API endpoints for TruthLens fact-checking system.

Endpoints:
- POST /api/analysis/text - Analyze text input
- POST /api/analysis/claim - Analyze single claim
- GET /api/analysis/{id} - Retrieve specific analysis
- DELETE /api/analysis/{id} - Delete analysis
- GET /api/analysis - List user's analyses (future)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.core.providers import AIProvider
from app.api.deps import get_current_active_user
from app.models.auth import User
from app.models.analysis import Analysis, InputType
from app.schemas.analysis import (
    AnalysisHistoryItem,
    AnalysisHistoryResponse,
    AnalysisRequest,
    AnalysisResponse,
)
from app.schemas.auth import UserResponse
from app.core.providers import AIProvider, SearchProvider
from app.services.normalization import InputNormalizationService
from app.services.analysis import AnalysisService
from app.providers.ollama import OllamaProvider
from app.providers.search import get_default_search_provider

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def get_ai_provider() -> AIProvider:
    """Dependency to get configured AI provider."""
    return OllamaProvider()


def get_search_provider() -> SearchProvider:
    """Dependency to get configured Search provider."""
    return get_default_search_provider()


async def analyze_text_internal(
    input_text: str,
    input_type: InputType,
    user: User,
    db: Session,
    ai_provider: AIProvider,
    search_provider: Optional[SearchProvider] = None
) -> tuple[bool, Optional[AnalysisResponse], str, int]:
    """
    Internal analysis pipeline.
    
    1. Validate input
    2. Normalize input
    3. Run analysis service (claims + evidence retrieval)
    4. Return structured response
    """
    # Validate input
    is_valid, error_msg, original_input, normalized_text = InputNormalizationService.process(input_text)
    if not is_valid:
        return False, None, error_msg, status.HTTP_400_BAD_REQUEST
    
    # Create analysis service
    analysis_service = AnalysisService(ai_provider, search_provider)
    
    # Run full analysis pipeline
    success, analysis, error_msg = await analysis_service.create_analysis(
        db=db,
        user_id=user.id,
        original_input=original_input,
        normalized_text=normalized_text,
        input_type=input_type
    )
    
    if not success:
        return False, None, error_msg, status.HTTP_500_INTERNAL_SERVER_ERROR
    
    # Convert to response
    response = AnalysisResponse.model_validate(analysis)
    return True, response, "", status.HTTP_200_OK


@router.post("/text", response_model=AnalysisResponse)
async def analyze_text(
    request: AnalysisRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    search_provider: SearchProvider = Depends(get_search_provider)
):
    """
    Analyze text input, extract claims, and retrieve evidence.
    """
    success, response, error_msg, status_code = await analyze_text_internal(
        request.input_text,
        InputType.TEXT,
        user,
        db,
        ai_provider,
        search_provider
    )
    
    if not success:
        raise HTTPException(
            status_code=status_code,
            detail=error_msg
        )
    
    return response


@router.post("/claim", response_model=AnalysisResponse)
async def analyze_claim(
    request: AnalysisRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    search_provider: SearchProvider = Depends(get_search_provider)
):
    """
    Analyze a single claim, extract sub-claims, and retrieve evidence.
    """
    success, response, error_msg, status_code = await analyze_text_internal(
        request.input_text,
        InputType.CLAIM,
        user,
        db,
        ai_provider,
        search_provider
    )
    
    if not success:
        raise HTTPException(
            status_code=status_code,
            detail=error_msg
        )
    
    return response


@router.get("", response_model=AnalysisHistoryResponse)
async def list_analyses(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List saved analyses belonging to the authenticated user, newest first."""
    user_analyses = db.query(Analysis).filter(Analysis.user_id == user.id)
    total_count = user_analyses.with_entities(func.count(Analysis.id)).scalar() or 0
    analyses = (
        user_analyses
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    for analysis in analyses:
        verdicts = {claim.verdict for claim in analysis.claims if claim.verdict}
        verdict_summary = None
        if len(verdicts) == 1:
            verdict_summary = next(iter(verdicts))
        elif len(verdicts) > 1:
            verdict_summary = "Multiple verdicts"

        text = " ".join((analysis.normalized_text or analysis.original_input).split())
        items.append(
            AnalysisHistoryItem(
                id=analysis.id,
                created_at=analysis.created_at,
                input_summary=text[:200],
                status=analysis.status,
                verdict_summary=verdict_summary,
            )
        )

    return AnalysisHistoryResponse(
        analyses=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve a specific analysis.
    
    Users can only retrieve their own analyses.
    
    Args:
        analysis_id: UUID of analysis to retrieve
        user: Authenticated user
        db: Database session
        
    Returns:
        AnalysisResponse
        
    Raises:
        403: User doesn't own this analysis
        404: Analysis not found
    """
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    # Enforce user ownership
    if analysis.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this analysis"
        )
    
    return AnalysisResponse.model_validate(analysis)


@router.delete("/{analysis_id}")
async def delete_analysis(
    analysis_id: UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete an analysis.
    
    Users can only delete their own analyses.
    
    Args:
        analysis_id: UUID of analysis to delete
        user: Authenticated user
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        403: User doesn't own this analysis
        404: Analysis not found
    """
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    # Enforce user ownership
    if analysis.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this analysis"
        )
    
    # Delete analysis (cascade deletes claims)
    db.delete(analysis)
    db.commit()
    
    return {
        "success": True,
        "message": f"Analysis {analysis_id} deleted successfully"
    }
