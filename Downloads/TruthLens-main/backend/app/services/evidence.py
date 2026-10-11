"""
Evidence Retrieval Service for TruthLens.

Retrieves web evidence for extracted claims using configured SearchProvider.
Associates retrieved sources with claims and updates evidence status.
"""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.providers import SearchProvider, SearchResult
from app.models.analysis import Claim, EvidenceSource, Analysis
from app.providers.search import extract_domain, get_default_search_provider

logger = logging.getLogger(__name__)


class EvidenceRetrievalService:
    """
    Coordinates evidence retrieval for claims.
    """

    def __init__(self, search_provider: Optional[SearchProvider] = None):
        self.search_provider = search_provider or get_default_search_provider()

    async def retrieve_evidence_for_claim(self, claim: Claim) -> List[EvidenceSource]:
        """
        Retrieve search evidence for a single claim.
        """
        # If claim is non-verifiable (e.g. opinion), do not search
        if not claim.verifiable:
            claim.evidence_status = "INSUFFICIENT_EVIDENCE"
            claim.evidence_note = "Claim classified as subjective or not factually verifiable."
            return []

        try:
            # Query search provider for the claim text
            results: List[SearchResult] = await self.search_provider.search(claim.text, limit=5)

            if not results:
                claim.evidence_status = "INSUFFICIENT_EVIDENCE"
                claim.evidence_note = "No reliable external sources found for this claim."
                return []

            # Deduplicate by URL
            seen_urls = set()
            sources: List[EvidenceSource] = []

            for r in results:
                if not r.url or r.url in seen_urls:
                    continue
                seen_urls.add(r.url)

                source = EvidenceSource(
                    claim_id=claim.id,
                    title=r.title[:500],
                    url=r.url[:2048],
                    snippet=(r.snippet[:500] if r.snippet else None),
                    domain=r.domain or extract_domain(r.url),
                    published_date=r.published_date[:100] if r.published_date else None,
                )
                sources.append(source)

            if sources:
                claim.evidence_status = "EVIDENCE_RETRIEVED"
                claim.evidence_note = f"Retrieved {len(sources)} source(s)."
                claim.sources = sources
            else:
                claim.evidence_status = "INSUFFICIENT_EVIDENCE"
                claim.evidence_note = "No valid sources found after parsing search results."

            return sources

        except Exception as e:
            logger.warning(f"Evidence retrieval failed for claim '{claim.text[:50]}': {e}")
            claim.evidence_status = "INSUFFICIENT_EVIDENCE"
            claim.evidence_note = "Search provider unavailable or timed out."
            return []

    async def retrieve_evidence_for_analysis(self, db: Session, analysis: Analysis) -> None:
        """
        Retrieve evidence for all claims in an analysis and persist sources.
        """
        for claim in analysis.claims:
            sources = await self.retrieve_evidence_for_claim(claim)
            for s in sources:
                s.claim_id = claim.id
                db.add(s)

        try:
            db.commit()
            db.refresh(analysis)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to persist evidence sources for analysis {analysis.id}: {e}")
