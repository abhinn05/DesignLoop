from datetime import datetime, timezone

import pytest

from lld_practice.domain.attempt import Attempt, AttemptStatus
from lld_practice.domain.errors import DomainError, SubmissionValidationError
from lld_practice.domain.rubric import RUBRIC
from lld_practice.domain.submission import TextDesignContent
from tests.designs import strong_parking, weak_parking

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _attempt() -> Attempt:
    return Attempt(
        id="a1",
        learner_id="l1",
        problem_id="parking-lot",
        status=AttemptStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
    )


def test_rubric_weights_sum_to_one():
    assert round(sum(item.weight for item in RUBRIC), 2) == 1.0


def test_submission_must_be_stored_before_it_can_be_evaluated():
    attempt = _attempt()
    content = TextDesignContent.from_dict(strong_parking())
    with pytest.raises(DomainError):
        attempt.begin_evaluation(NOW)
    attempt.mark_submitted(content, "sub-1", NOW)
    assert attempt.status is AttemptStatus.SUBMITTED
    assert attempt.submission_id == "sub-1"
    attempt.begin_evaluation(NOW)
    assert attempt.status is AttemptStatus.EVALUATING
    attempt.complete(NOW)
    assert attempt.status is AttemptStatus.COMPLETED


def test_failed_evaluation_can_be_retried_completed_cannot():
    attempt = _attempt()
    attempt.mark_submitted(TextDesignContent.from_dict(strong_parking()), "sub-1", NOW)
    attempt.begin_evaluation(NOW)
    attempt.fail("model timeout", NOW)
    assert attempt.failure_reason == "model timeout"
    attempt.begin_evaluation(NOW)
    attempt.complete(NOW)
    with pytest.raises(DomainError):
        attempt.begin_evaluation(NOW)
    with pytest.raises(DomainError):
        attempt.fail("again", NOW)


def test_draft_is_rejected_after_submit():
    attempt = _attempt()
    attempt.mark_submitted(TextDesignContent.from_dict(weak_parking()), "sub-1", NOW)
    with pytest.raises(DomainError):
        attempt.save_draft(TextDesignContent.from_dict(weak_parking()), NOW)


def test_thin_submission_is_rejected():
    content = TextDesignContent.from_dict(
        {
            "assumptions": "short",
            "classes": [{"name": "Lot", "responsibility": "parks", "collaborators": []}],
            "relationships": "",
            "tradeoffs": "",
            "extensibility": "",
            "edge_cases": "",
        }
    )
    with pytest.raises(SubmissionValidationError) as caught:
        content.validate()
    assert len(caught.value.errors) >= 3


def test_duplicate_class_names_are_rejected():
    design = strong_parking()
    design["classes"][1]["name"] = "ParkingLot"
    with pytest.raises(SubmissionValidationError) as caught:
        TextDesignContent.from_dict(design).validate()
    assert any("unique" in error for error in caught.value.errors)
