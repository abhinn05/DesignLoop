from lld_practice.domain.evaluation import overall_score
from lld_practice.domain.submission import SubmissionFormat, TextDesignContent
from lld_practice.evaluation.pipeline import EvaluationPipeline, parse_rewrite
from lld_practice.evaluation.rubric import RubricEvaluator
from lld_practice.problems.catalog import build_catalog
from tests.designs import strong_parking, weak_parking


def _feedback(design: dict, problem_id: str = "parking-lot"):
    problem = build_catalog().get(problem_id)
    content = TextDesignContent.from_dict(design)
    return RubricEvaluator().evaluate(problem, content)


def test_strong_design_reads_higher_than_a_god_class():
    strong = _feedback(strong_parking())
    weak = _feedback(weak_parking())
    assert overall_score(strong) >= 4.0
    assert overall_score(weak) <= 2.5
    assert overall_score(strong) - overall_score(weak) >= 1.5
    by_id = {item.criterion_id: item for item in strong}
    assert by_id["requirements"].score >= 4
    assert by_id["responsibilities"].score >= 4
    assert by_id["edge_cases"].score >= 4
    assert by_id["requirements"].evidence
    assert by_id["requirements"].confidence < 0.75


def test_parking_language_does_not_satisfy_the_vending_problem():
    on_parking = overall_score(_feedback(strong_parking(), "parking-lot"))
    on_vending = overall_score(_feedback(strong_parking(), "vending-machine"))
    assert on_parking > on_vending


def test_scores_stay_put_when_the_language_reviewer_rewrites_prose():
    problem = build_catalog().get("parking-lot")
    content = TextDesignContent.from_dict(strong_parking())
    base = RubricEvaluator().evaluate(problem, content)

    class Rewriter:
        note = ""

        def rewrite(self, problem, content, feedback):
            return [
                {
                    "criterion_id": item.criterion_id,
                    "evidence": "rewritten from the learner text",
                    "concern": "",
                    "suggestion": "Tighten this boundary.",
                }
                for item in feedback
            ]

    outcome = EvaluationPipeline(rewriter=Rewriter()).evaluate(problem, _submission(content))
    assert [item.score for item in outcome.feedback] == [item.score for item in base]
    assert outcome.feedback[0].source == "deterministic+llm"
    assert "Scores stayed" in outcome.note


def test_language_reviewer_failure_keeps_the_deterministic_reading():
    problem = build_catalog().get("parking-lot")
    content = TextDesignContent.from_dict(strong_parking())

    class Rewriter:
        note = ""

        def rewrite(self, problem, content, feedback):
            raise RuntimeError("timeout")

    outcome = EvaluationPipeline(rewriter=Rewriter()).evaluate(problem, _submission(content))
    assert outcome.feedback[0].source == "deterministic"
    assert "skipped" in outcome.note
    assert overall_score(outcome.feedback) > 0


def test_parse_rewrite_accepts_fenced_json_and_rejects_a_partial_rubric():
    ids = ["requirements", "responsibilities"]
    payload = """```json
    {"criteria": [
        {"criterion_id": "requirements", "evidence": "e", "concern": "", "suggestion": "s", "score": 100},
        {"criterion_id": "responsibilities", "evidence": "e2", "concern": "c", "suggestion": "s2"}
    ]}
    ```"""
    parsed = parse_rewrite(payload, ids)
    assert parsed is not None
    assert "score" not in parsed[0]
    assert parse_rewrite('{"criteria": []}', ids) is None


class _Submission:
    def __init__(self, content):
        self.content = content
        self.attempt_id = "a"
        self.format = content.format


def _submission(content):
    assert content.format is SubmissionFormat.TEXT_DESIGN
    return _Submission(content)
