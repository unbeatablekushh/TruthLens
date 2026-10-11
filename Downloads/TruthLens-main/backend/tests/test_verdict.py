"""Focused tests for evidence-based verdict evaluation."""

import pytest

from app.models.analysis import Claim, EvidenceSource
from app.services.verdict import VerdictService


class AssessmentProvider:
    """Return controlled evidence assessments without calling an external LLM."""

    def __init__(self, assessments=None, should_fail=False):
        self.assessments = iter(assessments or [])
        self.should_fail = should_fail

    async def generate_structured(self, prompt, schema, system_prompt=None):
        if self.should_fail:
            raise RuntimeError("Mock provider unavailable")

        return schema(
            assessment=next(self.assessments),
            explanation="The supplied snippet was assessed against the claim.",
        )

    async def generate(self, prompt, system_prompt=None):
        if self.should_fail:
            raise RuntimeError("Mock provider unavailable")
        return "The explanation is based on the assessed evidence."


def make_claim(assessments, domains=None):
    domains = domains or [f"source-{index}.example" for index in range(len(assessments))]
    claim = Claim(text="The city expanded its rail network in 2024.", verifiable=True)
    claim.sources = [
        EvidenceSource(
            title=f"Evidence source {index}",
            url=f"https://{domain}/report-{index}",
            snippet="A retrieved report about the city's rail network expansion.",
            domain=domain,
        )
        for index, domain in enumerate(domains)
    ]
    return claim


@pytest.mark.asyncio
async def test_independent_supporting_evidence_is_likely_true():
    claim = make_claim(["SUPPORTS", "SUPPORTS"])
    service = VerdictService(AssessmentProvider(["SUPPORTS", "SUPPORTS"]))

    await service.evaluate_claim(None, claim)

    assert claim.verdict == "LIKELY_TRUE"
    assert all(source.evidence_assessment == "SUPPORTS" for source in claim.sources)


@pytest.mark.asyncio
async def test_independent_contradicting_evidence_is_likely_false():
    claim = make_claim(["CONTRADICTS", "CONTRADICTS"])
    service = VerdictService(AssessmentProvider(["CONTRADICTS", "CONTRADICTS"]))

    await service.evaluate_claim(None, claim)

    assert claim.verdict == "LIKELY_FALSE"


@pytest.mark.asyncio
async def test_conflicting_evidence_is_partially_true():
    claim = make_claim(["SUPPORTS", "CONTRADICTS"])
    service = VerdictService(AssessmentProvider(["SUPPORTS", "CONTRADICTS"]))

    await service.evaluate_claim(None, claim)

    assert claim.verdict == "PARTIALLY_TRUE"


@pytest.mark.asyncio
async def test_missing_evidence_is_insufficient():
    claim = make_claim([])
    service = VerdictService(AssessmentProvider())

    await service.evaluate_claim(None, claim)

    assert claim.verdict == "INSUFFICIENT_EVIDENCE"
    assert "verification could not be completed" in claim.verdict_explanation.lower()
    assert "no evidence sources were retrieved" in claim.verdict_explanation.lower()


@pytest.mark.asyncio
async def test_irrelevant_evidence_is_insufficient():
    claim = make_claim(["IRRELEVANT"])
    service = VerdictService(AssessmentProvider(["IRRELEVANT"]))

    await service.evaluate_claim(None, claim)

    assert claim.verdict == "INSUFFICIENT_EVIDENCE"


@pytest.mark.asyncio
async def test_duplicate_domain_does_not_count_as_independent_support():
    claim = make_claim(["SUPPORTS", "SUPPORTS"], ["same.example", "same.example"])
    service = VerdictService(AssessmentProvider(["SUPPORTS", "SUPPORTS"]))

    await service.evaluate_claim(None, claim)

    assert claim.verdict == "UNVERIFIED"


@pytest.mark.asyncio
async def test_provider_failure_does_not_invent_a_verdict():
    claim = make_claim(["SUPPORTS", "SUPPORTS"])
    service = VerdictService(AssessmentProvider(should_fail=True))

    await service.evaluate_claim(None, claim)

    assert claim.verdict == "INSUFFICIENT_EVIDENCE"
    assert all(source.evidence_assessment == "IRRELEVANT" for source in claim.sources)
    assert all("unavailable" in source.assessment_explanation.lower() for source in claim.sources)