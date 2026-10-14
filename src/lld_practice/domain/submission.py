from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from lld_practice.domain.errors import SubmissionValidationError


class SubmissionFormat(str, Enum):
    TEXT_DESIGN = "text_design"


@dataclass(frozen=True)
class ClassSketch:
    """One type the learner claims, and the job they say it owns."""

    name: str
    responsibility: str
    collaborators: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "responsibility": self.responsibility,
            "collaborators": list(self.collaborators),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ClassSketch":
        raw = data.get("collaborators") or []
        if isinstance(raw, str):
            raw = [part.strip() for part in raw.split(",")]
        collaborators = tuple(part.strip() for part in raw if str(part).strip())
        return cls(
            name=str(data.get("name") or "").strip(),
            responsibility=str(data.get("responsibility") or "").strip(),
            collaborators=collaborators,
        )


class DesignContent:
    """What an evaluator is allowed to ask a submission, regardless of format.

    A later class-diagram format implements the same surface. Attempt and
    evaluation do not branch on the concrete format.
    """

    format: SubmissionFormat

    def validate(self) -> None:
        raise NotImplementedError

    def sections(self) -> dict[str, str]:
        raise NotImplementedError

    def classes(self) -> tuple[ClassSketch, ...]:
        raise NotImplementedError

    def searchable_text(self) -> str:
        parts = list(self.sections().values())
        for sketch in self.classes():
            parts.append(sketch.name)
            parts.append(sketch.responsibility)
            parts.extend(sketch.collaborators)
        return "\n".join(parts)

    def to_dict(self) -> dict:
        raise NotImplementedError


@dataclass(frozen=True)
class TextDesignContent(DesignContent):
    """Structured prose. Enough evidence of responsibilities without a diagram tool."""

    assumptions: str = ""
    class_sketches: tuple[ClassSketch, ...] = ()
    relationships: str = ""
    tradeoffs: str = ""
    extensibility: str = ""
    edge_cases: str = ""
    format: SubmissionFormat = SubmissionFormat.TEXT_DESIGN

    def classes(self) -> tuple[ClassSketch, ...]:
        return self.class_sketches

    def sections(self) -> dict[str, str]:
        return {
            "assumptions": self.assumptions,
            "relationships": self.relationships,
            "tradeoffs": self.tradeoffs,
            "extensibility": self.extensibility,
            "edge_cases": self.edge_cases,
        }

    def validate(self) -> None:
        errors: list[str] = []
        _require_text(self.assumptions, "Assumptions", 20, errors)
        _require_text(self.relationships, "Relationships", 20, errors)
        _require_text(self.tradeoffs, "Trade-offs", 20, errors)
        _require_text(self.extensibility, "Extensibility", 20, errors)
        _require_text(self.edge_cases, "Edge cases", 20, errors)
        _limit(self.assumptions, "Assumptions", errors)
        _limit(self.relationships, "Relationships", errors)
        _limit(self.tradeoffs, "Trade-offs", errors)
        _limit(self.extensibility, "Extensibility", errors)
        _limit(self.edge_cases, "Edge cases", errors)

        if len(self.class_sketches) < 2:
            errors.append("Name at least two classes so responsibilities can be separated.")
        if len(self.class_sketches) > 15:
            errors.append("Keep the sketch to 15 classes or fewer.")

        seen: set[str] = set()
        for sketch in self.class_sketches:
            label = sketch.name or "A class"
            if len(sketch.name) < 2:
                errors.append("Every class needs a name.")
            elif not sketch.name[0].isalpha():
                errors.append(f"{label} should start with a letter.")
            if len(sketch.responsibility) < 12:
                errors.append(f"{label} needs a responsibility of at least a short phrase.")
            if len(sketch.responsibility) > 500:
                errors.append(f"{label} has a responsibility that is too long to review.")
            if len(sketch.collaborators) > 8:
                errors.append(f"{label} lists too many collaborators. Keep the ones it actually uses.")
            key = sketch.name.casefold()
            if key and key in seen:
                errors.append(f"Class names must be unique ({sketch.name} is repeated).")
            seen.add(key)

        if errors:
            raise SubmissionValidationError(errors)

    def to_dict(self) -> dict:
        return {
            "assumptions": self.assumptions,
            "classes": [sketch.to_dict() for sketch in self.class_sketches],
            "relationships": self.relationships,
            "tradeoffs": self.tradeoffs,
            "extensibility": self.extensibility,
            "edge_cases": self.edge_cases,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "TextDesignContent":
        data = data or {}
        sketches = tuple(
            ClassSketch.from_dict(item) for item in (data.get("classes") or []) if isinstance(item, dict)
        )
        return cls(
            assumptions=str(data.get("assumptions") or "").strip(),
            class_sketches=sketches,
            relationships=str(data.get("relationships") or "").strip(),
            tradeoffs=str(data.get("tradeoffs") or "").strip(),
            extensibility=str(data.get("extensibility") or "").strip(),
            edge_cases=str(data.get("edge_cases") or "").strip(),
        )


def content_from_storage(fmt: str, data: dict) -> DesignContent:
    if fmt == SubmissionFormat.TEXT_DESIGN.value:
        return TextDesignContent.from_dict(data)
    raise ValueError(f"Unsupported submission format: {fmt}")


@dataclass(frozen=True)
class Submission:
    """Immutable once stored. Evaluation reads this, never a live draft."""

    id: str
    attempt_id: str
    format: SubmissionFormat
    content: DesignContent
    idempotency_key: str
    submitted_at: datetime


def _require_text(value: str, label: str, minimum: int, errors: list[str]) -> None:
    if len(value.strip()) < minimum:
        errors.append(f"Write a real sentence for {label} before this can be reviewed.")


def _limit(value: str, label: str, errors: list[str]) -> None:
    if len(value) > 4000:
        errors.append(f"{label} are too long. Keep them under 4000 characters.")
