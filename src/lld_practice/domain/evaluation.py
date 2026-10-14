from dataclasses import dataclass
from datetime import datetime

from lld_practice.domain.rubric import RUBRIC_BY_ID


@dataclass(frozen=True)
class CriterionFeedback:
    criterion_id: str
    title: str
    score: int
    evidence: str
    concern: str
    suggestion: str
    confidence: float
    source: str

    def to_dict(self) -> dict:
        return {
            "criterion_id": self.criterion_id,
            "title": self.title,
            "score": self.score,
            "evidence": self.evidence,
            "concern": self.concern,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CriterionFeedback":
        return cls(
            criterion_id=data["criterion_id"],
            title=data["title"],
            score=int(data["score"]),
            evidence=data.get("evidence") or "",
            concern=data.get("concern") or "",
            suggestion=data.get("suggestion") or "",
            confidence=float(data.get("confidence") or 0),
            source=data.get("source") or "deterministic",
        )


@dataclass(frozen=True)
class EvaluationRecord:
    id: str
    attempt_id: str
    status: str
    feedback: tuple[CriterionFeedback, ...]
    summary: str
    overall_score: float | None
    note: str
    error: str | None
    created_at: datetime


def overall_score(feedback: list[CriterionFeedback] | tuple[CriterionFeedback, ...]) -> float:
    weighted = 0.0
    total = 0.0
    for item in feedback:
        criterion = RUBRIC_BY_ID.get(item.criterion_id)
        if criterion is None:
            continue
        weighted += criterion.weight * item.score
        total += criterion.weight
    if total == 0:
        return 0.0
    return round(weighted / total, 2)


def reading_label(score: float) -> str:
    if score >= 4.5:
        return "Strong reading"
    if score >= 3.5:
        return "Solid base"
    if score >= 2.5:
        return "Partial"
    return "Early"
