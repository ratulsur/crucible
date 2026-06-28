/* Crucible web client.
 *
 * Two audio modes, chosen at startup from /api/health:
 *   server mode  — record with MediaRecorder, transcribe via /api/stt, and play
 *                  the interviewer's voice from /api/tts (best quality, persona
 *                  voices).
 *   browser mode — fall back to the browser's SpeechRecognition + speech
 *                  synthesis when no server audio key is configured.
 */
const $ = (id) => document.getElementById(id);

const _token = localStorage.getItem("crucible_token");
if (!_token) location.href = "/login";

const api = (path, opts = {}) =>
  fetch(path, {
    ...opts,
    headers: {
      "Authorization": "Bearer " + _token,
      ...(opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      ...(opts.headers || {}),
    },
  });

const state = {
  sessionId: null,
  voice: "sage",
  audioMode: "server", // or "browser"
  recording: false,
  lastQuestion: "",
  mediaRecorder: null,
  chunks: [],
  recognition: null,
  codingActive: false,
};

/* ----------------------------- setup ----------------------------- */
function wireToggles() {
  $("focus").querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () =>
      c.setAttribute("data-on", c.getAttribute("data-on") === "true" ? "false" : "true")
    )
  );
  ["gender", "difficulty"].forEach((id) => {
    const grp = $(id);
    grp.querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => {
        grp.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
        b.classList.add("on");
      })
    );
  });
}

function readSetup() {
  const focus = [...$("focus").querySelectorAll('.chip[data-on="true"]')].map((c) =>
    c.textContent.trim()
  );
  const gender = $("gender").querySelector("button.on").dataset.val;
  const difficulty = $("difficulty").querySelector("button.on").dataset.val;
  const jd = $("jd").value.trim();
  return {
    role_target: $("role").value.trim(),
    focus_areas: focus,
    persona_gender: gender,
    difficulty,
    jd_text: jd || null,
  };
}

/* ----------------------------- orb + log ----------------------------- */
function orb(modeClass, status) {
  const o = $("orb");
  o.className = "orb " + modeClass;
  o.innerHTML = '<div class="orb-ring r1"></div><div class="orb-ring r2"></div><div class="orb-core"></div>';
  if (status !== undefined) $("orb-status").textContent = status;
}

function addBubble(role, text) {
  const div = document.createElement("div");
  div.className = "bubble " + role;
  div.innerHTML = `<span class="speaker">${role === "interviewer" ? $("interviewer-name").textContent : "You"}</span>`;
  div.append(document.createTextNode(text));
  $("log").append(div);
  div.scrollIntoView({ behavior: "smooth", block: "end" });
}

/* ----------------------------- coding exercise ----------------------------- */
function showCodingPanel(problem) {
  state.codingActive = true;
  $("coding-problem").textContent = problem;
  $("code-editor").value = "# Write your Python solution here\n\n";
  $("code-output").textContent = "";
  $("code-output").classList.add("hidden");
  $("coding-panel").classList.remove("hidden");
  $("talk").style.display = "none";
  $("replay").style.display = "none";
  $("code-editor").focus();
}

function hideCodingPanel() {
  state.codingActive = false;
  $("coding-panel").classList.add("hidden");
  $("talk").style.display = "";
  $("replay").style.display = "";
}

async function runCode() {
  const code = $("code-editor").value;
  const btn = $("run-code");
  btn.disabled = true;
  btn.textContent = "Running…";
  try {
    const res = await api("/api/run_code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    const data = await res.json();
    const out = $("code-output");
    out.textContent = data.output || "(no output)";
    out.classList.remove("hidden");
  } catch (e) {
    const out = $("code-output");
    out.textContent = "[Error running code]";
    out.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.textContent = "▶ Run";
  }
}

async function submitCode() {
  const code = $("code-editor").value.trim();
  if (!code) return;
  const btn = $("submit-code");
  btn.disabled = true;
  orb("thinking", "Reviewing your code…");
  try {
    const res = await api("/api/session/code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, code }),
    });
    if (!res.ok) throw new Error("submit failed");
    const data = await res.json();
    hideCodingPanel();
    $("phase-tag").textContent = data.phase;
    await speak(data.utterance);
  } catch (e) {
    orb("idle", "Something went wrong — try again");
    enableTalk(true);
  } finally {
    btn.disabled = false;
  }
}

/* ----------------------------- speaking ----------------------------- */
async function speak(text, skipBubble = false) {
  state.lastQuestion = text;
  if (!skipBubble) addBubble("interviewer", text);
  orb("speaking", "Speaking…");
  if (state.audioMode === "server") {
    try {
      const res = await api("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice: state.voice }),
      });
      if (!res.ok) throw new Error("tts");
      const blob = await res.blob();
      const player = $("player");
      player.src = URL.createObjectURL(blob);
      await player.play();
      await new Promise((r) => (player.onended = r));
    } catch (e) {
      browserSpeak(text);
    }
  } else {
    await browserSpeak(text);
  }
  orb("idle", "Your turn");
  enableTalk(true);
}

function browserSpeak(text) {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window)) return resolve();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 0.98;
    u.onend = resolve;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  });
}

/* ----------------------------- listening ----------------------------- */
function enableTalk(on) {
  $("talk").disabled = !on;
}

function setTalkLabel(t) {
  $("talk-label").textContent = t;
}

async function toggleTalk() {
  if (state.recording) {
    await stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  state.recording = true;
  $("talk").classList.add("recording");
  setTalkLabel("Tap when finished");
  orb("listening", "Listening…");

  if (state.audioMode === "browser") {
    return startBrowserRecognition();
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
  state.mediaRecorder = new MediaRecorder(stream, { mimeType: mime });
  state.chunks = [];
  state.mediaRecorder.ondataavailable = (e) => e.data.size && state.chunks.push(e.data);
  state.mediaRecorder.onstop = () => stream.getTracks().forEach((t) => t.stop());
  state.mediaRecorder.start();
}

async function stopRecording() {
  state.recording = false;
  $("talk").classList.remove("recording");
  setTalkLabel("Tap to answer");
  enableTalk(false);
  orb("thinking", "Transcribing…");

  let text = "";
  if (state.audioMode === "browser") {
    text = await stopBrowserRecognition();
  } else {
    text = await transcribeRecording();
  }
  if (!text.trim()) {
    orb("idle", "Didn't catch that — try again");
    enableTalk(true);
    return;
  }
  addBubble("candidate", text);
  await submitAnswer(text);
}

function transcribeRecording() {
  return new Promise((resolve) => {
    const mr = state.mediaRecorder;
    if (!mr) return resolve("");
    mr.onstop = async () => {
      mr.stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(state.chunks, { type: mr.mimeType });
      const fd = new FormData();
      fd.append("file", blob, "answer." + (mr.mimeType.includes("mp4") ? "mp4" : "webm"));
      try {
        const res = await api("/api/stt", { method: "POST", body: fd, headers: {} });
        const data = await res.json();
        resolve(data.text || "");
      } catch (e) {
        resolve("");
      }
    };
    mr.stop();
  });
}

/* browser SpeechRecognition fallback */
function startBrowserRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    $("orb-status").textContent = "This browser has no speech recognition.";
    return;
  }
  const rec = new SR();
  rec.continuous = true;
  rec.interimResults = false;
  rec.lang = "en-US";
  rec._final = "";
  rec.onresult = (e) => {
    for (let i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) rec._final += e.results[i][0].transcript + " ";
    }
  };
  state.recognition = rec;
  rec.start();
}

function stopBrowserRecognition() {
  return new Promise((resolve) => {
    const rec = state.recognition;
    if (!rec) return resolve("");
    rec.onend = () => resolve((rec._final || "").trim());
    rec.stop();
  });
}

/* ----------------------------- turns ----------------------------- */
async function begin() {
  const btn = $("begin");
  btn.disabled = true;
  $("setup-status").className = "status-line";
  $("setup-status").textContent = "Setting up the room…";
  try {
    const res = await api("/api/session/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(readSetup()),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "start failed");
    const data = await res.json();
    state.sessionId = data.session_id;
    state.voice = data.voice;
    $("interviewer-name").textContent =
      $("gender").querySelector("button.on").dataset.val === "female" ? "Anjali Mehta" : "Arjun Rao";
    $("phase-tag").textContent = data.phase;
    show("room");
    setTalkLabel("Tap to answer");
    await speak(data.utterance);
  } catch (e) {
    $("setup-status").className = "status-line error";
    $("setup-status").textContent = e.message;
    btn.disabled = false;
  }
}

async function submitAnswer(answer) {
  orb("thinking", "Thinking…");
  try {
    const res = await api("/api/session/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, answer }),
    });
    const data = await res.json();
    $("phase-tag").textContent = data.phase;
    await speak(data.utterance);
    if (data.coding_exercise && data.coding_problem) {
      showCodingPanel(data.coding_problem);
    }
  } catch (e) {
    orb("idle", "Something went wrong — try again");
    enableTalk(true);
  }
}

async function endInterview() {
  $("end").disabled = true;
  show("report");
  $("report-body").innerHTML = '<p class="status-line">Writing up the assessment…</p>';
  try {
    const res = await api("/api/session/end", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId }),
    });
    const data = await res.json();
    renderReport(data.report);
  } catch (e) {
    $("report-body").innerHTML = '<p class="status-line error">Could not generate the report.</p>';
  }
}

/* ----------------------------- report ----------------------------- */
function renderReport(r) {
  const recClass = { strong_hire: "good", hire: "good", lean_hire: "mid", lean_no_hire: "mid", no_hire: "low" }[r.recommendation] || "mid";
  const badge = $("rec-badge");
  badge.textContent = (r.recommendation || "").replace(/_/g, " ");
  badge.className = "rec-badge " + recClass;
  $("headline").textContent = r.headline || "";

  let html = "";
  if (r.competencies?.length) {
    html += '<div class="block"><h3>Competencies</h3>';
    for (const c of r.competencies) {
      html += `<div class="comp"><div class="comp-top"><span class="n">${esc(c.name)}</span><span class="s">${c.score}/5</span></div><div class="bar"><i style="width:${c.score * 20}%"></i></div><p class="comp-comment">${esc(c.comment)}</p></div>`;
    }
    html += "</div>";
  }
  html += listBlock("Strengths", r.strengths, "strengths");
  html += listBlock("Gaps", r.gaps, "gaps");
  html += listBlock("Practice before the next round", r.action_items, "");

  if (r.model_answers?.length) {
    html += '<div class="block"><h3>How a strong answer sounds</h3>';
    for (const m of r.model_answers) {
      html += `<div class="model-answer"><p class="q">${esc(m.question)}</p><p class="miss">Missing: ${esc(m.what_was_missing)}</p><p class="strong">${esc(m.strong_answer)}</p></div>`;
    }
    html += "</div>";
  }
  if (r.closing_note) {
    html += `<div class="block"><h3>From your interviewer</h3><p class="closing">${esc(r.closing_note)}</p></div>`;
  }
  $("report-body").innerHTML = html;
}

function listBlock(title, items, cls) {
  if (!items?.length) return "";
  return `<div class="block ${cls}"><h3>${title}</h3><ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul></div>`;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

/* ----------------------------- nav ----------------------------- */
function show(view) {
  ["setup", "room", "report"].forEach((v) => $(v).classList.toggle("hidden", v !== view));
}

/* ----------------------------- boot ----------------------------- */
async function boot() {
  wireToggles();
  try {
    const h = await (await api("/api/health")).json();
    state.audioMode = h.audio_enabled ? "server" : "browser";
  } catch (e) {
    state.audioMode = "browser";
  }
  // Show username + add logout/dashboard links
  const uname = localStorage.getItem("crucible_username");
  if (uname) {
    const nav = document.createElement("div");
    nav.className = "top-nav";
    nav.innerHTML = `<span class="top-nav-user">${uname}</span><a class="ghost-link" href="/dashboard" style="margin:0">Dashboard</a><button class="mini" id="btn-logout-room">Logout</button>`;
    document.querySelector(".stage").prepend(nav);
    document.getElementById("btn-logout-room").addEventListener("click", () => {
      localStorage.clear(); location.href = "/login";
    });
  }

  $("begin").addEventListener("click", begin);
  $("talk").addEventListener("click", toggleTalk);
  $("replay").addEventListener("click", () => state.lastQuestion && speak(state.lastQuestion, true));
  $("end").addEventListener("click", endInterview);
  $("restart").addEventListener("click", () => location.reload());
  $("run-code").addEventListener("click", runCode);
  $("submit-code").addEventListener("click", submitCode);
  $("code-editor").addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const s = e.target.selectionStart;
      e.target.value = e.target.value.substring(0, s) + "    " + e.target.value.substring(e.target.selectionEnd);
      e.target.selectionStart = e.target.selectionEnd = s + 4;
    }
  });
  $("show-history").addEventListener("click", async (e) => {
    e.preventDefault();
    const { sessions } = await (await api("/api/sessions")).json();
    const s = $("setup-status");
    s.className = "status-line";
    s.textContent = sessions.length
      ? `${sessions.length} past interview(s). Most recent: ${sessions[0].role_target} — ${(sessions[0].recommendation || "n/a").replace(/_/g, " ")}.`
      : "No past interviews yet.";
  });
}

boot();
