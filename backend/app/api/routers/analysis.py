"""
Analysis API endpoints for TruthLens fact-checking system.

Endpoints:
- POST /api/analysis/text - Analyze text input
- POST /api/analysis/claim - Analyze single claim
- GET /api/analysis/{id} - Retrieve specific analysis
- DELETE /api/analysis/{id} - Delete analysis
- GET /api/analysis - List user's analyses (future)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.core.providers import AIProvider
from app.api.deps import get_current_active_user
from app.models.auth import User
from app.models.analysis import Analysis, InputType
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.schemas.auth import UserResponse
from app.services.normalization import InputNormalizationService
from app.services.analysis import AnalysisService
from app.providers.ollama import OllamaProvider

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def get_ai_provider() -> AIProvider:
    """Dependency to get configured AI provider."""
    return OllamaProvider()


async def analyze_text_internal(
    input_text: str,
    input_type: InputType,
    user: User,
    db: Session,
    ai_provider: AIProvider
) -> tuple[bool, Optional[AnalysisResponse], str]:
    """
    Internal analysis pipeline.
    
    1. Validate input
    2. Normalize input
    3. Run analysis service
    4. Return structured response
    """
    # Validate input
    is_valid, error_msg, original_input, normalized_text = InputNormalizationService.process(input_text)
    if not is_valid:
        return False, None, error_msg
    
    # Create analysis service
    analysis_service = AnalysisService(ai_provider)
    
    # Run full analysis pipeline
    success, analysis, error_msg = await analysis_service.create_analysis(
        db=db,
        user_id=user.id,
        original_input=original_input,
        normalized_text=normalized_text,
        input_type=input_type
    )
    
    if not success:
        return False, None, error_msg
    
    # Convert to response
    response = AnalysisResponse.model_validate(analysis)
    return True, response, ""


@router.post("/text", response_model=AnalysisResponse)
async def analyze_text(
    request: AnalysisRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider)
):
    """
    Analyze text input and extract claims.
    
    - Validates input (10-50k characters)
    - Normalizes text
    - Extracts factual claims using LLM
    - Returns structured analysis with claims
    
    Args:
        request: AnalysisRequest with input_text and input_type
        user: Authenticated user
        db: Database session
        ai_provider: AI provider for claim extraction
        
    Returns:
        AnalysisResponse with extracted claims
        
    Raises:
        400: Invalid input
        401: Not authenticated
        500: Processing error
    """
    success, response, error_msg = await analyze_text_internal(
        request.input_text,
        InputType.TEXT,
        user,
        db,
        ai_provider
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    return response


@router.post("/claim", response_model=AnalysisResponse)
async def analyze_claim(
    request: AnalysisRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider)
):
    """
    Analyze a single claim and extract sub-claims if applicable.
    
    Similar to /text but optimized for single claims.
    
    Args:
        request: AnalysisRequest with input_text and input_type=CLAIM
        user: Authenticated user
        db: Database session
        ai_provider: AI provider
        
    Returns:
        AnalysisResponse with claim analysis
    """
    success, response, error_msg = await analyze_text_internal(
        request.input_text,
        InputType.CLAIM,
        user,
        db,
        ai_provider
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    return response


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
