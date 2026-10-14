# AI usage

This prototype was built in Cursor with Grok. The notes below are the places where a default suggestion was a poor fit for the assignment, and what was kept instead.

## 1. A chat box and a 100-point score

The obvious AI shape is a text area and a prompt that says "score this design." That was rejected. A learner needs to show classes, jobs, relationships, a trade-off, and edge cases, or the review has nothing to point at. Feedback is eight rubric lines: score, evidence, concern, suggestion, confidence. A single number out of 100 is not shown.

## 2. Let the model own the score

A natural follow-up is to send the write-up to an LLM and store whatever JSON comes back. That was rejected as the source of truth. The model is optional, and when it is configured it may only rewrite evidence, concern, and suggestion. Scores stay on the deterministic rubric. If the call fails or the JSON is incomplete, the attempt still completes. Tests cover both the rewrite path and the failure path. No API key is required to demo the loop.

## 3. A React, Node, and microservice starter

The usual full-stack scaffold was rejected. The assignment is a domain-design exercise, and a simple monolith is explicitly enough. The practice rules live in Python classes (`Attempt`, `Submission`, `EvaluationPipeline`) with SQLite behind a repository. HTTP and the page are adapters. Kubernetes, a queue service, and a separate frontend build were not added.

## 4. Support text, code, and diagrams in the MVP

Supporting every submission format was the "complete" suggestion. It was rejected. Text design is the smallest format that still shows responsibilities and reasoning. `DesignContent` is the seam a class diagram would implement later. Evaluators declare `supported_formats`. Attempt history and the submit/retry flow do not mention the concrete format.

## 5. Hide uncertainty in the heuristic

Keyword coverage is a weak judge of design quality. The tempting fix was either to drop it or to present it as a precise grade. Neither was right for a two-day prototype. Topic checks stay, with confidence at 0.62 or lower, and the page tells the learner that a different wording can score low. The checker phrases are not sent to the browser, so the UI does not become a word list to paste. Responsibility and coupling scores are computed from the class list the learner actually wrote, which is firmer evidence.

AI was also used to draft problem statements, the rubric copy, and the test fixtures. The fixtures were then checked by running `pytest`, not by assuming the scores. The strong parking sketch scores at least 4/5 and the god-class sketch at most 2.5/5 in `tests/test_evaluation.py`.
