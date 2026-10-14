from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from lld_practice.domain.errors import DomainError
from lld_practice.domain.submission import DesignContent


class AttemptStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"


_STARTABLE = {AttemptStatus.SUBMITTED, AttemptStatus.FAILED}


@dataclass
class Attempt:
    """One practice run. The status is the only legal way evaluation can move."""

    id: str
    learner_id: str
    problem_id: str
    status: AttemptStatus
    created_at: datetime
    updated_at: datetime
    draft: DesignContent | None = None
    submission_id: str | None = None
    failure_reason: str | None = None

    def save_draft(self, content: DesignContent, now: datetime) -> None:
        if self.status is not AttemptStatus.DRAFT:
            raise DomainError(
                "Drafts can only be saved before submission.",
                status_code=409,
            )
        self.draft = content
        self.updated_at = now

    def mark_submitted(self, content: DesignContent, submission_id: str, now: datetime) -> None:
        if self.status is not AttemptStatus.DRAFT:
            raise DomainError(
                "This attempt was already submitted. Start another attempt to revise.",
                status_code=409,
            )
        content.validate()
        self.draft = content
        self.submission_id = submission_id
        self.status = AttemptStatus.SUBMITTED
        self.failure_reason = None
        self.updated_at = now

    def begin_evaluation(self, now: datetime) -> None:
        if self.status not in _STARTABLE:
            raise DomainError(
                "Evaluation can start only from a saved submission or a failed run.",
                status_code=409,
            )
        self.status = AttemptStatus.EVALUATING
        self.failure_reason = None
        self.updated_at = now

    def complete(self, now: datetime) -> None:
        if self.status is not AttemptStatus.EVALUATING:
            raise DomainError(
                "Only an in-progress evaluation can be completed.",
                status_code=409,
            )
        self.status = AttemptStatus.COMPLETED
        self.failure_reason = None
        self.updated_at = now

    def fail(self, reason: str, now: datetime) -> None:
        if self.status is not AttemptStatus.EVALUATING:
            raise DomainError(
                "Only an in-progress evaluation can fail.",
                status_code=409,
            )
        self.status = AttemptStatus.FAILED
        self.failure_reason = reason.strip() or "Evaluation failed."
        self.updated_at = now


@dataclass(frozen=True)
class Learner:
    id: str
    display_name: str
    created_at: datetime
