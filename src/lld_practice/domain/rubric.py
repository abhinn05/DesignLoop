from dataclasses import dataclass


@dataclass(frozen=True)
class Criterion:
    """A public dimension of feedback. Several designs can score well on it."""

    id: str
    title: str
    question: str
    weight: float


RUBRIC: tuple[Criterion, ...] = (
    Criterion(
        "requirements",
        "Requirement understanding",
        "Did the design address the hard parts of the problem, not only the happy path?",
        0.18,
    ),
    Criterion(
        "responsibilities",
        "Class responsibilities",
        "Does each type own one clear job?",
        0.16,
    ),
    Criterion(
        "coupling",
        "Coupling and cohesion",
        "Are dependencies few and intentional?",
        0.12,
    ),
    Criterion(
        "encapsulation",
        "Encapsulation and interfaces",
        "Are invariants hidden behind a small surface?",
        0.12,
    ),
    Criterion(
        "abstraction",
        "Abstraction",
        "Are the parts that will change isolated from the parts that stay stable?",
        0.12,
    ),
    Criterion(
        "extensibility",
        "Extensibility",
        "What stays stable when a rule or a type is added?",
        0.10,
    ),
    Criterion(
        "edge_cases",
        "Edge cases and testability",
        "Are the awkward cases owned by a specific type?",
        0.12,
    ),
    Criterion(
        "explanation",
        "Quality of explanation",
        "Are assumptions and trade-offs specific enough to review?",
        0.08,
    ),
)

RUBRIC_BY_ID: dict[str, Criterion] = {item.id: item for item in RUBRIC}


def confidence_label(value: float) -> str:
    if value >= 0.75:
        return "high"
    if value >= 0.6:
        return "medium"
    return "limited"
