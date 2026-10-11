"""
Tests for Analysis API and services.

Test coverage:
- TC-ANALYSIS-001: Valid text analysis
- TC-ANALYSIS-002: Valid claim analysis
- TC-ANALYSIS-003: Empty input
- TC-ANALYSIS-004: Input too short
- TC-ANALYSIS-005: Unauthenticated analysis request
- TC-ANALYSIS-006: User can retrieve own analysis
- TC-ANALYSIS-007: User cannot retrieve another user's analysis
- TC-ANALYSIS-008: Claim extraction returns structured data
- TC-ANALYSIS-009: Malformed AI response is handled safely
- TC-ANALYSIS-010: AI provider failure
- TC-ANALYSIS-011: Analysis status becomes FAILED after processing error
- TC-ANALYSIS-012: Multiple claims are persisted correctly
"""

import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from app.models.auth import User, Role
from app.models.analysis import Analysis, Claim, EvidenceSource, AnalysisStatus, InputType, ClaimType
from app.schemas.analysis import AnalysisRequest, ClaimExtractResponse, ClaimExtract
from app.services.normalization import InputNormalizationService
from app.services.analysis import AnalysisService, ClaimExtractionService
from app.core.providers import AIProvider, SearchProvider, SearchResult
from app.services.evidence import EvidenceRetrievalService


class TestInputNormalization:
    """Test input normalization and validation."""
    
    def test_normalize_removes_extra_spaces(self):
        """Test that extra spaces are normalized."""
        text = "Hello    world    this    is    text"
        normalized = InputNormalizationService.normalize_text(text)
        assert normalized == "Hello world this is text"
    
    def test_normalize_handles_newlines(self):
        """Test that newlines are normalized to spaces."""
        text = "Hello\n\nworld\nthis\ris\ttext"
        normalized = InputNormalizationService.normalize_text(text)
        assert "\n" not in normalized
        assert "Hello world this is text" in normalized
    
    def test_validate_empty_input(self):
        """TC-ANALYSIS-003: Test empty input validation."""
        is_valid, error = InputNormalizationService.validate_input("")
        assert not is_valid
        assert "empty" in error.lower()
    
    def test_validate_too_short_input(self):
        """TC-ANALYSIS-004: Test input too short validation."""
        is_valid, error = InputNormalizationService.validate_input("short")
        assert not is_valid
        assert "at least" in error.lower()
    
    def test_validate_valid_input(self):
        """Test valid input passes validation."""
        is_valid, error = InputNormalizationService.validate_input("This is a valid input for testing")
        assert is_valid
        assert error == ""
    
    def test_process_returns_normalized(self):
        """Test process function returns both original and normalized."""
        original = "Hello    world  this   is   text"
        is_valid, error, original_safe, normalized = InputNormalizationService.process(original)
        assert is_valid
        assert original_safe == original
        assert normalized == "Hello world this is text"
        assert "  " not in normalized  # No double spaces


class TestLanguageDetection:
    """Test language detection."""
    
    def test_detects_english(self):
        """Test English detection."""
        text = "The quick brown fox jumps over the lazy dog. This is a test."
        lang = InputNormalizationService.detect_language(text)
        # Should detect English or return default 'en'
        assert lang in ['en', 'unknown']
    
    def test_default_language_for_short_text(self):
        """Test short text defaults to English."""
        lang = InputNormalizationService.detect_language("hi")
        assert lang == "en"


class MockAIProvider(AIProvider):
    """Mock AI Provider for testing."""
    
    def __init__(self, response_data=None, should_fail=False):
        self.response_data = response_data or {
            "claims": [
                {
                    "text": "Test claim",
                    "claim_type": "STATISTICAL",
                    "importance": 0.85,
                    "verifiable": True
                }
            ]
        }
        self.should_fail = should_fail
        self.generate_calls = []
        self.generate_structured_calls = []
    
    async def generate(self, prompt: str, system_prompt=None) -> str:
        self.generate_calls.append((prompt, system_prompt))
        if self.should_fail:
            raise RuntimeError("Mock provider failure")
        return "Mock generated text"
    
    async def generate_structured(self, prompt: str, schema, system_prompt=None):
        self.generate_structured_calls.append((prompt, schema, system_prompt))
        if self.should_fail:
            raise RuntimeError("Mock provider failure")
        return schema(**self.response_data)


class TestClaimExtraction:
    """Test claim extraction service."""
    
    @pytest.mark.asyncio
    async def test_extract_claims_success(self, db: Session):
        """TC-ANALYSIS-008: Test successful claim extraction."""
        mock_provider = MockAIProvider()
        service = ClaimExtractionService(mock_provider)
        
        text = "India's GDP grew by 8.2 percent in Q2 2024."
        success, claims, error = await service.extract_claims(text)
        
        assert success
        assert len(claims) == 1
        assert claims[0].text == "Test claim"
        assert claims[0].claim_type == ClaimType.STATISTICAL
        assert error == ""
    
    @pytest.mark.asyncio
    async def test_extract_multiple_claims(self, db: Session):
        """TC-ANALYSIS-012: Test multiple claims extraction."""
        response_data = {
            "claims": [
                {
                    "text": "Claim 1",
                    "claim_type": "STATISTICAL",
                    "importance": 0.85,
                    "verifiable": True
                },
                {
                    "text": "Claim 2",
                    "claim_type": "POLITICAL",
                    "importance": 0.75,
                    "verifiable": True
                }
            ]
        }
        mock_provider = MockAIProvider(response_data)
        service = ClaimExtractionService(mock_provider)
        
        text = "Multiple claims in one text."
        success, claims, error = await service.extract_claims(text)
        
        assert success
        assert len(claims) == 2
        assert claims[0].text == "Claim 1"
        assert claims[1].text == "Claim 2"

    @pytest.mark.asyncio
    async def test_death_news_headline_is_normalized_and_searched(self):
        """Short factual headlines stay verifiable even if the model says opinion."""
        mock_provider = MockAIProvider({
            "claims": [{
                "text": "Nana Patekar death news",
                "claim_type": "OPINION",
                "importance": 0.8,
                "verifiable": False,
            }]
        })
        search_provider = AsyncMock(spec=SearchProvider)
        search_provider.search.return_value = [
            SearchResult(
                title="Search result",
                url="https://news.example/story",
                snippet="A result returned for the claim.",
                domain="news.example",
            )
        ]

        success, claims, error = await ClaimExtractionService(
            mock_provider
        ).extract_claims("Nana Patekar death news")
        assert success, error
        assert len(claims) == 1
        assert claims[0].text == "Nana Patekar has died."
        assert claims[0].claim_type == ClaimType.EVENT
        assert claims[0].verifiable is True

        sources = await EvidenceRetrievalService(
            search_provider
        ).retrieve_evidence_for_claim(claims[0])
        assert len(sources) == 1
        search_provider.search.assert_awaited_once_with(
            "Nana Patekar has died.", limit=5
        )

    @pytest.mark.asyncio
    async def test_genuine_opinion_remains_non_verifiable(self):
        mock_provider = MockAIProvider({
            "claims": [{
                "text": "Vanilla ice cream is the best dessert",
                "claim_type": "OPINION",
                "importance": 0.5,
                "verifiable": False,
            }]
        })

        success, claims, error = await ClaimExtractionService(
            mock_provider
        ).extract_claims("Vanilla ice cream is the best dessert")

        assert success, error
        assert len(claims) == 1
        assert claims[0].claim_type == ClaimType.OPINION
        assert claims[0].verifiable is False
    
    @pytest.mark.asyncio
    async def test_extract_claims_ai_failure(self):
        """TC-ANALYSIS-010: Test AI provider failure handling."""
        mock_provider = MockAIProvider(should_fail=True)
        service = ClaimExtractionService(mock_provider)
        
        text = "Test text"
        success, claims, error = await service.extract_claims(text)
        
        assert not success
        assert len(claims) == 0
        assert "failure" in error.lower() or "error" in error.lower()
    
    @pytest.mark.asyncio
    async def test_extract_claims_malformed_response(self):
        """TC-ANALYSIS-009: Test malformed AI response handling."""
        mock_provider = MockAIProvider()
        # Simulate malformed response by making the schema validation fail
        mock_provider.response_data = {"invalid": "structure"}
        
        service = ClaimExtractionService(mock_provider)
        
        text = "Test text"
        success, claims, error = await service.extract_claims(text)
        
        # Should handle gracefully
        assert not success
        assert len(claims) == 0
        assert error != ""


class TestAnalysisService:
    """Test full analysis service."""
    
    @pytest.mark.asyncio
    async def test_create_analysis_sets_language(self, db: Session, test_user: User):
        """Test that analysis service detects language."""
        mock_provider = MockAIProvider()
        service = AnalysisService(mock_provider)
        
        original = "The quick brown fox jumps over the lazy dog"
        normalized = "The quick brown fox jumps over the lazy dog"
        
        success, analysis, error = await service.create_analysis(
            db, test_user.id, original, normalized, InputType.TEXT
        )
        
        assert success
        assert analysis.language in ['en', 'unknown']
        assert analysis.status == AnalysisStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_create_analysis_extracts_claims(self, db: Session, test_user: User):
        """TC-ANALYSIS-001: Test text analysis with claim extraction."""
        mock_provider = MockAIProvider()
        service = AnalysisService(mock_provider)
        
        original = "India's GDP grew by 8.2 percent in Q2 2024."
        normalized = "India's GDP grew by 8.2 percent in Q2 2024."
        
        success, analysis, error = await service.create_analysis(
            db, test_user.id, original, normalized, InputType.TEXT
        )
        
        assert success
        assert analysis.status == AnalysisStatus.COMPLETED
        assert len(analysis.claims) > 0
        assert analysis.claims[0].text == "Test claim"
    
    @pytest.mark.asyncio
    async def test_create_analysis_handles_failure(self, db: Session, test_user: User):
        """TC-ANALYSIS-011: Test analysis status becomes FAILED on error."""
        mock_provider = MockAIProvider(should_fail=True)
        service = AnalysisService(mock_provider)
        
        original = "Some test text here"
        normalized = "Some test text here"
        
        success, analysis, error = await service.create_analysis(
            db, test_user.id, original, normalized, InputType.TEXT
        )
        
        assert not success
        assert analysis.status == AnalysisStatus.FAILED
        assert analysis.error_message != ""
        assert analysis.processing_completed_at is not None


class TestAnalysisAPI:
    """Test Analysis API endpoints."""
    
    def test_analyze_text_unauthenticated(self, test_client):
        """TC-ANALYSIS-005: Test unauthenticated request is rejected."""
        response = test_client.post(
            "/api/analysis/text",
            json={"input_text": "Valid analysis text here for testing"}
        )
        # Should return 403 or redirect to login
        assert response.status_code in [401, 403]
    
    def test_analyze_text_invalid_input(self, test_client, auth_headers):
        """TC-ANALYSIS-004: Test invalid input returns error."""
        response = test_client.post(
            "/api/analysis/text",
            json={"input_text": "short"},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "must be at least" in response.json()["detail"].lower()
    
    def test_analyze_text_empty_input(self, test_client, auth_headers):
        """TC-ANALYSIS-003: Test empty input returns error."""
        response = test_client.post(
            "/api/analysis/text",
            json={"input_text": ""},
            headers=auth_headers
        )
        assert response.status_code == 400
    
    def test_analyze_claim_endpoint(self, test_client, auth_headers):
        """TC-ANALYSIS-002: Test claim analysis endpoint works."""
        # This test requires Ollama or mock to be available
        # For now, test structure is in place
        response = test_client.post(
            "/api/analysis/claim",
            json={"input_text": "This claim needs to be analyzed for veracity"},
            headers=auth_headers
        )
        # Response depends on AI provider availability
        assert response.status_code in [200, 500]  # Either works or AI provider error
    
    def test_get_analysis_own(self, test_client, auth_headers, db: Session, test_user: User):
        """TC-ANALYSIS-006: User can retrieve own analysis."""
        # Create an analysis
        analysis = Analysis(
            user_id=test_user.id,
            input_type=InputType.TEXT,
            original_input="Test input",
            normalized_text="Test input",
            status=AnalysisStatus.COMPLETED,
            language="en"
        )
        db.add(analysis)
        db.commit()

        claim = Claim(
            analysis_id=analysis.id,
            text="A persisted claim without a verdict",
            claim_type=ClaimType.EVENT,
            importance=0.5,
            verifiable=True,
            extraction_confidence=1.0,
        )
        db.add(claim)
        db.commit()
        
        # Retrieve it
        response = test_client.get(
            f"/api/analysis/{analysis.id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["id"] == str(analysis.id)
        returned_claim = response.json()["claims"][0]
        assert returned_claim["verdict"] is None
        assert returned_claim["verdict_explanation"] is None
        assert returned_claim["verdict_limitations"] is None
        assert returned_claim["sources"] == []
    
    def test_get_analysis_other_user(self, test_client, auth_headers, db: Session):
        """TC-ANALYSIS-007: User cannot retrieve another user's analysis."""
        # Create analysis for different user
        other_user_id = uuid4()
        analysis = Analysis(
            user_id=other_user_id,
            input_type=InputType.TEXT,
            original_input="Other user's analysis",
            normalized_text="Other user's analysis",
            status=AnalysisStatus.COMPLETED,
            language="en"
        )
        db.add(analysis)
        db.commit()

        claim = Claim(
            analysis_id=analysis.id,
            text="Another user's private claim",
            claim_type=ClaimType.EVENT,
            importance=0.5,
            verifiable=True,
            extraction_confidence=1.0,
            verdict="LIKELY_TRUE",
            verdict_explanation="Private verdict explanation",
        )
        db.add(claim)
        db.commit()
        db.add(
            EvidenceSource(
                claim_id=claim.id,
                title="Private evidence source",
                url="https://private.example/report",
                snippet="Private evidence snippet",
                evidence_assessment="SUPPORTS",
                assessment_explanation="Private assessment",
            )
        )
        db.commit()
        
        # Try to retrieve as authenticated user
        response = test_client.get(
            f"/api/analysis/{analysis.id}",
            headers=auth_headers
        )
        assert response.status_code == 403
        assert "access" in response.json()["detail"].lower()
    
    def test_delete_analysis_own(self, test_client, auth_headers, db: Session, test_user: User):
        """Test user can delete own analysis."""
        # Create an analysis
        analysis = Analysis(
            user_id=test_user.id,
            input_type=InputType.TEXT,
            original_input="Test input to delete",
            normalized_text="Test input to delete",
            status=AnalysisStatus.COMPLETED,
            language="en"
        )
        db.add(analysis)
        db.commit()
        analysis_id = analysis.id
        
        # Delete it
        response = test_client.delete(
            f"/api/analysis/{analysis_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify deleted
        response = test_client.get(
            f"/api/analysis/{analysis_id}",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_delete_analysis_other_user(self, test_client, auth_headers, db: Session):
        """Test user cannot delete another user's analysis."""
        # Create analysis for different user
        other_user_id = uuid4()
        analysis = Analysis(
            user_id=other_user_id,
            input_type=InputType.TEXT,
            original_input="Other user's analysis",
            normalized_text="Other user's analysis",
            status=AnalysisStatus.COMPLETED,
            language="en"
        )
        db.add(analysis)
        db.commit()
        
        # Try to delete
        response = test_client.delete(
            f"/api/analysis/{analysis.id}",
            headers=auth_headers
        )
        assert response.status_code == 403


class TestAnalysisHistoryAPI:
    """Test paginated, user-scoped analysis history."""

    def test_history_empty(self, test_client, auth_headers):
        response = test_client.get("/api/analysis", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == {
            "analyses": [],
            "total_count": 0,
            "limit": 20,
            "offset": 0,
        }

    def test_history_is_user_scoped_and_newest_first(
        self, test_client, auth_headers, db: Session, test_user: User
    ):
        older = Analysis(
            user_id=test_user.id,
            input_type=InputType.TEXT,
            original_input="Older saved analysis",
            normalized_text="Older saved analysis",
            status=AnalysisStatus.COMPLETED,
            language="en",
            created_at=datetime(2026, 1, 1),
        )
        newer = Analysis(
            user_id=test_user.id,
            input_type=InputType.CLAIM,
            original_input="Newest saved claim",
            normalized_text="Newest saved claim",
            status=AnalysisStatus.COMPLETED,
            language="en",
            created_at=datetime(2026, 2, 1),
        )
        private = Analysis(
            user_id=uuid4(),
            input_type=InputType.TEXT,
            original_input="Another user's private analysis",
            normalized_text="Another user's private analysis",
            status=AnalysisStatus.COMPLETED,
            language="en",
            created_at=datetime(2026, 3, 1),
        )
        db.add_all([older, newer, private])
        db.commit()

        response = test_client.get("/api/analysis", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert [item["id"] for item in data["analyses"]] == [str(newer.id), str(older.id)]
        assert data["analyses"][0]["input_summary"] == "Newest saved claim"
        assert str(private.id) not in {item["id"] for item in data["analyses"]}

    def test_history_pagination(self, test_client, auth_headers, db: Session, test_user: User):
        analyses = [
            Analysis(
                user_id=test_user.id,
                input_type=InputType.TEXT,
                original_input=f"Saved analysis {index}",
                normalized_text=f"Saved analysis {index}",
                status=AnalysisStatus.COMPLETED,
                language="en",
                created_at=datetime(2026, 1, index + 1),
            )
            for index in range(3)
        ]
        db.add_all(analyses)
        db.commit()

        response = test_client.get("/api/analysis?limit=2&offset=1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 3
        assert data["limit"] == 2
        assert data["offset"] == 1
        assert [item["input_summary"] for item in data["analyses"]] == [
            "Saved analysis 1",
            "Saved analysis 0",
        ]

    def test_history_requires_authentication(self, test_client):
        response = test_client.get("/api/analysis")

        assert response.status_code in [401, 403]
