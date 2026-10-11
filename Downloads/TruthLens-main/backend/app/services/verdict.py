"""
Verdict Service for TruthLens.

Evaluates extracted claims using retrieved evidence sources to produce
one of five transparent verdicts:
    LIKELY_TRUE
    PARTIALLY_TRUE
    UNVERIFIED
    LIKELY_FALSE
    INSUFFICIENT_EVIDENCE

Design principles:
- Verdict calculation is rule-based and fully documented here.
- The LLM classifies individual evidence snippets only.
- Verdict scoring is deterministic given the assessment counts.
- If the LLM is unavailable, the service falls back to INSUFFICIENT_EVIDENCE
  with an honest explanation rather than fabricating a result.
- Duplicate source domains are de-weighted to avoid inflated counts from
  a single outlet's multiple pages.
"""

import logging
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.providers import AIProvider
from app.models.analysis import Claim, EvidenceSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Verdict constants
# ---------------------------------------------------------------------------

VERDICT_LIKELY_TRUE = "LIKELY_TRUE"
VERDICT_PARTIALLY_TRUE = "PARTIALLY_TRUE"
VERDICT_UNVERIFIED = "UNVERIFIED"
VERDICT_LIKELY_FALSE = "LIKELY_FALSE"
VERDICT_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

ASSESSMENT_SUPPORTS = "SUPPORTS"
ASSESSMENT_CONTRADICTS = "CONTRADICTS"
ASSESSMENT_MIXED = "MIXED"
ASSESSMENT_IRRELEVANT = "IRRELEVANT"


# ---------------------------------------------------------------------------
# LLM response schema for a single evidence assessment
# ---------------------------------------------------------------------------

class EvidenceAssessmentResponse(BaseModel):
    """Structured LLM response for a single source assessment."""
    assessment: str = Field(
        ...,
        description="One of: SUPPORTS, CONTRADICTS, MIXED, IRRELEVANT"
    )
    explanation: str = Field(
        ...,
        description="One-sentence reason for the assessment"
    )


# ---------------------------------------------------------------------------
# Scoring rules (documented transparently)
# ---------------------------------------------------------------------------

def _compute_verdict(support_count: int, contradict_count: int,
                     mixed_count: int, irrelevant_count: int,
                     total_sources: int) -> Tuple[str, str]:
    """
    Compute a verdict using simple, transparent threshold rules.

    Scoring rules (in priority order):
    1. No sources at all → INSUFFICIENT_EVIDENCE
    2. All assessments are IRRELEVANT or no useful assessments → INSUFFICIENT_EVIDENCE
    3. support_count > 0 and contradict_count == 0 and support_count >= 2
         → LIKELY_TRUE
    4. contradict_count > 0 and support_count == 0 and contradict_count >= 2
         → LIKELY_FALSE
    5. support_count >= 1 and contradict_count == 0
         → UNVERIFIED  (only one supporting source, not enough for LIKELY_TRUE)
    6. contradict_count >= 1 and support_count == 0
         → UNVERIFIED  (only one contradicting source)
    7. support_count > 0 and contradict_count > 0
         → PARTIALLY_TRUE  (conflicting evidence)
    8. mixed_count > 0 and support_count == 0 and contradict_count == 0
         → UNVERIFIED
    9. Fallback → UNVERIFIED

    Returns:
        (verdict, short_reason)
    """
    useful = support_count + contradict_count + mixed_count

    if total_sources == 0:
        return (
            VERDICT_INSUFFICIENT_EVIDENCE,
            "No sources were retrieved for this claim."
        )

    if useful == 0:
        return (
            VERDICT_INSUFFICIENT_EVIDENCE,
            "All retrieved sources were irrelevant to this claim."
        )

    if support_count >= 2 and contradict_count == 0:
        return (
            VERDICT_LIKELY_TRUE,
            f"{support_count} independent source(s) support this claim and none contradict it."
        )

    if contradict_count >= 2 and support_count == 0:
        return (
            VERDICT_LIKELY_FALSE,
            f"{contradict_count} independent source(s) contradict this claim and none support it."
        )

    if support_count >= 1 and contradict_count == 0:
        return (
            VERDICT_UNVERIFIED,
            f"Only {support_count} supporting source(s) found; more evidence is needed to confirm."
        )

    if contradict_count >= 1 and support_count == 0:
        return (
            VERDICT_UNVERIFIED,
            f"Only {contradict_count} contradicting source(s) found; more evidence is needed to refute."
        )

    if support_count > 0 and contradict_count > 0:
        return (
            VERDICT_PARTIALLY_TRUE,
            f"Conflicting evidence: {support_count} source(s) support and {contradict_count} contradict this claim."
        )

    if mixed_count > 0:
        return (
            VERDICT_UNVERIFIED,
            f"{mixed_count} source(s) contain mixed signals; the claim cannot be clearly confirmed or denied."
        )

    return VERDICT_UNVERIFIED, "Insufficient clear evidence to reach a conclusion."


# ---------------------------------------------------------------------------
# Fallback explanation templates (used when LLM is offline)
# ---------------------------------------------------------------------------

_VERDICT_TEMPLATES = {
    VERDICT_LIKELY_TRUE: (
        "Multiple independent sources support this claim. "
        "While no automatic system is infallible, the available evidence is consistent with the claim being true."
    ),
    VERDICT_PARTIALLY_TRUE: (
        "The evidence is mixed. Some sources support aspects of this claim while others contradict it. "
        "The full picture may depend on context or specific details."
    ),
    VERDICT_UNVERIFIED: (
        "The available evidence is insufficient to confirm or deny this claim. "
        "Only a small number of sources were found and they do not establish a clear pattern."
    ),
    VERDICT_LIKELY_FALSE: (
        "Multiple independent sources contradict this claim and none were found to support it. "
        "This does not constitute proof of falsity; further authoritative sources should be consulted."
    ),
    VERDICT_INSUFFICIENT_EVIDENCE: (
        "No relevant evidence was found for this claim. "
        "This may be because the claim is too obscure, the search provider returned no results, "
        "or the AI assistant is currently unavailable."
    ),
}

_LIMITATIONS_TEMPLATE = (
    "This assessment is based solely on web search snippets and automated AI classification. "
    "Snippets may be incomplete or out of context. "
    "TruthLens does not guarantee accuracy. Always verify important claims with primary sources."
)


# ---------------------------------------------------------------------------
# VerdictService
# ---------------------------------------------------------------------------

class VerdictService:
    """
    Evaluates a claim using its retrieved evidence sources.

    Steps:
    1. For each EvidenceSource with a snippet, ask the LLM to classify
       whether the snippet SUPPORTS, CONTRADICTS, is MIXED, or is IRRELEVANT
       relative to the claim text.
    2. De-weight duplicate domains (only the first source per domain contributes
       to the vote count).
    3. Apply documented scoring rules to choose a verdict.
    4. Ask the LLM to write a concise explanation (falls back to template if
       LLM is offline).
    5. Store assessment fields on each EvidenceSource and verdict fields on Claim.
    """

    # Prompt template for per-source classification
    CLASSIFICATION_PROMPT = (
        "You are a neutral fact-checking assistant.\n\n"
        "Claim: {claim}\n\n"
        "Evidence snippet from {domain}:\n\"{snippet}\"\n\n"
        "Classify the relationship of this snippet to the claim.\n"
        "Return ONLY a JSON object with two fields:\n"
        '  "assessment": one of SUPPORTS, CONTRADICTS, MIXED, IRRELEVANT\n'
        '  "explanation": one sentence (max 20 words) explaining why\n\n'
        "Rules:\n"
        "- SUPPORTS: snippet clearly backs the claim\n"
        "- CONTRADICTS: snippet clearly refutes the claim\n"
        "- MIXED: snippet is partly consistent and partly inconsistent\n"
        "- IRRELEVANT: snippet does not address the claim\n"
        "Return ONLY valid JSON."
    )

    EXPLANATION_PROMPT = (
        "You are a neutral fact-checking assistant.\n\n"
        "Claim: {claim}\n\n"
        "Verdict: {verdict}\n"
        "Reasoning: {reason}\n"
        "Supporting sources: {support_count}\n"
        "Contradicting sources: {contradict_count}\n\n"
        "Write a concise, factual explanation (2-3 sentences) for why this verdict was reached. "
        "Do not assert that the claim is definitively true or false unless the verdict is LIKELY_TRUE "
        "or LIKELY_FALSE. Do not invent facts. "
        "Return ONLY the explanation text, no JSON."
    )

    def __init__(self, ai_provider: Optional[AIProvider] = None):
        self.ai_provider = ai_provider

    async def _classify_source(
        self, claim_text: str, source: EvidenceSource
    ) -> Tuple[str, str]:
        """
        Ask the LLM to classify a single evidence source.

        Returns:
            (assessment, explanation) — falls back to IRRELEVANT on failure.
        """
        snippet = (source.snippet or "").strip()
        if not snippet:
            return ASSESSMENT_IRRELEVANT, "No snippet available to assess."

        if self.ai_provider is None:
            return ASSESSMENT_IRRELEVANT, "AI provider unavailable."

        prompt = self.CLASSIFICATION_PROMPT.format(
            claim=claim_text,
            domain=source.domain or source.url,
            snippet=snippet[:1000],  # Truncate very long snippets
        )

        try:
            result = await self.ai_provider.generate_structured(
                prompt=prompt,
                schema=EvidenceAssessmentResponse,
                system_prompt="You are a precise fact-checking AI. Respond only with the JSON object.",
            )
            # Validate the assessment value
            valid = {ASSESSMENT_SUPPORTS, ASSESSMENT_CONTRADICTS,
                     ASSESSMENT_MIXED, ASSESSMENT_IRRELEVANT}
            assessment = result.assessment.upper()
            if assessment not in valid:
                assessment = ASSESSMENT_IRRELEVANT
            return assessment, result.explanation
        except RuntimeError as e:
            logger.warning(f"LLM classification failed for source {source.url}: {e}")
            return ASSESSMENT_IRRELEVANT, "LLM classification unavailable."
        except Exception as e:
            logger.warning(f"Unexpected error classifying source {source.url}: {e}")
            return ASSESSMENT_IRRELEVANT, "Classification error."

    async def _generate_explanation(
        self,
        claim_text: str,
        verdict: str,
        reason: str,
        support_count: int,
        contradict_count: int,
    ) -> str:
        """
        Ask the LLM to write a natural-language explanation.
        Falls back to a template if LLM is unavailable.
        """
        if self.ai_provider is None:
            return _VERDICT_TEMPLATES.get(verdict, _VERDICT_TEMPLATES[VERDICT_UNVERIFIED])

        prompt = self.EXPLANATION_PROMPT.format(
            claim=claim_text,
            verdict=verdict,
            reason=reason,
            support_count=support_count,
            contradict_count=contradict_count,
        )
        try:
            text = await self.ai_provider.generate(
                prompt=prompt,
                system_prompt="You are a neutral fact-checking assistant. Write concise, accurate explanations.",
            )
            if not isinstance(text, str):
                logger.warning("LLM explanation response was not text; using a template")
                return _VERDICT_TEMPLATES.get(verdict, _VERDICT_TEMPLATES[VERDICT_UNVERIFIED])
            return text.strip()[:1000]
        except RuntimeError as e:
            logger.warning(f"LLM explanation generation failed: {e}")
            return _VERDICT_TEMPLATES.get(verdict, _VERDICT_TEMPLATES[VERDICT_UNVERIFIED])

    async def evaluate_claim(self, db: Session, claim: Claim) -> None:
        """
        Evaluate a single claim in-place, updating claim.verdict,
        claim.verdict_explanation, claim.verdict_limitations,
        and each source's evidence_assessment / assessment_explanation.

        Changes are NOT committed here — the caller handles commits.
        """
        sources: List[EvidenceSource] = claim.sources or []

        # --- Non-verifiable claims get INSUFFICIENT_EVIDENCE immediately ---
        if not claim.verifiable:
            claim.verdict = VERDICT_INSUFFICIENT_EVIDENCE
            claim.verdict_explanation = (
                "This claim was classified as subjective or not factually verifiable, "
                "so no verdict was produced."
            )
            claim.verdict_limitations = _LIMITATIONS_TEMPLATE
            return

        # --- Classify each source, de-duplicate by domain ---
        if not sources:
            claim.verdict = VERDICT_INSUFFICIENT_EVIDENCE
            claim.verdict_explanation = (
                "Verification could not be completed because no evidence sources "
                "were retrieved for this claim."
            )
            claim.verdict_limitations = _LIMITATIONS_TEMPLATE
            return

        seen_domains: set = set()
        support_count = 0
        contradict_count = 0
        mixed_count = 0
        irrelevant_count = 0

        for source in sources:
            assessment, explanation = await self._classify_source(claim.text, source)
            source.evidence_assessment = assessment
            source.assessment_explanation = explanation

            # De-weight: only the first source per domain contributes to the vote
            domain_key = source.domain or source.url
            if domain_key in seen_domains:
                continue
            seen_domains.add(domain_key)

            if assessment == ASSESSMENT_SUPPORTS:
                support_count += 1
            elif assessment == ASSESSMENT_CONTRADICTS:
                contradict_count += 1
            elif assessment == ASSESSMENT_MIXED:
                mixed_count += 1
            else:
                irrelevant_count += 1

        # --- Apply scoring rules ---
        verdict, reason = _compute_verdict(
            support_count, contradict_count, mixed_count,
            irrelevant_count, len(sources)
        )

        # --- Generate explanation ---
        explanation_text = await self._generate_explanation(
            claim.text, verdict, reason, support_count, contradict_count
        )

        # --- Persist to claim ---
        claim.verdict = verdict
        claim.verdict_explanation = explanation_text
        claim.verdict_limitations = _LIMITATIONS_TEMPLATE

        logger.info(
            f"Verdict for claim '{claim.text[:60]}': {verdict} "
            f"(support={support_count}, contradict={contradict_count}, "
            f"mixed={mixed_count}, irrelevant={irrelevant_count})"
        )

    async def evaluate_analysis(self, db: Session, analysis) -> None:
        """
        Evaluate all claims in an analysis and commit results.
        """
        for claim in analysis.claims:
            await self.evaluate_claim(db, claim)

        try:
            db.commit()
            db.refresh(analysis)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to persist verdicts for analysis {analysis.id}: {e}")
