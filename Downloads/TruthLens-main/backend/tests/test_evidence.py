"""
Tests for Evidence Retrieval Service and Search Providers (Milestone 3).

Test coverage:
- TC-EVIDENCE-001: Successful evidence retrieval for verifiable claim
- TC-EVIDENCE-002: Multiple search results correctly extracted and associated
- TC-EVIDENCE-003: No results found returns INSUFFICIENT_EVIDENCE
- TC-EVIDENCE-004: Search provider unavailable returns INSUFFICIENT_EVIDENCE
- TC-EVIDENCE-005: Search provider timeout is handled gracefully
- TC-EVIDENCE-006: Non-verifiable/opinion claims skip search
- TC-EVIDENCE-007: Domain correctly extracted from URLs
- TC-EVIDENCE-008: Source URLs preserved exactly as returned by provider
- TC-EVIDENCE-009: Full analysis pipeline stores and returns evidence sources via API
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session
import httpx

from app.models.analysis import Analysis, Claim, EvidenceSource, InputType, ClaimType, AnalysisStatus
from app.core.providers import SearchResult, SearchProvider
from app.providers.search import (
    SearXNGProvider,
    DuckDuckGoProvider,
    FallbackSearchProvider,
    extract_domain,
)
from app.services.evidence import EvidenceRetrievalService
from app.services.analysis import AnalysisService
from app.schemas.analysis import ClaimExtractResponse, ClaimExtract


class TestDomainExtraction:
    """Test URL domain extraction utility."""

    def test_extract_standard_https(self):
        url = "https://www.reuters.com/business/economy-growth-2024"
        assert extract_domain(url) == "reuters.com"

    def test_extract_subdomain(self):
        url = "https://news.bbc.co.uk/world/article123"
        assert extract_domain(url) == "news.bbc.co.uk"

    def test_extract_simple_domain(self):
        url = "http://example.org/path"
        assert extract_domain(url) == "example.org"


class TestEvidenceRetrievalUnit:
    """Unit tests for EvidenceRetrievalService."""

    @pytest.mark.asyncio
    async def test_successful_evidence_retrieval(self):
        """TC-EVIDENCE-001: Successful evidence retrieval."""
        mock_search = AsyncMock(spec=SearchProvider)
        mock_search.search.return_value = [
            SearchResult(
                title="Global Economy in 2024",
                url="https://www.worldbank.org/en/news/press-release/2024/economy",
                snippet="The global economy expanded at a moderate pace in 2024.",
                domain="worldbank.org"
            )
        ]

        service = EvidenceRetrievalService(search_provider=mock_search)
        claim = Claim(
            id=uuid4(),
            text="The global economy expanded in 2024",
            verifiable=True,
            claim_type=ClaimType.STATISTICAL,
            importance=0.9
        )

        sources = await service.retrieve_evidence_for_claim(claim)

        assert len(sources) == 1
        assert sources[0].title == "Global Economy in 2024"
        assert sources[0].url == "https://www.worldbank.org/en/news/press-release/2024/economy"
        assert sources[0].domain == "worldbank.org"
        assert claim.evidence_status == "EVIDENCE_RETRIEVED"
        assert "1" in claim.evidence_note

    @pytest.mark.asyncio
    async def test_multiple_search_results(self):
        """TC-EVIDENCE-002: Multiple search results correctly attached."""
        mock_search = AsyncMock(spec=SearchProvider)
        mock_search.search.return_value = [
            SearchResult(
                title="Source 1",
                url="https://source1.com/story",
                snippet="Snippet 1",
                domain="source1.com"
            ),
            SearchResult(
                title="Source 2",
                url="https://source2.org/report",
                snippet="Snippet 2",
                domain="source2.org"
            ),
        ]

        service = EvidenceRetrievalService(search_provider=mock_search)
        claim = Claim(
            id=uuid4(),
            text="Carbon emissions reached new peaks in 2023",
            verifiable=True,
            claim_type=ClaimType.SCIENTIFIC,
            importance=0.95
        )

        sources = await service.retrieve_evidence_for_claim(claim)

        assert len(sources) == 2
        assert claim.evidence_status == "EVIDENCE_RETRIEVED"
        assert len(claim.sources) == 2
        assert sources[0].url == "https://source1.com/story"
        assert sources[1].url == "https://source2.org/report"

    @pytest.mark.asyncio
    async def test_no_results_found(self):
        """TC-EVIDENCE-003: No results found returns INSUFFICIENT_EVIDENCE."""
        mock_search = AsyncMock(spec=SearchProvider)
        mock_search.search.return_value = []

        service = EvidenceRetrievalService(search_provider=mock_search)
        claim = Claim(
            id=uuid4(),
            text="An obscure statement with zero web presence",
            verifiable=True,
            claim_type=ClaimType.OTHER,
            importance=0.5
        )

        sources = await service.retrieve_evidence_for_claim(claim)

        assert len(sources) == 0
        assert claim.evidence_status == "INSUFFICIENT_EVIDENCE"
        assert "No reliable external sources" in claim.evidence_note

    @pytest.mark.asyncio
    async def test_search_provider_unavailable(self):
        """TC-EVIDENCE-004: Search provider throws exception."""
        mock_search = AsyncMock(spec=SearchProvider)
        mock_search.search.side_effect = RuntimeError("Connection refused to search backend")

        service = EvidenceRetrievalService(search_provider=mock_search)
        claim = Claim(
            id=uuid4(),
            text="Some test claim",
            verifiable=True,
            claim_type=ClaimType.STATISTICAL,
            importance=0.8
        )

        sources = await service.retrieve_evidence_for_claim(claim)

        assert len(sources) == 0
        assert claim.evidence_status == "INSUFFICIENT_EVIDENCE"
        assert "unavailable" in claim.evidence_note.lower()

    @pytest.mark.asyncio
    async def test_non_verifiable_claim_skips_search(self):
        """TC-EVIDENCE-006: Opinion/unverifiable claim skips search entirely."""
        mock_search = AsyncMock(spec=SearchProvider)

        service = EvidenceRetrievalService(search_provider=mock_search)
        claim = Claim(
            id=uuid4(),
            text="Vanilla ice cream is the best dessert",
            verifiable=False,
            claim_type=ClaimType.OPINION,
            importance=0.2
        )

        sources = await service.retrieve_evidence_for_claim(claim)

        assert len(sources) == 0
        assert claim.evidence_status == "INSUFFICIENT_EVIDENCE"
        assert "subjective" in claim.evidence_note.lower()
        mock_search.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_source_urls_preserved_exactly(self):
        """TC-EVIDENCE-008: Exact URL preserved without hallucination or modification."""
        exact_url = "https://example.com/exact/path/test?id=42&sort=desc"
        mock_search = AsyncMock(spec=SearchProvider)
        mock_search.search.return_value = [
            SearchResult(
                title="Exact URL Source",
                url=exact_url,
                snippet="Evidence snippet text",
                domain="example.com"
            )
        ]

        service = EvidenceRetrievalService(search_provider=mock_search)
        claim = Claim(
            id=uuid4(),
            text="Testing exact URL preservation",
            verifiable=True,
            claim_type=ClaimType.EVENT,
            importance=0.7
        )

        sources = await service.retrieve_evidence_for_claim(claim)
        assert sources[0].url == exact_url


class TestEvidenceAPIIntegration:
    """Test full API pipeline integration with evidence retrieval."""

    @pytest.mark.parametrize(
        ("assessments", "expected_verdict"),
        [
            (["SUPPORTS", "SUPPORTS"], "LIKELY_TRUE"),
            (["CONTRADICTS", "CONTRADICTS"], "LIKELY_FALSE"),
            (["SUPPORTS", "CONTRADICTS"], "PARTIALLY_TRUE"),
            (["MIXED"], "UNVERIFIED"),
            (["IRRELEVANT"], "INSUFFICIENT_EVIDENCE"),
            ([], "INSUFFICIENT_EVIDENCE"),
        ],
    )
    def test_api_returns_and_persists_verdict_assessments(
        self, test_client, auth_headers, assessments, expected_verdict
    ):
        """The analysis API returns assessed sources and persisted claim verdicts."""
        mock_ai = AsyncMock()
        assessment_values = iter(assessments)

        async def generate_structured(prompt, schema, system_prompt=None):
            if schema is ClaimExtractResponse:
                return ClaimExtractResponse(
                    claims=[
                        ClaimExtract(
                            text="India recorded 8.2 percent GDP growth in 2024",
                            claim_type=ClaimType.STATISTICAL,
                            importance=0.9,
                            verifiable=True,
                        )
                    ]
                )
            assessment = next(assessment_values)
            return schema(
                assessment=assessment,
                explanation=f"Mock evidence assessment: {assessment.lower()}.",
            )

        mock_ai.generate_structured.side_effect = generate_structured
        mock_ai.generate.return_value = "Explanation based on the assessed sources."

        mock_search = AsyncMock(spec=SearchProvider)
        mock_search.search.return_value = [
            SearchResult(
                title=f"India GDP evidence {index + 1}",
                url=f"https://source{index + 1}.example/report",
                snippet="Retrieved evidence about India's reported GDP growth.",
                domain=f"source{index + 1}.example",
            )
            for index, _ in enumerate(assessments)
        ]

        from app.api.routers.analysis import get_ai_provider, get_search_provider
        from app.main import app

        app.dependency_overrides[get_ai_provider] = lambda: mock_ai
        app.dependency_overrides[get_search_provider] = lambda: mock_search

        try:
            response = test_client.post(
                "/api/analysis/claim",
                json={"input_text": "India recorded 8.2 percent GDP growth in 2024"},
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "COMPLETED"
            assert len(data["claims"]) == 1
            claim = data["claims"][0]
            assert claim["verdict"] == expected_verdict
            assert claim["verdict_explanation"]
            assert claim["verdict_limitations"]
            assert [source["evidence_assessment"] for source in claim["sources"]] == assessments
            assert all(source["assessment_explanation"] for source in claim["sources"])
            if assessments:
                assert claim["sources"][0]["title"] == "India GDP evidence 1"
                assert claim["sources"][0]["url"] == "https://source1.example/report"
                assert claim["sources"][0]["snippet"] == "Retrieved evidence about India's reported GDP growth."
            else:
                assert claim["sources"] == []

            retrieved = test_client.get(f"/api/analysis/{data['id']}", headers=auth_headers)
            assert retrieved.status_code == 200
            persisted_claim = retrieved.json()["claims"][0]
            assert persisted_claim["verdict"] == expected_verdict
            assert [source["evidence_assessment"] for source in persisted_claim["sources"]] == assessments
        finally:
            app.dependency_overrides.pop(get_ai_provider, None)
            app.dependency_overrides.pop(get_search_provider, None)
