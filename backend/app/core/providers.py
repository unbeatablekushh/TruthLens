from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

# =====================================================================
# AI / LLM Provider Abstraction
# =====================================================================
class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text from the LLM."""
        pass

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: type[BaseModel], system_prompt: Optional[str] = None) -> BaseModel:
        """Generate structured JSON output validated by Pydantic."""
        pass

class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings for a given text."""
        pass

# =====================================================================
# Search Provider Abstraction
# =====================================================================
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    published_date: Optional[str] = None

class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Search the web and return results."""
        pass

# =====================================================================
# OCR Provider Abstraction
# =====================================================================
class OCRProvider(ABC):
    @abstractmethod
    async def extract_text(self, image_path: str) -> str:
        """Extract text from an image."""
        pass

# =====================================================================
# Storage Provider Abstraction
# =====================================================================
class StorageProvider(ABC):
    @abstractmethod
    async def save_file(self, file_name: str, content: bytes) -> str:
        """Save a file and return its URI/path."""
        pass

    @abstractmethod
    async def get_file(self, uri: str) -> bytes:
        """Retrieve a file by its URI/path."""
        pass
