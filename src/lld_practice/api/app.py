import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from lld_practice.api.present import attempt_detail, attempt_summary, problem_detail, problem_summary
from lld_practice.application.service import PracticeService
from lld_practice.domain.errors import DomainError
from lld_practice.domain.submission import ClassSketch, TextDesignContent
from lld_practice.evaluation.llm import rewriter_from_env
from lld_practice.evaluation.pipeline import EvaluationPipeline
from lld_practice.infrastructure.repository import SqliteRepository
from lld_practice.problems.catalog import build_catalog

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class LearnerIn(BaseModel):
    display_name: str


class ClassIn(BaseModel):
    name: str = ""
    responsibility: str = ""
    collaborators: list[str] = Field(default_factory=list)


class DesignIn(BaseModel):
    assumptions: str = ""
    classes: list[ClassIn] = Field(default_factory=list)
    relationships: str = ""
    tradeoffs: str = ""
    extensibility: str = ""
    edge_cases: str = ""


class AttemptIn(BaseModel):
    learner_id: str
    problem_id: str
    from_attempt_id: str | None = None


class SubmitIn(BaseModel):
    content: DesignIn
    idempotency_key: str


def create_app(
    *,
    db_path: str | None = None,
    sync_evaluation: bool | None = None,
    pipeline: EvaluationPipeline | None = None,
) -> FastAPI:
    path = db_path or os.environ.get("LLD_DB_PATH", "data/practice.sqlite")
    if sync_evaluation is None:
        sync_evaluation = os.environ.get("LLD_SYNC_EVALUATION", "").strip() in {"1", "true", "yes"}
    repo = SqliteRepository(path)
    catalog = build_catalog()
    service = PracticeService(
        repo,
        catalog,
        pipeline or EvaluationPipeline(rewriter=rewriter_from_env()),
    )
    recovered = service.recover_interrupted()

    app = FastAPI(title="DesignLoop", version="0.1.0")
    app.state.service = service
    app.state.sync_evaluation = sync_evaluation
    app.state.recovered = recovered

    @app.exception_handler(DomainError)
    def handle_domain(_request, exc: DomainError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.message, "errors": exc.errors},
        )

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/problems")
    def list_problems():
        return [problem_summary(problem) for problem in catalog.list()]

    @app.get("/api/problems/{problem_id}")
    def get_problem(problem_id: str):
        return problem_detail(catalog.get(problem_id))

    @app.post("/api/learners", status_code=201)
    def create_learner(body: LearnerIn):
        learner = service.create_learner(body.display_name)
        return {"id": learner.id, "display_name": learner.display_name}

    @app.post("/api/attempts", status_code=201)
    def start_attempt(body: AttemptIn):
        attempt = service.start_attempt(body.learner_id, body.problem_id, body.from_attempt_id)
        return attempt_detail(service, attempt)

    @app.get("/api/attempts")
    def list_attempts(learner_id: str):
        service._require_learner(learner_id)
        return [attempt_summary(service, attempt) for attempt in repo.list_attempts(learner_id)]

    @app.get("/api/attempts/{attempt_id}")
    def get_attempt(attempt_id: str):
        return attempt_detail(service, service._require_attempt(attempt_id))

    @app.put("/api/attempts/{attempt_id}/draft")
    def save_draft(attempt_id: str, body: DesignIn):
        attempt = service.save_draft(attempt_id, _content(body))
        return attempt_detail(service, attempt)

    @app.post("/api/attempts/{attempt_id}/submit")
    def submit(attempt_id: str, body: SubmitIn, background: BackgroundTasks):
        attempt, created = service.submit(attempt_id, _content(body.content), body.idempotency_key)
        if created:
            _schedule(background, service, attempt.id, sync_evaluation)
            attempt = service._require_attempt(attempt.id)
        return attempt_detail(service, attempt)

    @app.post("/api/attempts/{attempt_id}/retry")
    def retry(attempt_id: str, background: BackgroundTasks):
        attempt = service._require_attempt(attempt_id)
        if attempt.status.value != "failed":
            raise DomainError("Only a failed evaluation can be run again.", status_code=409)
        if service.repo.get_submission(attempt_id) is None:
            raise DomainError("There is no saved submission to evaluate.", status_code=409)
        _schedule(background, service, attempt_id, sync_evaluation)
        return attempt_detail(service, service._require_attempt(attempt_id))

    @app.get("/api/learners/{learner_id}/insights")
    def insights(learner_id: str):
        return service.insights(learner_id)

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/styles.css")
    def styles():
        return FileResponse(WEB_DIR / "styles.css", media_type="text/css", headers={"Cache-Control": "no-cache"})

    @app.get("/app.js")
    def script():
        return FileResponse(WEB_DIR / "app.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    return app


def _schedule(background: BackgroundTasks, service: PracticeService, attempt_id: str, sync: bool) -> None:
    if sync:
        service.run_evaluation(attempt_id)
    else:
        background.add_task(service.run_evaluation, attempt_id)


def _content(body: DesignIn) -> TextDesignContent:
    return TextDesignContent(
        assumptions=body.assumptions.strip(),
        class_sketches=tuple(
            ClassSketch(
                name=item.name.strip(),
                responsibility=item.responsibility.strip(),
                collaborators=tuple(part.strip() for part in item.collaborators if part.strip()),
            )
            for item in body.classes
        ),
        relationships=body.relationships.strip(),
        tradeoffs=body.tradeoffs.strip(),
        extensibility=body.extensibility.strip(),
        edge_cases=body.edge_cases.strip(),
    )


app = create_app()
