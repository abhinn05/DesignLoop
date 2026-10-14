# DesignLoop

A small practice loop for low-level design. A learner picks a problem, writes a structured design, submits it, and gets rubric feedback they can revise against. The point is improvement across attempts, not a single "correct" class diagram.

## Run

From this directory, on Python 3.11+:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn lld_practice.api.app:app --app-dir src --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

Interactive API docs: http://127.0.0.1:8000/docs

Attempts are stored in `data/practice.sqlite` (created on startup). An evaluation left in `evaluating` from a crashed process is marked failed on the next startup. The submission stays.

## Tests

```powershell
python -m pytest
```

## Practice loop

1. Choose one of four problems (vending machine, parking lot, elevator control, movie booking).
2. Write assumptions, classes and their jobs, relationships, a trade-off, what would stay stable, and the awkward cases.
3. Submit. The submission is stored before review starts. The request returns while review is still queued.
4. Read feedback: each rubric line has a score out of 5, evidence from the write-up, a concern, a suggestion, and a confidence label.
5. Revise. A new attempt can start from the previous submission. History shows the weakest average dimension.

Status moves `draft → submitted → evaluating → completed`, or `evaluating → failed`. A failed review can be run again. The same idempotency key does not start a second review.

## Key decisions

- **Text design, not a diagram editor.** Responsibilities and trade-offs are the evidence we can review in two days. A class diagram would be a new `DesignContent`, not a new practice flow.
- **Scores come from a deterministic rubric.** An optional language model may rewrite comments. It is not allowed to change scores. Without `OPENAI_API_KEY`, the rubric stands on its own.
- **Lexical checks are incomplete on purpose.** They look for topics, not a reference solution, and the UI says when confidence is limited.
- **One process, SQLite, an in-process background task.** Enough to show that a slow or failed review must not drop the submission.

## Optional language review

```powershell
$env:OPENAI_API_KEY = "..."
$env:OPENAI_MODEL = "gpt-4o-mini"
# optional: $env:OPENAI_BASE_URL = "https://api.openai.com/v1"
python -m uvicorn lld_practice.api.app:app --app-dir src --host 127.0.0.1 --port 8000
```

If the call fails, the attempt still completes and the deterministic comments are kept.

## Layout

| Path | Role |
| --- | --- |
| `src/lld_practice/domain` | Attempt lifecycle, submission, rubric, problems |
| `src/lld_practice/evaluation` | Deterministic rubric and optional prose rewriter |
| `src/lld_practice/application` | Practice use cases |
| `src/lld_practice/infrastructure` | SQLite |
| `src/lld_practice/api` | HTTP adapter |
| `src/lld_practice/web` | Practice UI |
| `docs/RESEARCH.md` | Learner problem, existing tools, gaps |
| `docs/DESIGN.md` | Model, evaluation, trade-offs |
| `AI_USAGE.md` | Decisions made with AI assistance |

## Limitations

- A display name in the browser is not an account. Anyone with an attempt id can open it.
- Only the text-design format is implemented.
- Topic checks miss a good design that uses different words, and they can reward a write-up that mentions a topic without designing it. Class-responsibility and coupling scores look at the class list itself, which is harder to fake with a pasted requirement.
- Review runs in the web process. The first piece to move out is the evaluator, because it is the slow and fallible part and the practice flow already talks to it through `EvaluationPipeline`.

## Submit

The assignment form is:

https://docs.google.com/forms/d/e/1FAIpQLSfoHirkkjOeAYvzWksEVXSEQN5rEeD2Dyn5lPbSOkPhW65WHg/viewform?usp=publish-editor
