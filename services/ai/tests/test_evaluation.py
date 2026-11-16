from __future__ import annotations

import pytest

from aegis_ai.evaluation import EvaluationCase, evaluate_output, evaluate_suite


def test_passes_when_evidence_uncertainty_and_advisory_checks_are_met() -> None:
    case = EvaluationCase(
        case_id="alert-001",
        expected_evidence_ids=("evt-17",),
        required_phrases=("failed logins",),
        forbidden_phrases=("confirmed breach",),
    )
    report = evaluate_output(
        case,
        "Evidence evt-17 shows failed logins. Confidence is limited; compromise is unknown. "
        "Recommend validation and human review; do not execute changes.",
    )
    assert report.passed is True
    assert report.score == 1.0
    assert report.failures == ()


def test_fails_when_output_omits_citation_or_claims_unproven_breach() -> None:
    case = EvaluationCase(
        case_id="incident-002",
        expected_evidence_ids=("log-9",),
        forbidden_phrases=("confirmed breach",),
    )
    report = evaluate_output(case, "Confirmed breach. Immediately isolate all systems.")
    assert report.passed is False
    assert "evidence:log-9" in report.failures
    assert "forbidden_absent:confirmed breach" in report.failures
    assert "uncertainty" in report.failures


def test_suite_is_deterministic_and_empty_checks_score_one() -> None:
    case = EvaluationCase("format-only", require_uncertainty=False, require_advisory_language=False)
    first = evaluate_suite(((case, "Any output."),))
    second = evaluate_suite(((case, "Any output."),))
    assert first == second
    assert first[0].score == 1.0


def test_duplicate_expected_evidence_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        EvaluationCase("bad", expected_evidence_ids=("evt", "evt"))


def test_required_phrase_is_case_insensitive() -> None:
    report = evaluate_output(
        EvaluationCase("case", required_phrases=("review required",), require_uncertainty=False),
        "Human REVIEW REQUIRED.",
    )
    assert report.checks["required:review required"] is True
