from datetime import datetime, timedelta, timezone

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from lld_practice.api.app import create_app
from lld_practice.application.service import PracticeService
from lld_practice.domain.attempt import AttemptStatus
from lld_practice.domain.errors import DomainError
from lld_practice.evaluation.pipeline import EvaluationPipeline
from lld_practice.infrastructure.repository import SqliteRepository
from lld_practice.problems.catalog import build_catalog
from tests.designs import strong_parking, weak_parking


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 3, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.now
        self.now = current + timedelta(seconds=1)
        return current


class BoomEvaluator:
    name = "boom"
    supported_formats = frozenset({"text_design"})
    calls = 0

    def evaluate(self, problem, content):
        BoomEvaluator.calls += 1
        raise RuntimeError("model timeout")


class ProbePipeline:
    def __init__(self, repo, inner):
        self.repo = repo
        self.inner = inner
        self.status_during_eval = None
        self.submission_was_stored = False

    def evaluate(self, problem, submission):
        attempt = self.repo.get_attempt(submission.attempt_id)
        self.status_during_eval = attempt.status
        self.submission_was_stored = self.repo.get_submission(submission.attempt_id) is not None
        return self.inner.evaluate(problem, submission)


@pytest.fixture
def service(tmp_path):
    repo = SqliteRepository(str(tmp_path / "practice.sqlite"))
    pipeline = EvaluationPipeline()
    probe = ProbePipeline(repo, pipeline)
    return PracticeService(repo, build_catalog(), probe, clock=Clock())


def _learner_and_attempt(service: PracticeService):
    learner = service.create_learner("Asha")
    attempt = service.start_attempt(learner.id, "parking-lot")
    return learner, attempt


def test_submit_stores_the_attempt_before_evaluation_starts(service):
    _, attempt = _learner_and_attempt(service)
    from lld_practice.domain.submission import TextDesignContent

    saved, created = service.submit(attempt.id, TextDesignContent.from_dict(strong_parking()), "idem-key-1")
    assert created is True
    assert saved.status is AttemptStatus.SUBMITTED
    assert service.repo.get_submission(attempt.id) is not None
    assert service.repo.latest_evaluation(attempt.id) is None

    service.run_evaluation(attempt.id)
    probe = service.pipeline
    assert probe.submission_was_stored is True
    assert probe.status_during_eval is AttemptStatus.EVALUATING
    finished = service.repo.get_attempt(attempt.id)
    assert finished.status is AttemptStatus.COMPLETED
    assert service.repo.latest_evaluation(attempt.id).overall_score >= 4


def test_same_idempotency_key_does_not_evaluate_twice(service):
    _, attempt = _learner_and_attempt(service)
    from lld_practice.domain.submission import TextDesignContent

    content = TextDesignContent.from_dict(strong_parking())
    service.submit(attempt.id, content, "idem-key-1")
    service.run_evaluation(attempt.id)
    again, created = service.submit(attempt.id, content, "idem-key-1")
    assert created is False
    assert again.status is AttemptStatus.COMPLETED
    assert len(service.repo.list_evaluations(attempt.id)) == 1
    with pytest.raises(DomainError) as caught:
        service.submit(attempt.id, content, "idem-key-2")
    assert caught.value.status_code == 409


def test_failed_evaluation_keeps_the_submission_and_retry_can_succeed(tmp_path):
    repo = SqliteRepository(str(tmp_path / "practice.sqlite"))
    clock = Clock()
    failing = PracticeService(
        repo,
        build_catalog(),
        EvaluationPipeline(evaluator=BoomEvaluator()),
        clock=clock,
    )
    learner = failing.create_learner("Asha")
    attempt = failing.start_attempt(learner.id, "parking-lot")
    from lld_practice.domain.submission import TextDesignContent

    failing.submit(attempt.id, TextDesignContent.from_dict(strong_parking()), "idem-key-1")
    failing.run_evaluation(attempt.id)
    failed = repo.get_attempt(attempt.id)
    assert failed.status is AttemptStatus.FAILED
    assert "model timeout" in failed.failure_reason
    assert repo.get_submission(attempt.id) is not None

    failing.pipeline = EvaluationPipeline()
    failing.run_evaluation(attempt.id)
    restored = repo.get_attempt(attempt.id)
    assert restored.status is AttemptStatus.COMPLETED
    assert restored.submission_id == failed.submission_id
    assert len(repo.list_evaluations(attempt.id)) == 2


def test_interrupted_evaluation_is_failed_without_losing_the_submission(service):
    _, attempt = _learner_and_attempt(service)
    from lld_practice.domain.submission import TextDesignContent

    service.submit(attempt.id, TextDesignContent.from_dict(weak_parking()), "idem-key-1")
    assert service.repo.mark_evaluating(attempt.id, service.clock()) is True
    assert service.recover_interrupted() == 1
    recovered = service.repo.get_attempt(attempt.id)
    assert recovered.status is AttemptStatus.FAILED
    assert "interrupted" in recovered.failure_reason
    assert service.repo.get_submission(attempt.id) is not None
    service.run_evaluation(attempt.id)
    assert service.repo.get_attempt(attempt.id).status is AttemptStatus.COMPLETED


def test_revision_copies_the_previous_submission(service):
    learner, attempt = _learner_and_attempt(service)
    from lld_practice.domain.submission import TextDesignContent

    service.submit(attempt.id, TextDesignContent.from_dict(strong_parking()), "idem-key-1")
    service.run_evaluation(attempt.id)
    revised = service.start_attempt(learner.id, "parking-lot", from_attempt_id=attempt.id)
    assert revised.status is AttemptStatus.DRAFT
    assert revised.draft is not None
    assert revised.draft.classes()[0].name == "ParkingLot"
    insights = service.insights(learner.id)
    assert insights["completed_count"] == 1
    assert insights["weakest"] is not None


def test_async_submit_returns_before_evaluation(tmp_path, monkeypatch):
    app = create_app(db_path=str(tmp_path / "practice.sqlite"), sync_evaluation=False)
    scheduled = []

    def spy(self, func, *args, **kwargs):
        scheduled.append((func.__name__, args))

    monkeypatch.setattr(BackgroundTasks, "add_task", spy)
    client = TestClient(app)
    learner = client.post("/api/learners", json={"display_name": "Asha"}).json()
    attempt = client.post(
        "/api/attempts",
        json={"learner_id": learner["id"], "problem_id": "parking-lot"},
    ).json()
    saved = client.post(
        f"/api/attempts/{attempt['id']}/submit",
        json={"content": strong_parking(), "idempotency_key": "idem-key-1"},
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["status"] == "submitted"
    assert body["submission"]["id"]
    assert body["evaluation"] is None
    assert scheduled[0][0] == "run_evaluation"

    app.state.service.run_evaluation(attempt["id"])
    completed = client.get(f"/api/attempts/{attempt['id']}").json()
    assert completed["status"] == "completed"
    assert len(completed["evaluation"]["feedback"]) == 8


def test_startup_recovers_an_evaluation_that_was_left_running(tmp_path):
    path = str(tmp_path / "practice.sqlite")
    first = create_app(db_path=path, sync_evaluation=True)
    client = TestClient(first)
    learner = client.post("/api/learners", json={"display_name": "Asha"}).json()
    attempt = client.post(
        "/api/attempts",
        json={"learner_id": learner["id"], "problem_id": "vending-machine"},
    ).json()
    client.put(f"/api/attempts/{attempt['id']}/draft", json=weak_parking())
    from lld_practice.domain.submission import TextDesignContent

    first.state.service.submit(attempt["id"], TextDesignContent.from_dict(weak_parking()), "idem-key-1")
    assert first.state.service.repo.mark_evaluating(attempt["id"], first.state.service.clock())
    second = create_app(db_path=path, sync_evaluation=True)
    assert second.state.recovered == 1
    restored = TestClient(second).get(f"/api/attempts/{attempt['id']}").json()
    assert restored["status"] == "failed"
    assert restored["submission"] is not None
