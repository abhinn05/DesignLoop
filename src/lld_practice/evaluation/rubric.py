"""Deterministic rubric. Scores come from the submission text and class list.

Lexical checks are incomplete on purpose: another valid wording can miss a
signal. Those criteria carry limited confidence, and the suggestion names the
design question rather than a required class.
"""

import re

from lld_practice.domain.evaluation import CriterionFeedback
from lld_practice.domain.problem import Problem
from lld_practice.domain.rubric import RUBRIC_BY_ID
from lld_practice.domain.submission import DesignContent

_SOURCE = "deterministic"


class RubricEvaluator:
    name = "deterministic-rubric"
    supported_formats = frozenset({"text_design"})

    def evaluate(self, problem: Problem, content: DesignContent) -> list[CriterionFeedback]:
        blob = content.searchable_text()
        return [
            _requirements(problem, blob),
            _responsibilities(content),
            _coupling(content),
            _encapsulation(blob),
            _abstraction(problem, blob),
            _extensibility(content),
            _edge_cases(problem, blob),
            _explanation(content),
        ]


def build_summary(problem: Problem, feedback: list[CriterionFeedback], note: str) -> str:
    if not feedback:
        return note or "No rubric reading was produced."
    weakest = min(feedback, key=lambda item: (item.score, item.criterion_id))
    strongest = max(feedback, key=lambda item: (item.score, item.criterion_id))
    from lld_practice.domain.evaluation import overall_score

    score = overall_score(feedback)
    return (
        f"Rubric reading {score:.1f}/5 on {problem.title}. "
        f"Strongest signal: {strongest.title} ({strongest.score}/5). "
        f"Highest-leverage revision: {weakest.title}. {weakest.suggestion}"
    )


def _item(
    criterion_id: str,
    score: int,
    evidence: str,
    concern: str,
    suggestion: str,
    confidence: float,
) -> CriterionFeedback:
    criterion = RUBRIC_BY_ID[criterion_id]
    return CriterionFeedback(
        criterion_id=criterion_id,
        title=criterion.title,
        score=_clamp(score),
        evidence=evidence.strip(),
        concern=concern.strip(),
        suggestion=suggestion.strip(),
        confidence=confidence,
        source=_SOURCE,
    )


def _requirements(problem: Problem, blob: str) -> CriterionFeedback:
    hits, misses = _split(problem.concerns, blob)
    total = len(problem.concerns) or 1
    score = _band(len(hits) / total)
    quotes = [_quote(blob, concern.signals[0]) for concern in hits[:2]]
    quotes = [quote for quote in quotes if quote]
    if quotes:
        evidence = "Addressed " + ", ".join(concern.title for concern in hits) + ". " + " ".join(quotes)
    elif hits:
        evidence = "Addressed " + ", ".join(concern.title for concern in hits) + "."
    else:
        evidence = "None of the problem's design concerns show up in the write-up."
    if misses:
        concern = "Not visible yet: " + ", ".join(item.title for item in misses) + "."
        suggestion = misses[0].suggestion
    else:
        concern = ""
        suggestion = "Keep each covered concern owned by one type so a later rule change does not spread."
    return _item("requirements", score, evidence, concern, suggestion, 0.62)


def _responsibilities(content: DesignContent) -> CriterionFeedback:
    sketches = content.classes()
    if not sketches:
        return _item(
            "responsibilities",
            1,
            "This submission does not name any classes.",
            "Without types, responsibilities cannot be reviewed.",
            "Name the types that own the work, one job each.",
            0.9,
        )
    notes: list[str] = []
    sound = 0
    for sketch in sketches:
        reason = _responsibility_issue(sketch.name, sketch.responsibility)
        if reason:
            notes.append(reason)
        else:
            sound += 1
    score = _band(sound / len(sketches))
    if len(sketches) < 3:
        score = min(score, 2)
        notes.append(f"Only {len(sketches)} types are named, so the split of work is hard to review.")
    elif len(sketches) > 12:
        score = min(score, 3)
        notes.append("This many types can hide a missing boundary.")
    preview = "; ".join(f"{sketch.name}: {sketch.responsibility}" for sketch in sketches[:3])
    evidence = preview if preview else "No responsibilities were written down."
    if notes:
        concern = " ".join(notes[:3])
        suggestion = "Give each remaining job its own type, and rewrite catch-all responsibilities as a single sentence."
    else:
        concern = ""
        suggestion = "Check that no type both decides a policy and stores the record of what happened."
    return _item("responsibilities", score, evidence, concern, suggestion, 0.86)


def _coupling(content: DesignContent) -> CriterionFeedback:
    sketches = content.classes()
    count = len(sketches)
    if count == 0:
        return _item(
            "coupling",
            1,
            "No collaborators can be read because there are no classes.",
            "The dependency sketch is missing.",
            "Name, for each type, the few types it actually calls.",
            0.8,
        )
    degrees = [len(sketch.collaborators) for sketch in sketches]
    average = sum(degrees) / count
    hubs = [
        sketch.name
        for sketch, degree in zip(sketches, degrees)
        if count > 2 and degree >= count - 1
    ]
    if average == 0:
        score = 2
        concern = "No collaborators are named, so coupling cannot be reviewed."
        suggestion = "List the types each class actually uses. A type with no collaborators is fine only when it is a value."
    elif hubs:
        score = 2
        concern = "These types collaborate with almost everything: " + ", ".join(hubs) + "."
        suggestion = "Move the hub's extra jobs behind a smaller interface so most types do not see each other."
    elif average > 4:
        score = 3
        concern = "The average type names a lot of collaborators."
        suggestion = "Drop collaborators that are only data passed through, and keep the ones that are called."
    elif count >= 4 and 0.8 <= average <= 2.5:
        score = 5
        concern = ""
        suggestion = "Keep new features from adding a collaborator to every type."
    else:
        score = 4
        concern = ""
        suggestion = "Check the types with the longest collaborator lists first."
    named = ", ".join(
        f"{sketch.name} -> {', '.join(sketch.collaborators) or 'none'}" for sketch in sketches[:4]
    )
    evidence = f"Average named collaborators: {average:.1f}. {named}."
    return _item("coupling", score, evidence, concern, suggestion, 0.8)


def _encapsulation(blob: str) -> CriterionFeedback:
    terms = ("interface", "abstract", "invariant", "does not expose", "hides", "encapsulat", "protocol")
    found = [term for term in terms if term in blob.casefold()]
    if len(found) >= 3:
        score = 5
    elif len(found) == 2:
        score = 4
    elif len(found) == 1:
        score = 3
    else:
        score = 2
    if found:
        evidence = "The write-up names " + ", ".join(found) + ". " + _quote(blob, found[0])
        concern = "" if score >= 4 else "The boundary is mentioned once, without saying what stays hidden."
    else:
        evidence = "The write-up does not name an interface, a protocol, or an invariant."
        concern = "Callers may be depending on concrete rules rather than a small surface."
    suggestion = (
        "Name the invariant one type protects, and which collaborator is an interface "
        "so callers do not depend on the concrete rule."
    )
    return _item("encapsulation", score, evidence, concern, suggestion, 0.48)


def _abstraction(problem: Problem, blob: str) -> CriterionFeedback:
    hits, misses = _split(problem.variation_points, blob)
    total = len(problem.variation_points) or 1
    score = _band(len(hits) / total)
    if hits:
        evidence = "Variation mentioned: " + ", ".join(item.title for item in hits) + "."
        quote = _quote(blob, hits[0].signals[0])
        if quote:
            evidence = f"{evidence} {quote}"
    else:
        evidence = "The write-up does not isolate a part that is expected to change."
    if misses:
        concern = "Still mixed into the core: " + ", ".join(item.title for item in misses) + "."
        suggestion = misses[0].suggestion
    else:
        concern = ""
        suggestion = "When the next rule arrives, only the isolated type should need a new implementation."
    return _item("abstraction", score, evidence, concern, suggestion, 0.6)


def _extensibility(content: DesignContent) -> CriterionFeedback:
    text = content.sections().get("extensibility", "").strip()
    folded = text.casefold()
    phrases = (
        "without changing",
        "without modifying",
        "stays the same",
        "only the",
        "new class",
        "open for extension",
    )
    found = [phrase for phrase in phrases if phrase in folded]
    if len(text) < 40:
        score = 2
    elif found and len(text) >= 80:
        score = 5
    elif found:
        score = 4
    else:
        score = 3
    evidence = text if text else "The extensibility section is empty."
    if found:
        concern = ""
        suggestion = "Name the type that would be added, and the type that would not be edited."
    else:
        concern = "The section does not say what remains stable."
        suggestion = "Write one change you expect, which new type absorbs it, and which existing type stays the same."
    return _item("extensibility", score, evidence, concern, suggestion, 0.58)


def _edge_cases(problem: Problem, blob: str) -> CriterionFeedback:
    hits, misses = _split(problem.situations, blob)
    total = len(problem.situations) or 1
    score = _band(len(hits) / total)
    if hits:
        evidence = "Situations mentioned: " + ", ".join(item.title for item in hits) + "."
    else:
        evidence = "The listed awkward situations are not discussed."
    if misses:
        concern = "Not owned yet: " + ", ".join(item.title for item in misses) + "."
        suggestion = misses[0].suggestion
    else:
        concern = ""
        suggestion = "For each situation, name the type a test would call and the outcome it asserts."
    return _item("edge_cases", score, evidence, concern, suggestion, 0.62)


def _explanation(content: DesignContent) -> CriterionFeedback:
    sections = content.sections()
    assumptions = sections.get("assumptions", "").strip()
    tradeoffs = sections.get("tradeoffs", "").strip()
    folded_trade = tradeoffs.casefold()
    folded_assumptions = assumptions.casefold()
    points = 0
    if "because" in folded_trade or "because" in folded_assumptions:
        points += 1
    if any(word in folded_trade for word in ("instead", "rather", "cost", "simpler", "complexity")):
        points += 1
    if len(assumptions) >= 80:
        points += 1
    if len(tradeoffs) >= 80:
        points += 1
    score = (1, 2, 3, 4, 5)[points]
    evidence = f"Assumptions: {assumptions[:180] or 'missing'}"
    if points >= 3:
        concern = ""
        suggestion = "Keep the rejected alternative next to the choice so a later reader can see the cost."
    else:
        concern = "The reasoning is thin: a reviewer cannot see what was chosen against."
        suggestion = "Name one alternative you did not take, and the cost of the one you did, using because."
    return _item("explanation", score, evidence, concern, suggestion, 0.55)


def _responsibility_issue(name: str, responsibility: str) -> str | None:
    folded = responsibility.casefold()
    words = responsibility.split()
    ands = folded.count(" and ")
    if len(words) < 6:
        return f"{name} has a thin responsibility."
    if "everything" in folded or ands >= 3:
        return f"{name} is doing several jobs at once."
    if name.casefold() in {"system", "manager", "controller", "god"} and ands >= 2:
        return f"{name} looks like a catch-all controller."
    return None


def _split(items, blob: str) -> tuple[list, list]:
    hits = []
    misses = []
    for item in items:
        if any(_has(blob, signal) for signal in item.signals):
            hits.append(item)
        else:
            misses.append(item)
    return hits, misses


def _find(blob: str, signal: str):
    return re.search(rf"\b{re.escape(signal)}\b", blob, flags=re.IGNORECASE)


def _has(blob: str, signal: str) -> bool:
    return _find(blob, signal) is not None


def _quote(blob: str, signal: str) -> str:
    match = _find(blob, signal)
    if match is None:
        return ""
    start = max(0, match.start() - 40)
    end = min(len(blob), match.end() + 50)
    if start > 0:
        while start < match.start() and not blob[start - 1].isspace():
            start += 1
    if end < len(blob) and not blob[end - 1].isspace():
        while end > match.end() and not blob[end - 1].isspace():
            end -= 1
    snippet = " ".join(blob[start:end].split())
    return f'"{snippet}"'


def _band(ratio: float) -> int:
    if ratio >= 0.85:
        return 5
    if ratio >= 0.65:
        return 4
    if ratio >= 0.45:
        return 3
    if ratio >= 0.25:
        return 2
    return 1


def _clamp(score: int) -> int:
    return max(1, min(5, score))
