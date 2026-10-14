import json

from fastapi.testclient import TestClient

from lld_practice.api.app import create_app
from lld_practice.evaluation.pipeline import EvaluationPipeline
from lld_practice.evaluation.rubric import RubricEvaluator
from tests.designs import strong_parking, weak_parking


def _client(tmp_path, pipeline=None):
    app = create_app(
        db_path=str(tmp_path / "practice.sqlite"),
        sync_evaluation=True,
        pipeline=pipeline,
    )
    return TestClient(app), app


def _start(client, problem_id="parking-lot"):
    learner = client.post("/api/learners", json={"display_name": "  Asha   "}).json()
    attempt = client.post(
        "/api/attempts",
        json={"learner_id": learner["id"], "problem_id": problem_id},
    ).json()
    return learner, attempt


def test_practice_loop_from_problem_to_history(tmp_path):
    client, _app = _client(tmp_path)
    problems = client.get("/api/problems").json()
    assert len(problems) == 4
    detail = client.get("/api/problems/parking-lot").json()
    assert "allocation policy" not in json.dumps(detail).lower()
    assert "signals" not in detail
    assert len(detail["rubric"]) == 8

    learner, attempt = _start(client)
    assert attempt["status"] == "draft"
    rejected = client.post(
        f"/api/attempts/{attempt['id']}/submit",
        json={"content": {"assumptions": "no"}, "idempotency_key": "idem-key-1"},
    )
    assert rejected.status_code == 422
    assert rejected.json()["errors"]
    still = client.get(f"/api/attempts/{attempt['id']}").json()
    assert still["status"] == "draft"
    assert still["submission"] is None

    submitted = client.post(
        f"/api/attempts/{attempt['id']}/submit",
        json={"content": strong_parking(), "idempotency_key": "idem-key-1"},
    )
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["status"] == "completed"
    assert body["evaluation"]["overall_score"] >= 4
    assert body["evaluation"]["feedback"][0]["evidence"]
    replay = client.post(
        f"/api/attempts/{attempt['id']}/submit",
        json={"content": strong_parking(), "idempotency_key": "idem-key-1"},
    )
    assert replay.json()["submission"]["id"] == body["submission"]["id"]

    history = client.get("/api/attempts", params={"learner_id": learner["id"]}).json()
    assert history[0]["overall_score"] >= 4
    insights = client.get(f"/api/learners/{learner['id']}/insights").json()
    assert insights["completed_count"] == 1

    revised = client.post(
        "/api/attempts",
        json={
            "learner_id": learner["id"],
            "problem_id": "parking-lot",
            "from_attempt_id": attempt["id"],
        },
    ).json()
    assert revised["draft"]["classes"][0]["name"] == "ParkingLot"


def test_failed_run_can_be_retried_from_the_api(tmp_path):
    class Once:
        def __init__(self):
            self.calls = 0
            self.supported_formats = frozenset({"text_design"})

        def evaluate(self, problem, content):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("model timeout")
            return RubricEvaluator().evaluate(problem, content)

    client, app = _client(tmp_path, pipeline=EvaluationPipeline(evaluator=Once()))
    _learner, attempt = _start(client)
    failed = client.post(
        f"/api/attempts/{attempt['id']}/submit",
        json={"content": weak_parking(), "idempotency_key": "idem-key-9"},
    ).json()
    assert failed["status"] == "failed"
    assert failed["submission"]["content"]["assumptions"]
    blocked = client.post(f"/api/attempts/{attempt['id']}/retry")
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "completed"
    missing = client.post(f"/api/attempts/{attempt['id']}/retry")
    assert missing.status_code == 409
    assert app.state.service.repo.get_submission(attempt["id"]).id == failed["submission"]["id"]


def test_unknown_problem_and_blank_name_are_rejected(tmp_path):
    client, _app = _client(tmp_path)
    assert client.post("/api/learners", json={"display_name": "   "}).status_code == 400
    learner = client.post("/api/learners", json={"display_name": "Asha"}).json()
    missing = client.post(
        "/api/attempts",
        json={"learner_id": learner["id"], "problem_id": "does-not-exist"},
    )
    assert missing.status_code == 404
    assert client.get("/api/health").json()["status"] == "ok"
