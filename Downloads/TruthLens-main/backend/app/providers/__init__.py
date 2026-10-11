"""
Provider implementations for TruthLens.

This package contains concrete implementations of the provider abstractions
defined in app.core.providers.
"""

from app.providers.ollama import OllamaProvider
from app.providers.search import (
    SearXNGProvider,
    DuckDuckGoProvider,
    FallbackSearchProvider,
    get_default_search_provider,
)

__all__ = [
    'OllamaProvider',
    'SearXNGProvider',
    'DuckDuckGoProvider',
    'FallbackSearchProvider',
    'get_default_search_provider',
]
