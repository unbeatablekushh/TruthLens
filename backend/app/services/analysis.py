"""
Claim Extraction Service

Uses LLM to extract and classify factual claims from normalized text.
Validates structured output from LLM.
"""

import logging
from typing import List
from sqlalchemy.orm import Session

from app.core.providers import AIProvider
from app.models.analysis import Claim, Analysis, ClaimType
from app.schemas.analysis import ClaimExtractResponse, ClaimExtract
from app.services.normalization import LanguageDetectionService

logger = logging.getLogger(__name__)


class ClaimExtractionService:
    """
    Extracts and validates claims from normalized text using LLM.
    
    The LLM is responsible for:
    - Identifying factual claims
    - Classifying claim types
    - Assigning importance scores
    - Determining verifiability
    
    The service is responsible for:
    - Loading and formatting the extraction prompt
    - Calling the LLM
    - Validating structured output
    - Handling errors safely
    - Persisting claims to database
    """
    
    def __init__(self, ai_provider: AIProvider):
        """
        Initialize claim extraction service.
        
        Args:
            ai_provider: Configured AI provider (OllamaProvider, etc.)
        """
        self.ai_provider = ai_provider
    
    @staticmethod
    def load_extraction_prompt() -> str:
        """
        Load the claim extraction prompt from file.
        
        Returns:
            Prompt text for claim extraction
        """
        try:
            with open('prompts/claim_extraction.txt', 'r') as f:
                return f.read()
        except FileNotFoundError:
            # Fallback if file not found
            logger.warning("Claim extraction prompt file not found, using default")
            return ClaimExtractionService.DEFAULT_EXTRACTION_PROMPT
    
    DEFAULT_EXTRACTION_PROMPT = """You are a fact-checking assistant. Extract all factual claims from the following text. 
Return a JSON object with a "claims" array. Each claim should have: text, claim_type, importance (0-1), and verifiable (true/false).
Do NOT determine if claims are true or false. Only identify and classify them.
Return ONLY valid JSON, no other text."""
    
    async def extract_claims(self, 
                            normalized_text: str,
                            language: str = "en") -> tuple[bool, List[Claim], str]:
        """
        Extract claims from normalized text using LLM.
        
        Args:
            normalized_text: Cleaned and normalized input text
            language: Language code of text (for future multilingual support)
            
        Returns:
            Tuple of (success: bool, claims: List[Claim], error_message: str)
            - success: Whether extraction succeeded
            - claims: List of extracted Claim objects (or empty list if failed)
            - error_message: Error message if failed (empty string if successful)
        """
        try:
            # Load extraction prompt
            extraction_prompt = self.load_extraction_prompt()
            
            # Format prompt with input text
            full_prompt = extraction_prompt + "\n\nText to analyze:\n" + normalized_text
            
            # Call LLM for structured output
            logger.info(f"Extracting claims from text (language: {language})")
            response = await self.ai_provider.generate_structured(
                prompt=full_prompt,
                schema=ClaimExtractResponse,
                system_prompt="You are an expert fact-checker. Extract factual claims accurately."
            )
            
            # Convert response to Claim objects (not yet persisted)
            claims = []
            for claim_data in response.claims:
                claim = Claim(
                    text=claim_data.text,
                    claim_type=claim_data.claim_type,
                    importance=claim_data.importance,
                    verifiable=claim_data.verifiable,
                    extraction_confidence=0.95  # Base confidence from successful LLM extraction
                )
                claims.append(claim)
            
            logger.info(f"Successfully extracted {len(claims)} claims")
            return True, claims, ""
            
        except RuntimeError as e:
            error_msg = f"LLM claim extraction failed: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
        except Exception as e:
            error_msg = f"Unexpected error in claim extraction: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
    
    @staticmethod
    def persist_claims(db: Session, 
                       analysis: Analysis, 
                       claims: List[Claim]) -> bool:
        """
        Persist extracted claims to database.
        
        Args:
            db: Database session
            analysis: Parent Analysis object
            claims: List of Claim objects to persist
            
        Returns:
            Whether persistence succeeded
        """
        try:
            # Associate claims with analysis
            for claim in claims:
                claim.analysis_id = analysis.id
                db.add(claim)
            
            # Commit all claims
            db.commit()
            logger.info(f"Persisted {len(claims)} claims for analysis {analysis.id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to persist claims: {e}")
            return False


class AnalysisService:
    """
    Orchestrates the full analysis pipeline.
    
    Coordinates:
    - Input normalization
    - Language detection
    - Claim extraction
    - Status management
    - Error handling
    """
    
    def __init__(self, ai_provider: AIProvider):
        """Initialize analysis service."""
        self.ai_provider = ai_provider
        self.claim_extraction = ClaimExtractionService(ai_provider)
    
    async def create_analysis(self,
                             db: Session,
                             user_id,
                             original_input: str,
                             normalized_text: str,
                             input_type) -> tuple[bool, 'Analysis', str]:
        """
        Execute full analysis pipeline for user input.
        
        Pipeline:
        1. Create Analysis record
        2. Detect language
        3. Extract claims
        4. Persist claims
        5. Update status
        
        Args:
            db: Database session
            user_id: ID of user submitting analysis
            original_input: Original unmodified input
            normalized_text: Normalized input text
            input_type: Type of input (TEXT, CLAIM, etc.)
            
        Returns:
            Tuple of (success: bool, analysis: Analysis, error_message: str)
        """
        from app.models.analysis import Analysis, AnalysisStatus
        from datetime import datetime
        
        # Create Analysis record
        analysis = Analysis(
            user_id=user_id,
            input_type=input_type,
            original_input=original_input,
            normalized_text=normalized_text,
            status=AnalysisStatus.PROCESSING,
            processing_started_at=datetime.utcnow()
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        
        try:
            # Detect language
            analysis.language = LanguageDetectionService.detect_language(normalized_text)
            db.commit()
            
            # Extract claims
            success, claims, error_msg = await self.claim_extraction.extract_claims(
                normalized_text,
                language=analysis.language
            )
            
            if not success:
                # Mark as failed
                analysis.status = AnalysisStatus.FAILED
                analysis.error_message = error_msg
                analysis.processing_completed_at = datetime.utcnow()
                db.commit()
                return False, analysis, error_msg
            
            # Persist claims
            persist_ok = ClaimExtractionService.persist_claims(db, analysis, claims)
            if not persist_ok:
                analysis.status = AnalysisStatus.FAILED
                analysis.error_message = "Failed to persist extracted claims"
                analysis.processing_completed_at = datetime.utcnow()
                db.commit()
                return False, analysis, "Failed to persist extracted claims"
            
            # Mark as completed
            analysis.status = AnalysisStatus.COMPLETED
            analysis.processing_completed_at = datetime.utcnow()
            db.commit()
            db.refresh(analysis)  # Refresh to load claims
            
            return True, analysis, ""
            
        except Exception as e:
            error_msg = f"Analysis processing failed: {str(e)}"
            logger.error(error_msg)
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = error_msg
            analysis.processing_completed_at = datetime.utcnow()
            db.commit()
            return False, analysis, error_msg
