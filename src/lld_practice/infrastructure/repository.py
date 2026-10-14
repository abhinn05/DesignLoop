import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from lld_practice.domain.attempt import Attempt, AttemptStatus, Learner
from lld_practice.domain.errors import DomainError
from lld_practice.domain.evaluation import CriterionFeedback, EvaluationRecord
from lld_practice.domain.submission import (
    Submission,
    SubmissionFormat,
    content_from_storage,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS learners (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    status TEXT NOT NULL,
    draft_json TEXT,
    submission_id TEXT,
    failure_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (learner_id) REFERENCES learners(id)
);

CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL UNIQUE,
    format TEXT NOT NULL,
    content_json TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    UNIQUE (attempt_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS evaluations (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    status TEXT NOT NULL,
    feedback_json TEXT NOT NULL,
    summary TEXT NOT NULL,
    overall_score REAL,
    note TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_learner ON attempts(learner_id, created_at);
CREATE INDEX IF NOT EXISTS idx_eval_attempt ON evaluations(attempt_id, created_at);
"""


class SqliteRepository:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        conn = self._connect()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _session(self):
        with self._lock:
            conn = self._connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def create_learner(self, learner: Learner) -> None:
        with self._session() as conn:
            conn.execute(
                "INSERT INTO learners (id, display_name, created_at) VALUES (?, ?, ?)",
                (learner.id, learner.display_name, _iso(learner.created_at)),
            )

    def get_learner(self, learner_id: str) -> Learner | None:
        with self._session() as conn:
            row = conn.execute("SELECT * FROM learners WHERE id = ?", (learner_id,)).fetchone()
            return _learner(row) if row else None

    def insert_attempt(self, attempt: Attempt) -> None:
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO attempts (
                    id, learner_id, problem_id, status, draft_json, submission_id,
                    failure_reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _attempt_values(attempt),
            )

    def get_attempt(self, attempt_id: str) -> Attempt | None:
        with self._session() as conn:
            row = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
            return _attempt(row) if row else None

    def list_attempts(self, learner_id: str) -> list[Attempt]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT * FROM attempts WHERE learner_id = ? ORDER BY created_at DESC, id DESC",
                (learner_id,),
            ).fetchall()
            return [_attempt(row) for row in rows]

    def list_by_status(self, status: AttemptStatus) -> list[Attempt]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT * FROM attempts WHERE status = ?",
                (status.value,),
            ).fetchall()
            return [_attempt(row) for row in rows]

    def update_draft(self, attempt: Attempt) -> None:
        with self._session() as conn:
            cursor = conn.execute(
                """
                UPDATE attempts
                SET draft_json = ?, updated_at = ?
                WHERE id = ? AND status = 'draft'
                """,
                (_draft_json(attempt), _iso(attempt.updated_at), attempt.id),
            )
            if cursor.rowcount == 0:
                raise DomainError("Drafts can only be saved before submission.", status_code=409)

    def commit_submission(self, attempt: Attempt, submission: Submission) -> str:
        """Persist the submission before any evaluation. Returns 'created' or 'replay'."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT status FROM attempts WHERE id = ?",
                    (attempt.id,),
                ).fetchone()
                if row is None:
                    conn.rollback()
                    raise DomainError("Attempt not found.", status_code=404)
                existing = conn.execute(
                    "SELECT id, idempotency_key FROM submissions WHERE attempt_id = ?",
                    (attempt.id,),
                ).fetchone()
                if existing is not None:
                    conn.rollback()
                    if existing["idempotency_key"] == submission.idempotency_key:
                        return "replay"
                    raise DomainError(
                        "This attempt was already submitted. Start another attempt to revise.",
                        status_code=409,
                    )
                if row["status"] != AttemptStatus.DRAFT.value:
                    conn.rollback()
                    raise DomainError(
                        "This attempt can no longer be submitted.",
                        status_code=409,
                    )
                conn.execute(
                    """
                    INSERT INTO submissions (
                        id, attempt_id, format, content_json, idempotency_key, submitted_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        submission.id,
                        submission.attempt_id,
                        submission.format.value,
                        json.dumps(submission.content.to_dict()),
                        submission.idempotency_key,
                        _iso(submission.submitted_at),
                    ),
                )
                cursor = conn.execute(
                    """
                    UPDATE attempts
                    SET status = ?, draft_json = ?, submission_id = ?, failure_reason = NULL, updated_at = ?
                    WHERE id = ? AND status = 'draft'
                    """,
                    (
                        AttemptStatus.SUBMITTED.value,
                        json.dumps(submission.content.to_dict()),
                        submission.id,
                        _iso(attempt.updated_at),
                        attempt.id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise DomainError("This attempt can no longer be submitted.", status_code=409)
                conn.commit()
                return "created"
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def get_submission(self, attempt_id: str) -> Submission | None:
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM submissions WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            return _submission(row) if row else None

    def mark_evaluating(self, attempt_id: str, now: datetime) -> bool:
        with self._session() as conn:
            cursor = conn.execute(
                """
                UPDATE attempts
                SET status = 'evaluating', failure_reason = NULL, updated_at = ?
                WHERE id = ? AND status IN ('submitted', 'failed')
                """,
                (_iso(now), attempt_id),
            )
            return cursor.rowcount == 1

    def mark_completed(self, attempt_id: str, now: datetime) -> None:
        with self._session() as conn:
            cursor = conn.execute(
                """
                UPDATE attempts
                SET status = 'completed', failure_reason = NULL, updated_at = ?
                WHERE id = ? AND status = 'evaluating'
                """,
                (_iso(now), attempt_id),
            )
            if cursor.rowcount != 1:
                raise DomainError("Only an in-progress evaluation can be completed.", status_code=409)

    def mark_failed(self, attempt_id: str, reason: str, now: datetime) -> None:
        with self._session() as conn:
            cursor = conn.execute(
                """
                UPDATE attempts
                SET status = 'failed', failure_reason = ?, updated_at = ?
                WHERE id = ? AND status = 'evaluating'
                """,
                (reason, _iso(now), attempt_id),
            )
            if cursor.rowcount != 1:
                raise DomainError("Only an in-progress evaluation can fail.", status_code=409)

    def recover_interrupted(self, reason: str, now: datetime) -> int:
        with self._session() as conn:
            cursor = conn.execute(
                """
                UPDATE attempts
                SET status = 'failed', failure_reason = ?, updated_at = ?
                WHERE status = 'evaluating'
                """,
                (reason, _iso(now)),
            )
            return cursor.rowcount

    def add_evaluation(self, record: EvaluationRecord) -> None:
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO evaluations (
                    id, attempt_id, status, feedback_json, summary, overall_score, note, error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.attempt_id,
                    record.status,
                    json.dumps([item.to_dict() for item in record.feedback]),
                    record.summary,
                    record.overall_score,
                    record.note,
                    record.error,
                    _iso(record.created_at),
                ),
            )

    def latest_evaluation(self, attempt_id: str) -> EvaluationRecord | None:
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT * FROM evaluations
                WHERE attempt_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (attempt_id,),
            ).fetchone()
            return _evaluation(row) if row else None

    def list_evaluations(self, attempt_id: str) -> list[EvaluationRecord]:
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM evaluations
                WHERE attempt_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (attempt_id,),
            ).fetchall()
            return [_evaluation(row) for row in rows]


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _draft_json(attempt: Attempt) -> str | None:
    if attempt.draft is None:
        return None
    return json.dumps(attempt.draft.to_dict())


def _attempt_values(attempt: Attempt) -> tuple:
    return (
        attempt.id,
        attempt.learner_id,
        attempt.problem_id,
        attempt.status.value,
        _draft_json(attempt),
        attempt.submission_id,
        attempt.failure_reason,
        _iso(attempt.created_at),
        _iso(attempt.updated_at),
    )


def _learner(row: sqlite3.Row) -> Learner:
    return Learner(row["id"], row["display_name"], _parse(row["created_at"]))


def _attempt(row: sqlite3.Row) -> Attempt:
    draft = None
    if row["draft_json"]:
        draft = content_from_storage(SubmissionFormat.TEXT_DESIGN.value, json.loads(row["draft_json"]))
    return Attempt(
        id=row["id"],
        learner_id=row["learner_id"],
        problem_id=row["problem_id"],
        status=AttemptStatus(row["status"]),
        created_at=_parse(row["created_at"]),
        updated_at=_parse(row["updated_at"]),
        draft=draft,
        submission_id=row["submission_id"],
        failure_reason=row["failure_reason"],
    )


def _submission(row: sqlite3.Row) -> Submission:
    fmt = SubmissionFormat(row["format"])
    return Submission(
        id=row["id"],
        attempt_id=row["attempt_id"],
        format=fmt,
        content=content_from_storage(fmt.value, json.loads(row["content_json"])),
        idempotency_key=row["idempotency_key"],
        submitted_at=_parse(row["submitted_at"]),
    )


def _evaluation(row: sqlite3.Row) -> EvaluationRecord:
    feedback = tuple(CriterionFeedback.from_dict(item) for item in json.loads(row["feedback_json"]))
    score = row["overall_score"]
    return EvaluationRecord(
        id=row["id"],
        attempt_id=row["attempt_id"],
        status=row["status"],
        feedback=feedback,
        summary=row["summary"],
        overall_score=None if score is None else float(score),
        note=row["note"],
        error=row["error"],
        created_at=_parse(row["created_at"]),
    )
