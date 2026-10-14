from lld_practice.application.service import PracticeService
from lld_practice.domain.attempt import Attempt
from lld_practice.domain.evaluation import reading_label
from lld_practice.domain.problem import Problem
from lld_practice.domain.rubric import RUBRIC, confidence_label
from lld_practice.domain.submission import DesignContent


def problem_summary(problem: Problem) -> dict:
    return {
        "id": problem.id,
        "title": problem.title,
        "difficulty": problem.difficulty.value,
        "summary": problem.summary,
    }


def problem_detail(problem: Problem) -> dict:
    return {
        **problem_summary(problem),
        "statement": problem.statement,
        "requirements": list(problem.requirements),
        "constraints": list(problem.constraints),
        "situations": [item.title for item in problem.situations],
        "hints": list(problem.hints),
        "rubric": [
            {"id": item.id, "title": item.title, "question": item.question}
            for item in RUBRIC
        ],
    }


def content_dict(content: DesignContent | None) -> dict | None:
    if content is None:
        return None
    return content.to_dict()


def attempt_detail(service: PracticeService, attempt: Attempt) -> dict:
    try:
        title = service.catalog.get(attempt.problem_id).title
    except Exception:
        title = "Retired problem"
    submission = service.repo.get_submission(attempt.id)
    evaluation = service.repo.latest_evaluation(attempt.id)
    payload = {
        "id": attempt.id,
        "learner_id": attempt.learner_id,
        "problem_id": attempt.problem_id,
        "problem_title": title,
        "status": attempt.status.value,
        "failure_reason": attempt.failure_reason,
        "created_at": attempt.created_at.isoformat(),
        "updated_at": attempt.updated_at.isoformat(),
        "draft": content_dict(attempt.draft),
        "submission": None,
        "evaluation": None,
    }
    if submission is not None:
        payload["submission"] = {
            "id": submission.id,
            "format": submission.format.value,
            "content": submission.content.to_dict(),
            "idempotency_key": submission.idempotency_key,
            "submitted_at": submission.submitted_at.isoformat(),
        }
    if evaluation is not None:
        payload["evaluation"] = {
            "id": evaluation.id,
            "status": evaluation.status,
            "summary": evaluation.summary,
            "overall_score": evaluation.overall_score,
            "reading": reading_label(evaluation.overall_score or 0) if evaluation.overall_score is not None else None,
            "note": evaluation.note,
            "error": evaluation.error,
            "created_at": evaluation.created_at.isoformat(),
            "feedback": [
                {
                    **item.to_dict(),
                    "confidence_label": confidence_label(item.confidence),
                }
                for item in evaluation.feedback
            ],
            "comparison": service.comparison(attempt),
        }
    return payload


def attempt_summary(service: PracticeService, attempt: Attempt) -> dict:
    try:
        title = service.catalog.get(attempt.problem_id).title
    except Exception:
        title = "Retired problem"
    evaluation = service.repo.latest_evaluation(attempt.id)
    score = None
    if evaluation is not None and evaluation.status == "completed":
        score = evaluation.overall_score
    return {
        "id": attempt.id,
        "problem_id": attempt.problem_id,
        "problem_title": title,
        "status": attempt.status.value,
        "overall_score": score,
        "created_at": attempt.created_at.isoformat(),
        "updated_at": attempt.updated_at.isoformat(),
    }
