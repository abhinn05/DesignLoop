from dataclasses import dataclass
from enum import Enum

from lld_practice.domain.errors import DomainError


class Difficulty(str, Enum):
    INTRO = "intro"
    CORE = "core"
    STRETCH = "stretch"


@dataclass(frozen=True)
class DesignConcern:
    """A topic a serious design should address. Not a required class name."""

    id: str
    title: str
    suggestion: str
    signals: tuple[str, ...]


@dataclass(frozen=True)
class Situation:
    id: str
    title: str
    suggestion: str
    signals: tuple[str, ...]


@dataclass(frozen=True)
class VariationPoint:
    id: str
    title: str
    suggestion: str
    signals: tuple[str, ...]


@dataclass(frozen=True)
class Problem:
    id: str
    title: str
    difficulty: Difficulty
    summary: str
    statement: str
    requirements: tuple[str, ...]
    constraints: tuple[str, ...]
    situations: tuple[Situation, ...]
    concerns: tuple[DesignConcern, ...]
    variation_points: tuple[VariationPoint, ...]
    hints: tuple[str, ...]


class ProblemCatalog:
    def __init__(self, problems: list[Problem]) -> None:
        self._problems = list(problems)
        self._by_id = {problem.id: problem for problem in problems}

    def list(self) -> list[Problem]:
        return list(self._problems)

    def get(self, problem_id: str) -> Problem:
        problem = self._by_id.get(problem_id)
        if problem is None:
            raise DomainError("Problem not found.", status_code=404)
        return problem
