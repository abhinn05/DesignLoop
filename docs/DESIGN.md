# Design note

## MVP

DesignLoop helps one learner practice low-level design and see what to change next. It is not an LMS. There are four problems, one submission format, one review pipeline, and an attempt history.

```text
Choose problem → draft a text design → submit → feedback → revise
```

The learner's name is a display label stored in the browser. There is no account system.

## What the learner must provide

A reviewable attempt is a `TextDesignContent`:

| Section | What it proves |
| --- | --- |
| Assumptions | Scope. What was left out on purpose. |
| Classes | A name, one responsibility, and the collaborators that type uses. |
| Relationships | Who depends on whom, and what is hidden. |
| Trade-offs | An alternative and a cost. |
| Extensibility | What stays stable when a rule is added. |
| Edge cases | Which type owns the awkward situations from the problem. |

Empty or tiny sections are rejected with a 422. The draft is still saved, and no evaluation row is created. That is input validation, not a failed review.

## Flow and status

`Attempt` is the aggregate. Its status is the only legal lifecycle:

```text
draft → submitted → evaluating → completed
                          └────→ failed → evaluating → …
```

`PracticeService.submit` validates, then `SqliteRepository.commit_submission` writes the submission and the `submitted` status in one transaction. Only after that does the API schedule `run_evaluation`. The HTTP request does not wait for review unless `LLD_SYNC_EVALUATION` is set (tests use that).

`run_evaluation` moves the attempt to `evaluating` before the rubric runs, so a probe can see that the submission already exists. On success it stores an `EvaluationRecord` and marks `completed`. On an exception it stores a failed evaluation and marks `failed`. The submission row is untouched. Retry is allowed only from `failed`. The same idempotency key returns the existing submission and does not schedule another review. A different key after submit is a 409.

If the process dies mid-review, the next startup marks leftover `evaluating` attempts as `failed` with the reason that review was interrupted. The learner can retry. Nothing is re-queued automatically, which avoids a duplicate review after a restart.

## Important types

| Type | Owns |
| --- | --- |
| `Problem` | Statement, requirements, and the topics a review may look for. Not a reference design. |
| `ProblemCatalog` | The in-memory set of problems. Attempts store an id, not a copy of the statement. |
| `Learner` | Display name. |
| `Attempt` | Status transitions, draft, link to the submission. |
| `DesignContent` | What any submission format must answer: `validate`, `sections`, `classes`, `searchable_text`. |
| `TextDesignContent` | The MVP format. |
| `Submission` | Immutable snapshot plus an idempotency key. Review reads this, never the live draft. |
| `Criterion` / `RUBRIC` | The eight public dimensions and their weights. |
| `RubricEvaluator` | Deterministic scores, evidence, concern, suggestion, confidence. |
| `SuggestionRewriter` | Optional prose. `NullRewriter` or `LlmSuggestionRewriter`. |
| `EvaluationPipeline` | Runs one evaluator, then the rewriter. Scores are copied from the rubric. |
| `EvaluationRecord` | The stored result, including a failed run. |
| `PracticeService` | Use cases. The only type the HTTP layer needs for the loop. |
| `SqliteRepository` | Persistence and the conditional status updates. |

HTTP (`api/app.py`) and the page (`web/`) are adapters. They do not decide transitions.

## Evaluation

Eight dimensions, weights summing to 1, each scored 1–5:

1. Requirement understanding
2. Class responsibilities
3. Coupling and cohesion
4. Encapsulation and interfaces
5. Abstraction
6. Extensibility
7. Edge cases and testability
8. Quality of explanation

Deterministic, because they are facts about the submission:

- Required sections and unique class names (rejected before review).
- Status transitions, idempotency, and "store before review."
- Responsibility shape: thin text, or a type that says it does everything.
- Collaborator degree: missing, or one type that points at almost every other type.

Judgment-heavy, and still heuristic in this MVP:

- Whether the write-up addresses the problem's design concerns and situations. The concern list is a set of topics, not a required class diagram. Matching is lexical, so confidence stays at or below 0.62 and the suggestion names the design question.
- Encapsulation language (interface, invariant, "does not expose"). Confidence is 0.48 because a keyword is not a design.
- Explanation specificity: "because," an alternative, a cost.

The checker phrases are not included in the problem API. Sending them would turn the page into a word list. After submit, a miss produces a suggestion that teaches the topic.

An LLM, if `OPENAI_API_KEY` is set, receives the rubric and the submission and may replace evidence, concern, and suggestion. `parse_rewrite` drops anything that is not one entry per criterion. Score fields in the model JSON are ignored. A transport or schema failure is recorded on the evaluation note and the deterministic text is kept.

The summary points at the strongest signal and the highest-leverage revision. The history endpoint averages completed scores per dimension and names the weakest. A completed attempt can include per-criterion deltas against the previous completed attempt on the same problem.

## Change tests

**A. Text today, a class diagram later.** `Submission.format` and `DesignContent` are the seam. A diagram type would implement `classes()` by mapping nodes to responsibilities, or return an empty class list until a diagram evaluator exists. `content_from_storage` is the only factory that grows. `Attempt`, the status machine, and history do not change. The rubric already explains a missing class list instead of crashing.

**B. Another evaluator later.** `EvaluationPipeline` depends on an object with `evaluate` and `supported_formats`, plus a rewriter. Tests already substitute an evaluator that throws and one that wraps the rubric. A human-review or rule evaluator is another implementation passed into the pipeline. `PracticeService.run_evaluation` stays the same. The practice flow is not rewritten.

## Trade-offs

- Text instead of code: we cannot compile or unit-test the learner's design. We can review responsibilities without a sandbox. Code can be a later format with its own evaluator.
- Heuristic topic checks instead of an LLM-only judge: the demo and the tests run offline, and scores do not drift between runs. The cost is false negatives when the learner uses other words. That is stated in the UI.
- SQLite and an in-process task instead of a queue: duplicate review is prevented with a conditional `UPDATE` and an in-process in-flight set. That lock is per process. It is the right size until more than one web process runs reviews.
- Problems live in code, not in the database. Editing a problem is a deploy. Old attempts keep the problem id and still open if the problem is removed (`Retired problem`).

## If this grows

The slow, fallible piece is evaluation. It is already behind `EvaluationPipeline`, and the submission is already durable before it starts. That is the first component to run in a worker: the API would keep doing `submit` + enqueue, and the worker would keep calling `run_evaluation`. The practice flow, the rubric, and the status machine stay. A second web server would need the in-flight guard to move into the database (a claim column), which `mark_evaluating` is already shaped as: only one `UPDATE` from `submitted` or `failed` succeeds.
