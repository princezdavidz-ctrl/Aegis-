"""Strict, bounded contracts for evidence-grounded security analysis."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class EvidenceItem(BaseModel):
    """A bounded, tenant-scoped evidence fragment supplied by a trusted caller."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")
    source_type: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_-]*$")
    observed_at: str | None = Field(default=None, max_length=40)
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def reject_empty_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evidence content must not be blank")
        return value.strip()


class AnalysisRequest(BaseModel):
    """A bounded analysis request; tenant identity is deliberately not client-set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task: str = Field(min_length=1, max_length=1200)
    evidence: tuple[EvidenceItem, ...] = Field(min_length=1, max_length=30)

    @field_validator("task")
    @classmethod
    def normalize_task(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("task must not be blank")
        return normalized

    @model_validator(mode="after")
    def evidence_ids_are_unique(self) -> AnalysisRequest:
        identifiers = [item.evidence_id for item in self.evidence]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("evidence_id values must be unique")
        if sum(len(item.content) for item in self.evidence) > 60000:
            raise ValueError("combined evidence exceeds the 60000-character limit")
        return self


class SecurityFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(min_length=3, max_length=160)
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(min_length=1, max_length=2000)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=10)
    recommended_actions: tuple[str, ...] = Field(min_length=1, max_length=8)

    @field_validator("title", "explanation")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text fields must not be blank")
        return value.strip()


class AnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str = Field(min_length=1, max_length=2000)
    findings: tuple[SecurityFinding, ...] = Field(max_length=20)
    limitations: tuple[str, ...] = Field(max_length=12)
    requires_human_review: bool = True

    @model_validator(mode="after")
    def findings_must_reference_supplied_evidence(self) -> AnalysisResult:
        supplied_ids = set(self._context_evidence_ids)
        for finding in self.findings:
            if not set(finding.evidence_ids).issubset(supplied_ids):
                raise ValueError("findings may reference only supplied evidence IDs")
        return self

    # Populated only by validate_analysis_result below; excluded from JSON schema.
    _context_evidence_ids: frozenset[str] = frozenset()


def validate_analysis_result(payload: object, request: AnalysisRequest) -> AnalysisResult:
    """Validate model output and enforce evidence references against this request."""

    result = AnalysisResult.model_validate(payload)
    allowed_ids = {item.evidence_id for item in request.evidence}
    for finding in result.findings:
        if not set(finding.evidence_ids).issubset(allowed_ids):
            raise ValueError("model output referenced evidence not present in the request")
    return result
