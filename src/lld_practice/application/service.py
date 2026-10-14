import re
import threading
from collections.abc import Callable
from datetime import datetime, timezone

from lld_practice.domain.attempt import Attempt, AttemptStatus, Learner
from lld_practice.domain.errors import DomainError, SubmissionValidationError
from lld_practice.domain.evaluation import EvaluationRecord, overall_score
from lld_practice.domain.problem import ProblemCatalog
from lld_practice.domain.rubric import RUBRIC
from lld_practice.domain.submission import Submission, SubmissionFormat, TextDesignContent
from lld_practice.evaluation.pipeline import EvaluationPipeline
from lld_practice.infrastructure.repository import SqliteRepository

_KEY = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
_INTERRUPTED = "Evaluation was interrupted before it finished. Your submission is saved."


class PracticeService:
    """Use cases for the practice loop. Persistence happens before evaluation."""

    def __init__(
        self,
        repo: SqliteRepository,
        catalog: ProblemCatalog,
        pipeline: EvaluationPipeline,
        *,
        clock: Callable[[], datetime] | None = None,
        ids: Callable[[], str] | None = None,
    ) -> None:
        self.repo = repo
        self.catalog = catalog
        self.pipeline = pipeline
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.ids = ids or _default_id
        self._inflight: set[str] = set()
        self._eval_lock = threading.Lock()

    def create_learner(self, display_name: str) -> Learner:
        name = " ".join(display_name.split())
        if not name or len(name) > 40:
            raise DomainError("Use a name between 1 and 40 characters.")
        if any(ord(char) < 32 for char in name):
            raise DomainError("The name contains characters that cannot be stored.")
        learner = Learner(self.ids(), name, self.clock())
        self.repo.create_learner(learner)
        return learner

    def start_attempt(
        self,
        learner_id: str,
        problem_id: str,
        from_attempt_id: str | None = None,
    ) -> Attempt:
        self._require_learner(learner_id)
        self.catalog.get(problem_id)
        now = self.clock()
        draft = None
        if from_attempt_id:
            previous = self._require_attempt(from_attempt_id)
            if previous.learner_id != learner_id or previous.problem_id != problem_id:
                raise DomainError("A revision has to stay on the same problem and learner.", status_code=409)
            submission = self.repo.get_submission(previous.id)
            if submission is not None:
                draft = submission.content
            elif previous.draft is not None:
                draft = previous.draft
        attempt = Attempt(
            id=self.ids(),
            learner_id=learner_id,
            problem_id=problem_id,
            status=AttemptStatus.DRAFT,
            created_at=now,
            updated_at=now,
            draft=draft,
        )
        self.repo.insert_attempt(attempt)
        return attempt

    def save_draft(self, attempt_id: str, content: TextDesignContent) -> Attempt:
        attempt = self._require_attempt(attempt_id)
        attempt.save_draft(content, self.clock())
        self.repo.update_draft(attempt)
        return self._require_attempt(attempt_id)

    def submit(self, attempt_id: str, content: TextDesignContent, idempotency_key: str) -> tuple[Attempt, bool]:
        """Store the submission. Returns (attempt, created). Does not evaluate."""
        self._check_key(idempotency_key)
        attempt = self._require_attempt(attempt_id)
        try:
            content.validate()
        except SubmissionValidationError:
            if attempt.status is AttemptStatus.DRAFT:
                attempt.save_draft(content, self.clock())
                self.repo.update_draft(attempt)
            raise

        if attempt.status is not AttemptStatus.DRAFT:
            existing = self.repo.get_submission(attempt.id)
            if existing is not None and existing.idempotency_key == idempotency_key:
                return self._require_attempt(attempt.id), False
            raise DomainError(
                "This attempt was already submitted. Start another attempt to revise.",
                status_code=409,
            )

        now = self.clock()
        submission = Submission(
            id=self.ids(),
            attempt_id=attempt.id,
            format=SubmissionFormat.TEXT_DESIGN,
            content=content,
            idempotency_key=idempotency_key,
            submitted_at=now,
        )
        attempt.mark_submitted(content, submission.id, now)
        outcome = self.repo.commit_submission(attempt, submission)
        return self._require_attempt(attempt.id), outcome == "created"

    def run_evaluation(self, attempt_id: str) -> None:
        with self._eval_lock:
            if attempt_id in self._inflight:
                return
            attempt = self.repo.get_attempt(attempt_id)
            if attempt is None or attempt.status not in (AttemptStatus.SUBMITTED, AttemptStatus.FAILED):
                return
            if not self.repo.mark_evaluating(attempt_id, self.clock()):
                return
            self._inflight.add(attempt_id)
        try:
            submission = self.repo.get_submission(attempt_id)
            if submission is None:
                self.repo.mark_failed(attempt_id, "Submission was missing.", self.clock())
                return
            problem = self.catalog.get(attempt.problem_id)
            try:
                outcome = self.pipeline.evaluate(problem, submission)
            except Exception as exc:
                message = str(exc).strip() or exc.__class__.__name__
                self.repo.add_evaluation(
                    EvaluationRecord(
                        id=self.ids(),
                        attempt_id=attempt_id,
                        status="failed",
                        feedback=(),
                        summary="Evaluation did not finish. Your submission is saved.",
                        overall_score=None,
                        note="",
                        error=message,
                        created_at=self.clock(),
                    )
                )
                self.repo.mark_failed(attempt_id, message, self.clock())
                return
            self.repo.add_evaluation(
                EvaluationRecord(
                    id=self.ids(),
                    attempt_id=attempt_id,
                    status="completed",
                    feedback=outcome.feedback,
                    summary=outcome.summary,
                    overall_score=overall_score(outcome.feedback),
                    note=outcome.note,
                    error=None,
                    created_at=self.clock(),
                )
            )
            self.repo.mark_completed(attempt_id, self.clock())
        finally:
            with self._eval_lock:
                self._inflight.discard(attempt_id)

    def recover_interrupted(self) -> int:
        return self.repo.recover_interrupted(_INTERRUPTED, self.clock())

    def insights(self, learner_id: str) -> dict:
        self._require_learner(learner_id)
        totals = {item.id: [] for item in RUBRIC}
        completed = 0
        attempts = self.repo.list_attempts(learner_id)
        for attempt in attempts:
            if attempt.status is not AttemptStatus.COMPLETED:
                continue
            evaluation = self.repo.latest_evaluation(attempt.id)
            if evaluation is None or evaluation.status != "completed":
                continue
            completed += 1
            for item in evaluation.feedback:
                if item.criterion_id in totals:
                    totals[item.criterion_id].append(item.score)
        averages = []
        for criterion in RUBRIC:
            scores = totals[criterion.id]
            if not scores:
                continue
            averages.append(
                {
                    "criterion_id": criterion.id,
                    "title": criterion.title,
                    "average": round(sum(scores) / len(scores), 2),
                }
            )
        weakest = min(averages, key=lambda row: (row["average"], row["criterion_id"])) if averages else None
        return {
            "attempt_count": len(attempts),
            "completed_count": completed,
            "averages": averages,
            "weakest": weakest,
        }

    def comparison(self, attempt: Attempt) -> dict | None:
        if attempt.status is not AttemptStatus.COMPLETED:
            return None
        current = self.repo.latest_evaluation(attempt.id)
        if current is None:
            return None
        previous_attempt = None
        for candidate in self.repo.list_attempts(attempt.learner_id):
            if candidate.id == attempt.id or candidate.problem_id != attempt.problem_id:
                continue
            if candidate.status is not AttemptStatus.COMPLETED:
                continue
            if candidate.created_at >= attempt.created_at:
                continue
            previous_attempt = candidate
            break
        if previous_attempt is None:
            return None
        previous = self.repo.latest_evaluation(previous_attempt.id)
        if previous is None:
            return None
        previous_scores = {item.criterion_id: item.score for item in previous.feedback}
        deltas = {
            item.criterion_id: item.score - previous_scores[item.criterion_id]
            for item in current.feedback
            if item.criterion_id in previous_scores
        }
        return {
            "previous_attempt_id": previous_attempt.id,
            "previous_score": previous.overall_score,
            "deltas": deltas,
        }

    def _require_learner(self, learner_id: str) -> Learner:
        learner = self.repo.get_learner(learner_id)
        if learner is None:
            raise DomainError("Learner not found.", status_code=404)
        return learner

    def _require_attempt(self, attempt_id: str) -> Attempt:
        attempt = self.repo.get_attempt(attempt_id)
        if attempt is None:
            raise DomainError("Attempt not found.", status_code=404)
        return attempt

    def _check_key(self, key: str) -> None:
        if not _KEY.match(key or ""):
            raise DomainError("idempotency_key must be 8–80 letters, numbers, underscores, or hyphens.")


def _default_id() -> str:
    from uuid import uuid4

    return uuid4().hex
