"""
Input Normalization Service

Normalizes user input while preserving meaningful content.
- Removes extra whitespace
- Trims unnecessary formatting
- Validates input constraints
- Preserves original input separately
"""

import re
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class InputNormalizationService:
    """Normalizes text input for analysis processing."""
    
    # Minimum and maximum lengths
    MIN_INPUT_LENGTH = 10  # At least 10 characters to extract meaningful claims
    MAX_INPUT_LENGTH = 50000  # Reasonable limit for processing
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text for processing.
        
        Operations:
        - Strip leading/trailing whitespace
        - Replace multiple consecutive spaces with single space
        - Normalize newlines to spaces (preserve structure intent)
        - Remove unnecessary unicode whitespace
        
        Args:
            text: Raw input text
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Strip leading/trailing whitespace
        normalized = text.strip()
        
        # Normalize multiple spaces to single space
        normalized = re.sub(r' {2,}', ' ', normalized)
        
        # Normalize multiple newlines/tabs to single space
        normalized = re.sub(r'[\n\r\t]{1,}', ' ', normalized)
        
        # Remove other unicode whitespace characters
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Clean up any remaining leading/trailing space after normalization
        normalized = normalized.strip()
        
        return normalized
    
    @staticmethod
    def validate_input(text: str) -> Tuple[bool, str]:
        """
        Validate input meets requirements.
        
        Checks:
        - Not empty
        - At least MIN_INPUT_LENGTH characters
        - Not exceeding MAX_INPUT_LENGTH characters
        - Not just whitespace
        
        Args:
            text: Input text to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for empty/None
        if not text:
            return False, "Input cannot be empty"
        
        # Check for whitespace-only
        if not text.strip():
            return False, "Input cannot be only whitespace"
        
        # Check minimum length
        text_len = len(text)
        if text_len < InputNormalizationService.MIN_INPUT_LENGTH:
            return False, f"Input must be at least {InputNormalizationService.MIN_INPUT_LENGTH} characters (got {text_len})"
        
        # Check maximum length
        if text_len > InputNormalizationService.MAX_INPUT_LENGTH:
            return False, f"Input must not exceed {InputNormalizationService.MAX_INPUT_LENGTH} characters (got {text_len})"
        
        return True, ""
    
    @staticmethod
    def process(original_input: str) -> Tuple[bool, str, str, str]:
        """
        Validate and normalize input.
        
        Args:
            original_input: Raw user input
            
        Returns:
            Tuple of (is_valid, error_message, original_input_safe, normalized_text)
            - is_valid: Whether input passed validation
            - error_message: If invalid, the error message (empty string if valid)
            - original_input_safe: Safe copy of original (up to MAX_INPUT_LENGTH)
            - normalized_text: Normalized version for processing
        """
        # Truncate extremely long input for storage (shouldn't happen due to frontend limit)
        original_input_safe = original_input[:InputNormalizationService.MAX_INPUT_LENGTH]
        
        # Validate
        is_valid, error_msg = InputNormalizationService.validate_input(original_input)
        if not is_valid:
            return False, error_msg, original_input_safe, ""
        
        # Normalize
        normalized = InputNormalizationService.normalize_text(original_input)
        
        # Re-validate normalized version still meets minimum
        is_valid, error_msg = InputNormalizationService.validate_input(normalized)
        if not is_valid:
            return False, f"Input normalized to less than minimum length", original_input_safe, ""
        
        return True, "", original_input_safe, normalized


class LanguageDetectionService:
    """
    Detects language of input text.
    
    Currently supports English detection.
    Can be extended for multilingual support.
    """
    
    # Simple English detection based on common English words
    COMMON_ENGLISH_WORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
        'could', 'may', 'might', 'can', 'and', 'or', 'but', 'not', 'no', 'in',
        'on', 'at', 'to', 'for', 'of', 'with', 'by', 'as', 'that', 'this',
        'it', 'they', 'them', 'their', 'what', 'which', 'who', 'when', 'where',
        'why', 'how', 'all', 'each', 'every', 'both', 'some', 'any', 'more',
        'most', 'other', 'such', 'than', 'very', 'just', 'only', 'been',
    }
    
    @staticmethod
    def detect_language(text: str) -> str:
        """
        Detect language of input text.
        
        Currently returns 'en' for English or 'unknown'.
        Future: integrate with language detection library.
        
        Args:
            text: Text to detect language of
            
        Returns:
            ISO 639-1 language code (e.g., 'en', 'es', 'fr')
        """
        if not text or len(text) < 10:
            return "en"  # Default to English for very short text
        
        # Simple heuristic: count common English words
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        english_word_count = sum(1 for word in words if word in LanguageDetectionService.COMMON_ENGLISH_WORDS)
        
        # If more than 30% are common English words, assume English
        if len(words) > 0 and english_word_count / len(words) > 0.30:
            return "en"
        
        # Default to English (can be overridden by more sophisticated detection later)
        # For now, TruthLens focuses on English
        return "en"
