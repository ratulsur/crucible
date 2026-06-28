const $ = (id) => document.getElementById(id);

// Redirect if already logged in
if (localStorage.getItem("crucible_token")) {
  location.href = "/";
}

function showTab(tab) {
  $("pane-login").classList.toggle("hidden", tab !== "login");
  $("pane-register").classList.toggle("hidden", tab !== "register");
  $("tabs").querySelectorAll("button").forEach((b) => {
    b.classList.toggle("on", b.dataset.tab === tab);
  });
  $("auth-error").classList.add("hidden");
}

$("tabs").querySelectorAll("button").forEach((b) =>
  b.addEventListener("click", () => showTab(b.dataset.tab))
);

function showError(msg) {
  const el = $("auth-error");
  el.textContent = msg;
  el.classList.remove("hidden");
}

async function doAuth(url, body, btn) {
  btn.disabled = true;
  $("auth-error").classList.add("hidden");
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) { showError(data.detail || "Something went wrong"); return; }
    localStorage.setItem("crucible_token", data.access_token);
    localStorage.setItem("crucible_username", data.username);
    localStorage.setItem("crucible_uid", data.user_id);
    location.href = "/";
  } catch (e) {
    showError("Could not reach the server.");
  } finally {
    btn.disabled = false;
  }
}

$("btn-login").addEventListener("click", () => {
  doAuth("/api/auth/login", {
    username: $("login-username").value.trim(),
    password: $("login-password").value,
  }, $("btn-login"));
});

$("btn-register").addEventListener("click", () => {
  doAuth("/api/auth/register", {
    username: $("reg-username").value.trim(),
    password: $("reg-password").value,
  }, $("btn-register"));
});

// Allow Enter key
["login-username","login-password"].forEach((id) =>
  $(id).addEventListener("keydown", (e) => e.key === "Enter" && $("btn-login").click())
);
["reg-username","reg-password"].forEach((id) =>
  $(id).addEventListener("keydown", (e) => e.key === "Enter" && $("btn-register").click())
);
