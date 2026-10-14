import json
from dataclasses import dataclass

from lld_practice.domain.evaluation import CriterionFeedback
from lld_practice.domain.problem import Problem
from lld_practice.domain.submission import DesignContent, Submission
from lld_practice.evaluation.rubric import RubricEvaluator, build_summary


@dataclass(frozen=True)
class EvaluationOutcome:
    feedback: tuple[CriterionFeedback, ...]
    summary: str
    note: str


class EvaluationPipeline:
    """Run the rubric, then optionally rewrite prose. Scores are never taken from a model."""

    def __init__(self, evaluator: RubricEvaluator | None = None, rewriter: "SuggestionRewriter | None" = None) -> None:
        self.evaluator = evaluator or RubricEvaluator()
        self.rewriter = rewriter or NullRewriter()

    def evaluate(self, problem: Problem, submission: Submission) -> EvaluationOutcome:
        content = submission.content
        if content.format.value not in self.evaluator.supported_formats:
            raise UnsupportedSubmission(content.format.value)
        feedback = self.evaluator.evaluate(problem, content)
        note = self.rewriter.note
        try:
            rewritten = self.rewriter.rewrite(problem, content, feedback)
        except Exception as exc:
            rewritten = None
            note = f"Language reviewer skipped ({exc.__class__.__name__}). Scores stay on the deterministic rubric."
        if rewritten:
            feedback = _merge(feedback, rewritten)
            note = (
                "Wording was revised by the language reviewer. "
                "Scores stayed on the deterministic rubric."
            )
        summary = build_summary(problem, feedback, note)
        return EvaluationOutcome(tuple(feedback), summary, note)


class UnsupportedSubmission(Exception):
    def __init__(self, fmt: str) -> None:
        super().__init__(f"No evaluator is registered for submission format '{fmt}'.")
        self.format = fmt


class SuggestionRewriter:
    note = ""

    def rewrite(
        self,
        problem: Problem,
        content: DesignContent,
        feedback: list[CriterionFeedback],
    ) -> list[dict] | None:
        raise NotImplementedError


class NullRewriter(SuggestionRewriter):
    note = "Scores and comments come from deterministic rubric checks."

    def rewrite(self, problem: Problem, content: DesignContent, feedback: list[CriterionFeedback]) -> None:
        return None


class LlmSuggestionRewriter(SuggestionRewriter):
    """Optional prose pass. A transport failure must not fail the attempt."""

    note = ""

    def __init__(self, transport) -> None:
        self._transport = transport

    def rewrite(self, problem: Problem, content: DesignContent, feedback: list[CriterionFeedback]) -> list[dict] | None:
        payload = self._transport(_prompt(problem, content, feedback))
        return parse_rewrite(payload, [item.criterion_id for item in feedback])


def parse_rewrite(payload: str, expected_ids: list[str]) -> list[dict] | None:
    data = _load_json(payload)
    if not isinstance(data, dict):
        return None
    rows = data.get("criteria")
    if not isinstance(rows, list):
        return None
    by_id = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        criterion_id = row.get("criterion_id")
        if criterion_id not in expected_ids or criterion_id in by_id:
            continue
        by_id[criterion_id] = {
            "criterion_id": criterion_id,
            "evidence": _clean(row.get("evidence")),
            "concern": _clean(row.get("concern")),
            "suggestion": _clean(row.get("suggestion")),
        }
    if len(by_id) != len(expected_ids):
        return None
    return [by_id[criterion_id] for criterion_id in expected_ids]


def _merge(feedback: list[CriterionFeedback], rewritten: list[dict]) -> list[CriterionFeedback]:
    by_id = {row["criterion_id"]: row for row in rewritten}
    merged: list[CriterionFeedback] = []
    for item in feedback:
        row = by_id.get(item.criterion_id)
        if row is None:
            merged.append(item)
            continue
        merged.append(
            CriterionFeedback(
                criterion_id=item.criterion_id,
                title=item.title,
                score=item.score,
                evidence=row["evidence"] or item.evidence,
                concern=row["concern"],
                suggestion=row["suggestion"] or item.suggestion,
                confidence=item.confidence,
                source="deterministic+llm",
            )
        )
    return merged


def _prompt(problem: Problem, content: DesignContent, feedback: list[CriterionFeedback]) -> str:
    rubric = [
        {
            "criterion_id": item.criterion_id,
            "title": item.title,
            "score": item.score,
            "evidence": item.evidence,
            "concern": item.concern,
            "suggestion": item.suggestion,
        }
        for item in feedback
    ]
    return json.dumps(
        {
            "instruction": (
                "You are reviewing a low-level design practice attempt. "
                "Several different designs can be valid. Do not demand a specific pattern name. "
                "Do not change scores. Rewrite evidence, concern, and suggestion so each one "
                "quotes or paraphrases the learner's own text. Return JSON only."
            ),
            "problem": {"title": problem.title, "statement": problem.statement},
            "submission": content.to_dict(),
            "rubric": rubric,
            "response_shape": {
                "criteria": [
                    {
                        "criterion_id": "id from rubric",
                        "evidence": "short quote or observation from the submission",
                        "concern": "empty string if nothing material",
                        "suggestion": "one concrete revision",
                    }
                ]
            },
        },
        ensure_ascii=True,
    )


def _load_json(payload: str) -> dict | None:
    text = (payload or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()[:600]
