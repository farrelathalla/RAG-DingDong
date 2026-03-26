// frontend/app.js
const API = "";  // same origin

// ── State ──────────────────────────────────────────────────────────────────────
let chatHistory = [];
let isIndexed = false;
let isAuthenticated = false;

// ── DOM refs ───────────────────────────────────────────────────────────────────
const messagesEl = document.getElementById("messages");
const queryInput = document.getElementById("query-input");
const sendBtn = document.getElementById("send-btn");
const indexBtn = document.getElementById("index-btn");
const loginBtn = document.getElementById("login-btn");
const loggedInInfo = document.getElementById("logged-in-info");
const authStatusMsg = document.getElementById("auth-status-msg");
const indexMsg = document.getElementById("index-msg");
const indexProgress = document.getElementById("index-progress");
const statPages = document.getElementById("stat-pages");
const statDocs = document.getElementById("stat-docs");
const docsList = document.getElementById("docs-list");
const sourcesPanel = document.getElementById("sources-panel");
const sourcesList = document.getElementById("sources-list");

// ── Init ───────────────────────────────────────────────────────────────────────
async function init() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("auth") === "success") {
    window.history.replaceState({}, "", "/");
  }
  await checkAuth();
  await loadStatus();
}

// ── Auth ────────────────────────────────────────────────────────────────────────
async function checkAuth() {
  try {
    const r = await fetch(`${API}/auth/status`);
    const data = await r.json();
    isAuthenticated = data.authenticated;
    if (isAuthenticated) {
      loginBtn.classList.add("hidden");
      loggedInInfo.classList.remove("hidden");
      authStatusMsg.textContent = "Connected to Google Drive";
      indexBtn.disabled = false;
    } else {
      loginBtn.classList.remove("hidden");
      loggedInInfo.classList.add("hidden");
      authStatusMsg.textContent = "Not connected";
    }
  } catch {
    authStatusMsg.textContent = "Could not reach API";
  }
}

// ── Status & docs ──────────────────────────────────────────────────────────────
async function loadStatus() {
  try {
    const [statusR, docsR] = await Promise.all([
      fetch(`${API}/api/status`),
      fetch(`${API}/api/docs`),
    ]);
    const status = await statusR.json();
    const docsData = await docsR.json();

    isIndexed = status.indexed;
    statPages.textContent = status.page_count || "—";
    statDocs.textContent = status.doc_count || "—";

    if (status.indexing) {
      indexMsg.textContent = "Indexing in progress...";
      indexProgress.classList.remove("hidden");
      indexBtn.disabled = true;
      setTimeout(loadStatus, 3000);
    } else {
      indexProgress.classList.add("hidden");
    }

    docsList.innerHTML = "";
    for (const name of (docsData.docs || [])) {
      const li = document.createElement("li");
      li.title = name;
      li.textContent = name;
      docsList.appendChild(li);
    }

    if (isIndexed) {
      enableChat();
      indexMsg.textContent = `Index ready · ${status.page_count} pages`;
    }
  } catch (e) {
    indexMsg.textContent = "Could not load status";
  }
}

// ── Index trigger ──────────────────────────────────────────────────────────────
indexBtn.addEventListener("click", async () => {
  indexBtn.disabled = true;
  indexMsg.textContent = "Starting index...";
  indexProgress.classList.remove("hidden");
  try {
    const r = await fetch(`${API}/api/index`, { method: "POST" });
    const data = await r.json();
    if (r.ok) {
      indexMsg.textContent = "Indexing started — this may take a few minutes...";
      setTimeout(pollIndexStatus, 3000);
    } else {
      indexMsg.textContent = data.detail || "Failed to start indexing";
      indexBtn.disabled = false;
      indexProgress.classList.add("hidden");
    }
  } catch {
    indexMsg.textContent = "Request failed";
    indexBtn.disabled = false;
    indexProgress.classList.add("hidden");
  }
});

async function pollIndexStatus() {
  await loadStatus();
  const r = await fetch(`${API}/api/status`);
  const data = await r.json();
  if (data.indexing) {
    setTimeout(pollIndexStatus, 3000);
  } else {
    indexBtn.disabled = false;
    indexProgress.classList.add("hidden");
    if (data.indexed) {
      indexMsg.textContent = `Done! ${data.page_count} pages indexed.`;
      enableChat();
    }
  }
}

// ── Chat ────────────────────────────────────────────────────────────────────────
function enableChat() {
  queryInput.disabled = false;
  sendBtn.disabled = false;
  queryInput.placeholder = "Ask something about your study materials...";
}

sendBtn.addEventListener("click", sendMessage);
queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

async function sendMessage() {
  const query = queryInput.value.trim();
  if (!query) return;

  const welcome = messagesEl.querySelector(".welcome-msg");
  if (welcome) welcome.remove();

  queryInput.value = "";
  sendBtn.disabled = true;
  queryInput.disabled = true;
  sourcesPanel.classList.add("hidden");

  appendMessage("user", query);

  const thinkingId = appendMessage("assistant", "Searching your materials...", true);
  chatHistory.push({ role: "user", content: query });

  try {
    const r = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, history: chatHistory.slice(-10) }),
    });
    const data = await r.json();
    removeMessage(thinkingId);

    const answer = data.answer || "No answer returned.";
    appendMessage("assistant", answer);
    chatHistory.push({ role: "assistant", content: answer });

    if (data.sources && data.sources.length > 0) {
      renderSources(data.sources);
    }
  } catch (e) {
    removeMessage(thinkingId);
    appendMessage("assistant", "Error: Could not reach the API. Is the server running?");
  } finally {
    sendBtn.disabled = false;
    queryInput.disabled = false;
    queryInput.focus();
  }
}

// ── Message rendering ──────────────────────────────────────────────────────────
let msgCounter = 0;

function appendMessage(role, text, isThinking = false) {
  const id = `msg-${++msgCounter}`;
  const div = document.createElement("div");
  div.id = id;
  div.className = `message ${role}${isThinking ? " thinking" : ""}`;
  div.innerHTML = `
    <div class="message-label">${role === "user" ? "You" : "DingDong"}</div>
    <div class="bubble">${escapeHtml(text)}</div>
  `;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return id;
}

function removeMessage(id) {
  document.getElementById(id)?.remove();
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br/>");
}

// ── Sources rendering ──────────────────────────────────────────────────────────
function renderSources(sources) {
  sourcesList.innerHTML = "";
  for (const s of sources) {
    const card = document.createElement("div");
    card.className = "source-card";
    card.innerHTML = `
      <div class="doc-name" title="${escapeHtml(s.doc_name)}">${escapeHtml(s.doc_name)}</div>
      <div class="page-num">Page ${s.page_num}</div>
      <div class="snippet">${escapeHtml(s.snippet)}</div>
    `;
    sourcesList.appendChild(card);
  }
  sourcesPanel.classList.remove("hidden");
}

// ── Start ──────────────────────────────────────────────────────────────────────
init();
