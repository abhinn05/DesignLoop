# Research note

## The learner problem

Low-level design practice stalls after the blank page. A learner can sketch a parking lot, an elevator, or a vending machine and still not know whether the split of responsibilities is any good. Unlike an algorithm problem, there is no single output to compare. Two capable designs can use different types and both be sound. The useful question is not "does this match the sample," but "which part of this design will hurt when a requirement changes, and what should the learner try next?"

What a learner can do today is read a problem, draw boxes, and stop. The missing piece is a short loop: attempt, evidence-backed feedback, and another attempt that can be compared with the last one. The platform should remember which rubric dimensions stay weak. A one-time score does not do that.

A meaningful attempt has to carry evidence. A paragraph that says "I would use OOP" cannot be reviewed. The learner needs to name the types, the job each one owns, how they collaborate, what was rejected, and what happens in the awkward cases. That is the submission. A diagram or compiling code can be added later. They are more evidence, not a different practice loop.

## What already exists

I looked at a handful of places people already practice this, not a survey.

**Coding platforms and discussion threads (LeetCode, InterviewBit).** Machine-coding and LLD problems exist, and comment threads sometimes include a review. The workflow is still "post a solution and hope." Feedback is uneven, unscoped, and not tied to the author's previous attempts. There is no rubric that survives from one problem to the next.

**Guided courses (Educative's Grokking the Low Level Design Interview, and similar write-ups).** These teach a problem by walking through one reference design. They are useful the first time. They train the learner to reproduce that design. They do not take the learner's own sketch and say which responsibility is overloaded. The learning loop ends when the article ends.

**Timed machine-coding rounds (the style used by InterviewReady, WorkAtTech, and many company rounds).** The submission is code in an IDE, often judged by whether it runs. That proves behavior and, indirectly, structure. It is a poor fit when the thing being practiced is the split of responsibilities and the trade-off, and when several shapes of code would pass. It also assumes the learner is ready to implement. Many are still at the "what are the types?" stage.

**A whiteboard or Excalidraw, reviewed by a person or a chatbot.** A diagram shows relationships quickly. A human mock (Pramp, interviewing.io, or a friend) can give excellent feedback and cannot be repeated on a Tuesday night. Pasting the same diagram into a general chat model usually produces an unconstrained opinion: a score, a list of patterns, and little evidence quoted from the sketch. The learner cannot tell a stable weakness from a one-off comment.

## Gaps

- Practice stops at "I made a design." There is no stored attempt, so the next session starts from zero.
- Reference solutions are treated as the answer, so a different valid split looks wrong.
- Feedback is either absent, social, or a single model score with no rubric.
- Tools jump to code or to a drawing tool before the learner has said what each type is for.
- Nothing shows a recurring weakness ("your extensibility section is thin on every problem").

## Product direction

DesignLoop is one practice loop. Four problems. One submission format: a structured text design. One evaluation flow: a fixed eight-part rubric whose scores are deterministic, with evidence and a suggestion on every line. Attempt history, including the lowest average dimension, and a revise action that starts from the previous submission.

AI is optional and narrow. It may rephrase comments. It does not own the score, and the product works with no API key. The design is a monolith on purpose. The part that would move first, if review became slow, is the evaluator, because the attempt is already saved before review starts and the status is already `submitted → evaluating → completed / failed`.
