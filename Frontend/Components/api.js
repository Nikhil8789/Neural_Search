/**
 * Uses Vite proxy /api/* -> FastAPI on port 8000 (see vite.config.js).
 * Or set VITE_API_URL e.g. http://localhost:8000
 */
const BASE = import.meta.env.VITE_API_URL || "";

async function req(path, options = {}) {
  const url = `${BASE}${path}`;
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  
  const token = localStorage.getItem("token");
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const r = await fetch(url, {
    headers,
    ...options,
  });
  if (!r.ok) {
    const t = await r.text();
    let msg = r.statusText;
    try {
        const parsed = JSON.parse(t);
        msg = parsed.detail || msg;
    } catch(e) {}
    throw new Error(msg);
  }
  return r.json();
}

export function getConfig() {
  return req("/api/config");
}

export function sendChat(threadId, message) {
  return req("/api/chat", {
    method: "POST",
    body: JSON.stringify({ thread_id: threadId, message }),
  });
}

export function loadThread(threadId) {
  return req(`/api/chat/thread/${encodeURIComponent(threadId)}`);
}

export function sendFeedback(payload) {
  return req("/api/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── Auth Endpoints ──────────────────────────────────────────────

export function signup(name, email, password) {
  return req("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ name, email, password }),
  });
}

export function login(email, password) {
  return req("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

// ── Document Upload / Query ──────────────────────────────────────────────────

export async function uploadDocument(file, sessionToken = null) {
  const url = `${BASE}/api/documents/upload`;
  const form = new FormData();
  form.append("file", file);
  if (sessionToken) form.append("session_token", sessionToken);

  const token = localStorage.getItem("token");
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const r = await fetch(url, { method: "POST", headers, body: form });
  if (!r.ok) {
    const t = await r.text();
    let msg = r.statusText;
    try { msg = JSON.parse(t).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return r.json();
}

export function sendDocQuery(sessionToken, query, threadId = null) {
  return req("/api/documents/query", {
    method: "POST",
    body: JSON.stringify({ session_token: sessionToken, query, thread_id: threadId }),
  });
}

export function clearDocumentSession(sessionToken) {
  return req(`/api/documents/session/${encodeURIComponent(sessionToken)}`, {
    method: "DELETE",
  });
}
