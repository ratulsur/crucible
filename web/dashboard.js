const $ = (id) => document.getElementById(id);
const token = localStorage.getItem("crucible_token");
const username = localStorage.getItem("crucible_username") || "User";

if (!token) location.href = "/login";

const api = (path, opts = {}) =>
  fetch(path, {
    ...opts,
    headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json", ...(opts.headers || {}) },
  });

$("db-username").textContent = username;
$("btn-logout").addEventListener("click", () => {
  localStorage.clear();
  location.href = "/login";
});

// ── Helpers ──────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function recLabel(r) {
  return (r || "").replace(/_/g, " ");
}

function recClass(r) {
  return { strong_hire: "good", hire: "good", lean_hire: "mid",
           lean_no_hire: "mid", no_hire: "low" }[r] || "mid";
}

function fmtDate(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function decisionBadge(decision) {
  if (!decision) return "";
  const cls = decision === "next_round" ? "decision-next" : "decision-rejected";
  const label = decision === "next_round" ? "✓ Next Round" : "✗ Rejected";
  return `<span class="decision-badge ${cls}">${label}</span>`;
}

// ── Stats ─────────────────────────────────────────────────────────────────────
function renderStats(sessions) {
  const total = sessions.length;
  const decided = sessions.filter((s) => s.decision).length;
  const nextRound = sessions.filter((s) => s.decision === "next_round").length;
  const recs = sessions.map((s) => s.recommendation).filter(Boolean);
  const avgScore = recs.length
    ? (recs.map((r) => ({ strong_hire:5,hire:4,lean_hire:3,lean_no_hire:2,no_hire:1 }[r]||3))
        .reduce((a,b)=>a+b,0) / recs.length).toFixed(1)
    : "—";

  $("db-stats").innerHTML = `
    <div class="stat-card"><span class="stat-val">${total}</span><span class="stat-label">Total Interviews</span></div>
    <div class="stat-card"><span class="stat-val">${nextRound}</span><span class="stat-label">Moved to Next Round</span></div>
    <div class="stat-card"><span class="stat-val">${total - decided}</span><span class="stat-label">Awaiting Decision</span></div>
    <div class="stat-card"><span class="stat-val">${avgScore}</span><span class="stat-label">Avg Score (1–5)</span></div>
  `;
}

// ── Session cards ─────────────────────────────────────────────────────────────
function renderSessions(sessions) {
  const el = $("db-sessions");
  if (!sessions.length) {
    el.innerHTML = '<p class="status-line">No interviews yet. <a href="/" style="color:var(--ember)">Start one →</a></p>';
    return;
  }
  el.innerHTML = sessions.map((s) => `
    <div class="session-card" data-id="${s.session_id}">
      <div class="session-top">
        <div>
          <p class="session-role">${esc(s.role_target || "GenAI Interview")}</p>
          <p class="session-meta">${esc(s.persona_name || "")} · ${esc(s.difficulty || "")} · ${fmtDate(s.finished_at)}</p>
        </div>
        <div class="session-right">
          <span class="rec-badge ${recClass(s.recommendation)}">${recLabel(s.recommendation) || "pending"}</span>
          ${decisionBadge(s.decision)}
        </div>
      </div>
      ${s.report?.competencies ? renderMiniScores(s.report.competencies) : ""}
      <div class="session-actions">
        <button class="mini btn-view-report" data-id="${s.session_id}">View Report</button>
        ${!s.decision ? `
          <button class="btn-next-round" data-id="${s.session_id}">✓ Move to Next Round</button>
          <button class="btn-reject" data-id="${s.session_id}">✗ Reject</button>
        ` : ""}
      </div>
    </div>
  `).join("");

  // Decision buttons
  el.querySelectorAll(".btn-next-round").forEach((b) =>
    b.addEventListener("click", (e) => { e.stopPropagation(); setDecision(b.dataset.id, "next_round"); })
  );
  el.querySelectorAll(".btn-reject").forEach((b) =>
    b.addEventListener("click", (e) => { e.stopPropagation(); setDecision(b.dataset.id, "rejected"); })
  );
  el.querySelectorAll(".btn-view-report").forEach((b) =>
    b.addEventListener("click", (e) => { e.stopPropagation(); openReport(b.dataset.id, sessions); })
  );
}

function renderMiniScores(competencies) {
  return `<div class="mini-scores">${competencies.slice(0,4).map((c) =>
    `<div class="mini-score">
      <span class="mini-score-name">${esc(c.name)}</span>
      <div class="mini-bar"><i style="width:${c.score*20}%"></i></div>
      <span class="mini-score-val">${c.score}/5</span>
    </div>`
  ).join("")}</div>`;
}

// ── Decision ──────────────────────────────────────────────────────────────────
async function setDecision(sessionId, decision) {
  const res = await api(`/api/sessions/${sessionId}/decision`, {
    method: "PATCH",
    body: JSON.stringify({ decision }),
  });
  if (res.ok) loadSessions();
}

// ── Report modal ──────────────────────────────────────────────────────────────
function openReport(sessionId, sessions) {
  const s = sessions.find((x) => x.session_id === sessionId);
  if (!s || !s.report) return;
  const r = s.report;
  let html = `
    <div class="report-head" style="text-align:center;margin-bottom:20px">
      <span class="rec-badge ${recClass(r.recommendation)}">${recLabel(r.recommendation)}</span>
      <h2 class="headline" style="margin-top:12px">${esc(r.headline || "")}</h2>
    </div>`;

  if (r.competencies?.length) {
    html += '<div class="block"><h3>Competencies</h3>';
    for (const c of r.competencies) {
      html += `<div class="comp"><div class="comp-top"><span class="n">${esc(c.name)}</span><span class="s">${c.score}/5</span></div><div class="bar"><i style="width:${c.score*20}%"></i></div><p class="comp-comment">${esc(c.comment)}</p></div>`;
    }
    html += "</div>";
  }
  if (r.strengths?.length)
    html += `<div class="block strengths"><h3>Strengths</h3><ul>${r.strengths.map((i)=>`<li>${esc(i)}</li>`).join("")}</ul></div>`;
  if (r.gaps?.length)
    html += `<div class="block gaps"><h3>Gaps</h3><ul>${r.gaps.map((i)=>`<li>${esc(i)}</li>`).join("")}</ul></div>`;
  if (r.action_items?.length)
    html += `<div class="block"><h3>Practice before next round</h3><ul>${r.action_items.map((i)=>`<li>${esc(i)}</li>`).join("")}</ul></div>`;
  if (r.model_answers?.length) {
    html += '<div class="block"><h3>Model Answers</h3>';
    for (const m of r.model_answers)
      html += `<div class="model-answer"><p class="q">${esc(m.question)}</p><p class="miss">Missing: ${esc(m.what_was_missing)}</p><p class="strong">${esc(m.strong_answer)}</p></div>`;
    html += "</div>";
  }
  if (r.closing_note)
    html += `<div class="block"><h3>From your interviewer</h3><p class="closing">${esc(r.closing_note)}</p></div>`;

  $("modal-body").innerHTML = html;
  $("modal-overlay").classList.remove("hidden");
}

$("modal-close").addEventListener("click", () => $("modal-overlay").classList.add("hidden"));
$("modal-overlay").addEventListener("click", (e) => {
  if (e.target === $("modal-overlay")) $("modal-overlay").classList.add("hidden");
});

// ── Boot ──────────────────────────────────────────────────────────────────────
async function loadSessions() {
  try {
    const res = await api("/api/sessions");
    if (!res.ok) { location.href = "/login"; return; }
    const { sessions } = await res.json();
    renderStats(sessions);
    renderSessions(sessions);
    $("db-loading").style.display = "none";
  } catch (e) {
    $("db-loading").textContent = "Failed to load interviews.";
  }
}

loadSessions();
