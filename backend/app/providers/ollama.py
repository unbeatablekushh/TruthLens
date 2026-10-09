"""
Ollama AI Provider Implementation

Connects to Ollama for local LLM inference without requiring paid API services.
Supports both text generation and structured JSON output with Pydantic validation.
"""

import httpx
import json
import logging
from typing import Optional
from pydantic import BaseModel, ValidationError

from app.core.providers import AIProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


class OllamaProvider(AIProvider):
    """
    Local LLM provider using Ollama.
    
    Ollama must be running and accessible at the configured endpoint.
    Default model: mistral (fast, good quality)
    """
    
    def __init__(self, 
                 base_url: str = None, 
                 model: str = None):
        """
        Initialize Ollama provider.
        
        Args:
            base_url: Ollama API endpoint (default: http://localhost:11434)
            model: Model name to use (default: mistral)
        """
        self.base_url = base_url or getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = model or getattr(settings, 'OLLAMA_MODEL', 'mistral')
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 minute timeout for LLM
    
    async def generate(self, 
                       prompt: str, 
                       system_prompt: Optional[str] = None) -> str:
        """
        Generate text from the LLM.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt to set context
            
        Returns:
            Generated text from the LLM
            
        Raises:
            RuntimeError: If Ollama is not accessible or generation fails
        """
        try:
            # Combine system and user prompts
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "temperature": 0.7,  # Balanced creativity/consistency
                },
            )
            
            if response.status_code != 200:
                error_msg = f"Ollama API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            result = response.json()
            generated_text = result.get("response", "").strip()
            
            if not generated_text:
                logger.error("Ollama returned empty response")
                raise RuntimeError("Ollama returned empty response")
            
            return generated_text
            
        except httpx.ConnectError as e:
            error_msg = f"Could not connect to Ollama at {self.base_url}. Is it running? Error: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Ollama generation failed: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    async def generate_structured(self, 
                                  prompt: str, 
                                  schema: type[BaseModel],
                                  system_prompt: Optional[str] = None) -> BaseModel:
        """
        Generate structured JSON output validated by Pydantic.
        
        Args:
            prompt: The user prompt (should request JSON output)
            schema: Pydantic model to validate response against
            system_prompt: Optional system prompt
            
        Returns:
            Validated Pydantic model instance
            
        Raises:
            RuntimeError: If generation or validation fails
            ValidationError: If response doesn't match schema
        """
        try:
            # Add JSON format instruction if not already present
            json_prompt = prompt
            if "JSON" not in prompt and "json" not in prompt.lower():
                json_prompt += "\n\nReturn ONLY valid JSON, no other text."
            
            # Generate response
            response_text = await self.generate(json_prompt, system_prompt)
            
            # Extract JSON from response (handle cases where model returns text with JSON)
            json_str = response_text.strip()
            
            # Try to find JSON in the response if it contains other text
            if not json_str.startswith('{') and not json_str.startswith('['):
                # Look for JSON block
                import re
                json_match = re.search(r'[\{\[].*[\}\]]', json_str, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
            
            # Parse JSON
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse JSON from LLM response: {json_str[:200]}"
                logger.error(f"{error_msg}. Error: {e}")
                raise RuntimeError(error_msg)
            
            # Validate against schema
            try:
                validated_data = schema(**data)
                return validated_data
            except ValidationError as e:
                error_msg = f"LLM response failed validation: {e.json()[:200]}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
        except RuntimeError:
            raise
        except Exception as e:
            error_msg = f"Structured generation failed: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    async def close(self):
        """Clean up HTTP client."""
        await self.client.aclose()
