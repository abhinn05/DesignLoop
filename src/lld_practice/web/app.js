const state = {
  learner: loadLearner(),
  view: "problems",
  problems: [],
  insights: null,
  history: [],
  attempt: null,
  poll: null,
  banner: "",
};

const main = () => document.getElementById("main");

document.getElementById("nav-home").addEventListener("click", () => showProblems());
document.getElementById("nav-problems").addEventListener("click", () => showProblems());
document.getElementById("nav-history").addEventListener("click", () => showHistory());

boot();

async function boot() {
  if (state.learner) {
    try {
      await api(`/api/learners/${state.learner.id}/insights`);
    } catch (_error) {
      state.learner = null;
      localStorage.removeItem("designloop.learner");
    }
  }
  if (!state.learner) {
    renderGate();
    return;
  }
  enter();
  await showProblems();
}

function enter() {
  document.getElementById("gate").hidden = true;
  document.getElementById("shell").hidden = false;
  document.getElementById("learner-name").textContent = state.learner.display_name;
}

function renderGate() {
  document.getElementById("shell").hidden = true;
  const gate = document.getElementById("gate");
  gate.hidden = false;
  gate.innerHTML = `
    <form class="panel" id="gate-form">
      <p class="kicker">LLD practice</p>
      <h1>Design, submit, read the rubric, try again.</h1>
      <p class="lede">A short loop for class responsibilities and trade-offs. More than one design can be sound.</p>
      ${state.banner ? `<p class="banner">${esc(state.banner)}</p>` : ""}
      <label for="name">What should we call you?</label>
      <input id="name" name="name" type="text" maxlength="40" required autocomplete="nickname" />
      <button class="primary" type="submit">Enter the loop</button>
    </form>`;
  gate.querySelector("form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = new FormData(event.target).get("name");
    try {
      state.learner = await api("/api/learners", { method: "POST", body: { display_name: name } });
      localStorage.setItem("designloop.learner", JSON.stringify(state.learner));
      enter();
      await showProblems();
    } catch (error) {
      state.banner = error.message || "Could not start.";
      renderGate();
    }
  });
}

async function showProblems() {
  clearPoll();
  state.view = "problems";
  markNav();
  state.problems = await api("/api/problems");
  const root = main();
  root.innerHTML = `
    <p class="kicker">Practice loop</p>
    <h1>Pick a problem and design it in writing.</h1>
    <p class="lede">You will name classes, the job each one owns, and what you would change later. Feedback cites your text. It is a rubric reading, not a verdict that one diagram is correct.</p>
    <ol class="loop">
      <li>1 Choose</li><li>2 Design</li><li>3 Submit</li><li>4 Feedback</li><li>5 Revise</li>
    </ol>
    <div class="grid" id="problem-grid"></div>`;
  const grid = document.getElementById("problem-grid");
  state.problems.forEach((problem) => {
    const button = document.createElement("button");
    button.className = "card";
    button.type = "button";
    button.innerHTML = `
      <div class="meta"><span>${esc(problem.difficulty)}</span><span>Text design</span></div>
      <h2>${esc(problem.title)}</h2>
      <p>${esc(problem.summary)}</p>`;
    button.addEventListener("click", () => showProblem(problem.id));
    grid.appendChild(button);
  });
}

async function showProblem(id) {
  clearPoll();
  state.view = "problem";
  markNav();
  const problem = await api(`/api/problems/${id}`);
  const root = main();
  root.innerHTML = `
    <div class="problem-layout">
      <article class="panel">
        <p class="kicker">${esc(problem.difficulty)}</p>
        <h1>${esc(problem.title)}</h1>
        <p class="statement">${esc(problem.statement)}</p>
        <h2>Requirements</h2>
        <ul>${problem.requirements.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
        <h2>Constraints</h2>
        <ul>${problem.constraints.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
        <h2>Situations to account for</h2>
        <ul>${problem.situations.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
        <details class="hints">
          <summary>Hints, if you want them</summary>
          <ul>${problem.hints.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
        </details>
      </article>
      <aside class="panel">
        <p class="kicker">How you will be read</p>
        <h2>Eight questions, not one answer</h2>
        <ul>${problem.rubric.map((item) => `<li><strong>${esc(item.title)}.</strong> ${esc(item.question)}</li>`).join("")}</ul>
        <div class="actions" style="margin-top:1rem">
          <button class="primary" id="start" type="button">Start attempt</button>
          <button class="ghost" id="back" type="button">All problems</button>
        </div>
      </aside>
    </div>`;
  document.getElementById("back").addEventListener("click", () => showProblems());
  document.getElementById("start").addEventListener("click", () => startAttempt(problem.id));
}

async function startAttempt(problemId, fromAttemptId) {
  const body = { learner_id: state.learner.id, problem_id: problemId };
  if (fromAttemptId) body.from_attempt_id = fromAttemptId;
  state.attempt = await api("/api/attempts", { method: "POST", body });
  renderWorkspace(Boolean(fromAttemptId));
}

function renderWorkspace(revised) {
  clearPoll();
  state.view = "workspace";
  markNav();
  const attempt = state.attempt;
  const draft = attempt.draft || emptyDesign();
  const root = main();
  root.innerHTML = `
    <div class="workspace">
      <aside class="panel">
        <p class="kicker">${esc(attempt.problem_title)}</p>
        <h1>Say what each type owns.</h1>
        <p class="lede">A meaningful attempt names the classes, the job of each one, the relationships, a trade-off, and the awkward cases. A diagram can come later. This format is enough to review responsibilities.</p>
        ${revised ? `<p class="note">Started from your last submission. Change the parts the rubric flagged.</p>` : ""}
        <p class="note">The submission is saved before anyone reviews it. If review fails, the design is still here.</p>
      </aside>
      <form class="panel" id="design-form">
        <p class="save-note" id="save-note">Draft</p>
        <div id="form-errors"></div>
        ${field("Assumptions", "assumptions", "What are you not building, and why?", draft.assumptions)}
        <div class="class-head">
          <label>Classes</label>
          <button class="text-button" id="add-class" type="button">Add class</button>
        </div>
        <div id="classes"></div>
        ${field("Relationships", "relationships", "Who calls whom, and what is hidden?", draft.relationships)}
        ${field("Trade-offs", "tradeoffs", "What did you not choose, and what does this choice cost?", draft.tradeoffs)}
        ${field("Extensibility", "extensibility", "What stays stable when a rule changes?", draft.extensibility)}
        ${field("Edge cases", "edge_cases", "Which type owns each awkward situation?", draft.edge_cases)}
        <div class="actions">
          <button class="primary" type="submit">Submit for feedback</button>
          <button class="ghost" id="save-draft" type="button">Save draft</button>
        </div>
      </form>
    </div>`;
  const classes = document.getElementById("classes");
  const sketches = draft.classes && draft.classes.length ? draft.classes : [{}, {}];
  sketches.forEach((sketch) => classes.appendChild(classCard(sketch)));
  document.getElementById("add-class").addEventListener("click", () => {
    classes.appendChild(classCard({}));
  });
  document.getElementById("save-draft").addEventListener("click", () => saveDraft(false));
  document.getElementById("design-form").addEventListener("submit", submitDesign);
  root.querySelectorAll("textarea, input").forEach((node) => {
    node.addEventListener("change", () => saveDraft(true));
  });
}

function classCard(sketch) {
  const card = document.createElement("div");
  card.className = "class-card";
  card.innerHTML = `
    <div class="class-head"><strong>Class</strong><button class="text-button remove" type="button">Remove</button></div>
    <label>Name <input class="class-name" type="text" value="${esc(sketch.name || "")}" placeholder="TicketDesk" /></label>
    <label>Responsibility <span class="field-help">One job.</span>
      <textarea class="class-responsibility" placeholder="Issues a ticket that stores the entry time.">${esc(sketch.responsibility || "")}</textarea>
    </label>
    <label>Collaborators <span class="field-help">Comma-separated types this one uses.</span>
      <input class="class-collaborators" type="text" value="${esc((sketch.collaborators || []).join(", "))}" placeholder="Ticket, Pricing" />
    </label>`;
  card.querySelector(".remove").addEventListener("click", () => card.remove());
  return card;
}

function field(label, name, help, value) {
  return `<label>${esc(label)} <span class="field-help">${esc(help)}</span>
    <textarea name="${name}">${esc(value || "")}</textarea></label>`;
}

function readDesign(form) {
  const data = new FormData(form);
  const classes = [...form.querySelectorAll(".class-card")].map((card) => ({
    name: card.querySelector(".class-name").value.trim(),
    responsibility: card.querySelector(".class-responsibility").value.trim(),
    collaborators: card.querySelector(".class-collaborators").value.split(",").map((part) => part.trim()).filter(Boolean),
  })).filter((item) => item.name || item.responsibility || item.collaborators.length);
  return {
    assumptions: String(data.get("assumptions") || "").trim(),
    classes,
    relationships: String(data.get("relationships") || "").trim(),
    tradeoffs: String(data.get("tradeoffs") || "").trim(),
    extensibility: String(data.get("extensibility") || "").trim(),
    edge_cases: String(data.get("edge_cases") || "").trim(),
  };
}

async function saveDraft(silent) {
  const form = document.getElementById("design-form");
  if (!form || !state.attempt) return;
  try {
    state.attempt = await api(`/api/attempts/${state.attempt.id}/draft`, {
      method: "PUT",
      body: readDesign(form),
    });
    const note = document.getElementById("save-note");
    if (note) note.textContent = silent ? "Draft saved" : "Draft saved just now";
  } catch (error) {
    if (!silent) showErrors(error);
  }
}

async function submitDesign(event) {
  event.preventDefault();
  const form = event.target;
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  clearErrors();
  try {
    const key = form.dataset.key || crypto.randomUUID();
    form.dataset.key = key;
    state.attempt = await api(`/api/attempts/${state.attempt.id}/submit`, {
      method: "POST",
      body: { content: readDesign(form), idempotency_key: key },
    });
    await openAttempt(state.attempt.id);
  } catch (error) {
    showErrors(error);
    button.disabled = false;
  }
}

async function openAttempt(id) {
  clearPoll();
  state.attempt = await api(`/api/attempts/${id}`);
  if (state.attempt.status === "draft") {
    renderWorkspace(false);
    return;
  }
  renderResult();
  if (state.attempt.status === "submitted" || state.attempt.status === "evaluating") {
    state.poll = setInterval(() => refreshAttempt(), 800);
  }
}

async function refreshAttempt() {
  if (!state.attempt) return;
  const latest = await api(`/api/attempts/${state.attempt.id}`);
  state.attempt = latest;
  if (state.view === "result") renderResult();
  if (latest.status === "completed" || latest.status === "failed") clearPoll();
}

function renderResult() {
  state.view = "result";
  markNav();
  const attempt = state.attempt;
  const evaluation = attempt.evaluation;
  const root = main();
  const waiting = attempt.status === "submitted" || attempt.status === "evaluating";
  root.innerHTML = `
    <article class="panel">
      <p class="kicker">${esc(attempt.problem_title)}</p>
      <div class="score-row">
        <div>
          <h1>Feedback</h1>
          <p class="status ${esc(attempt.status)}">${esc(statusLabel(attempt.status))}</p>
        </div>
        ${evaluation && evaluation.overall_score != null ? `<div><p class="score">${evaluation.overall_score.toFixed(1)}<span>/5</span></p><p class="reading">${esc(evaluation.reading || "")}</p></div>` : ""}
      </div>
      ${waiting ? `<p class="summary">Submission saved. Evaluation is running. This page updates on its own. A slow or failed review does not drop the design.</p>` : ""}
      ${attempt.status === "failed" ? `<p class="summary">${esc(attempt.failure_reason || "Evaluation failed.")} The submission is still stored.</p><div class="actions"><button class="primary" id="retry" type="button">Run evaluation again</button></div>` : ""}
      ${evaluation && evaluation.summary ? `<p class="summary">${esc(evaluation.summary)}</p>` : ""}
      ${evaluation && evaluation.note ? `<p class="note">${esc(evaluation.note)} Lexical checks can miss a valid design that uses different words. Treat a limited-confidence line as a question.</p>` : `<p class="note">Lexical checks can miss a valid design that uses different words. Treat a limited-confidence line as a question.</p>`}
      ${evaluation && evaluation.comparison ? `<p class="note">Compared with the previous completed attempt (${signed(evaluation.comparison.previous_score)} / 5).</p>` : ""}
      <div id="criteria"></div>
      <div class="actions" style="margin-top:1rem">
        <button class="primary" id="revise" type="button">Revise and try again</button>
        <button class="ghost" id="back" type="button">All problems</button>
      </div>
    </article>`;
  const criteria = document.getElementById("criteria");
  (evaluation?.feedback || []).forEach((item) => {
    const delta = evaluation.comparison ? evaluation.comparison.deltas[item.criterion_id] : null;
    const block = document.createElement("section");
    block.className = "criterion";
    block.innerHTML = `
      <header>
        <h2>${esc(item.title)}</h2>
        <p>${item.score}/5 <span class="confidence">${esc(item.confidence_label)} confidence</span>
          ${delta == null ? "" : `<span class="delta ${delta > 0 ? "up" : delta < 0 ? "down" : ""}">${delta > 0 ? "+" : ""}${delta}</span>`}
        </p>
      </header>
      <div class="bar"><span style="width:${item.score * 20}%"></span></div>
      <p class="evidence">${esc(item.evidence)}</p>
      ${item.concern ? `<p class="concern">${esc(item.concern)}</p>` : ""}
      <p class="suggestion">${esc(item.suggestion)}</p>`;
    criteria.appendChild(block);
  });
  const retry = document.getElementById("retry");
  if (retry) retry.addEventListener("click", retryEvaluation);
  document.getElementById("revise").addEventListener("click", () => startAttempt(attempt.problem_id, attempt.id));
  document.getElementById("back").addEventListener("click", () => showProblems());
}

async function retryEvaluation() {
  clearPoll();
  const previousId = state.attempt.evaluation && state.attempt.evaluation.id;
  state.attempt = await api(`/api/attempts/${state.attempt.id}/retry`, { method: "POST" });
  renderResult();
  state.poll = setInterval(async () => {
    const latest = await api(`/api/attempts/${state.attempt.id}`);
    const changed = latest.evaluation && latest.evaluation.id !== previousId;
    state.attempt = latest;
    renderResult();
    if (latest.status === "completed" || (latest.status === "failed" && changed)) clearPoll();
  }, 800);
}

async function showHistory() {
  clearPoll();
  state.view = "history";
  markNav();
  state.history = await api(`/api/attempts?learner_id=${encodeURIComponent(state.learner.id)}`);
  state.insights = await api(`/api/learners/${state.learner.id}/insights`);
  const root = main();
  const weakest = state.insights.weakest;
  root.innerHTML = `
    <p class="kicker">Attempt history</p>
    <h1>What keeps showing up.</h1>
    <p class="lede">${state.insights.completed_count} completed of ${state.insights.attempt_count} attempts.</p>
    ${weakest ? `<p class="weak">Lowest average so far: <strong>${esc(weakest.title)}</strong> at ${weakest.average.toFixed(1)}/5. That is the dimension to aim at next.</p>` : `<p class="weak">Complete an attempt to see which dimension you keep losing.</p>`}
    <div id="history-list"></div>`;
  const list = document.getElementById("history-list");
  if (!state.history.length) {
    list.innerHTML = `<p class="lede">No attempts yet.</p>`;
    return;
  }
  state.history.forEach((item) => {
    const button = document.createElement("button");
    button.className = "card history-item";
    button.type = "button";
    button.innerHTML = `
      <strong>${esc(item.problem_title)}</strong>
      <span class="status ${esc(item.status)}">${esc(statusLabel(item.status))}</span>
      <span>${item.overall_score == null ? "—" : `${item.overall_score.toFixed(1)}/5`}</span>
      <span class="confidence">${esc(item.created_at.slice(0, 16).replace("T", " "))}</span>`;
    button.addEventListener("click", () => openAttempt(item.id));
    list.appendChild(button);
  });
}

function showErrors(error) {
  const host = document.getElementById("form-errors");
  if (!host) {
    state.banner = error.message || "Something went wrong.";
    return;
  }
  const errors = error.errors && error.errors.length ? error.errors : [error.message || "Something went wrong."];
  host.innerHTML = `<div class="errors"><ul>${errors.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></div>`;
}

function clearErrors() {
  const host = document.getElementById("form-errors");
  if (host) host.innerHTML = "";
}

function markNav() {
  const onHistory = state.view === "history";
  setCurrent("nav-problems", !onHistory);
  setCurrent("nav-history", onHistory);
}

function setCurrent(id, on) {
  const node = document.getElementById(id);
  if (on) node.setAttribute("aria-current", "page");
  else node.removeAttribute("aria-current");
}

function clearPoll() {
  if (state.poll) clearInterval(state.poll);
  state.poll = null;
}

function statusLabel(status) {
  return {
    draft: "Draft",
    submitted: "Saved",
    evaluating: "Evaluating",
    completed: "Feedback ready",
    failed: "Evaluation failed",
  }[status] || status;
}

function emptyDesign() {
  return { assumptions: "", classes: [], relationships: "", tradeoffs: "", extensibility: "", edge_cases: "" };
}

function signed(value) {
  return value == null ? "—" : Number(value).toFixed(1);
}

function loadLearner() {
  try {
    return JSON.parse(localStorage.getItem("designloop.learner") || "null");
  } catch (_error) {
    return null;
  }
}

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.message || "Request failed");
    error.errors = payload.errors || [];
    throw error;
  }
  return payload;
}
