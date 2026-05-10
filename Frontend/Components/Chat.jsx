import React, { useCallback, useEffect, useRef, useState } from "react";
import { clearDocumentSession, getConfig, loadThread, sendChat, sendDocQuery } from "../api.js";
import DocumentUpload from "./DocumentUpload.jsx";
import MessageBubble from "./MessageBubble.jsx";

const SAMPLE_QUESTIONS = [
  "Explain hybrid IR with BM25 and dense embeddings",
  "How does RAG generation work with retrieved context?",
  "Compare BM25 vs semantic search for information retrieval",
  "What is explainable ranking and why does it matter?",
];

const DOC_SAMPLE_QUESTIONS = [
  "Summarize the key points of this document",
  "What are the main findings or conclusions?",
  "List the important concepts mentioned",
  "What does this document say about [your topic]?",
];

export default function Chat({ user, onLogout }) {
  const [threadId, setThreadId]         = useState(null);
  const [messages, setMessages]         = useState([]);
  const [input, setInput]               = useState("");
  const [loading, setLoading]           = useState(false);
  const [suggestions, setSuggestions]   = useState([]);
  const [error, setError]               = useState("");
  const [serverInfo, setServerInfo]     = useState(null);
  const [showDocPanel, setShowDocPanel] = useState(false);
  const [docSession, setDocSession]     = useState(null);   // { session_token, filename, chunk_count, page_count }
  const listRef  = useRef(null);
  const inputRef = useRef(null);

  const providerLabel = (info) => {
    if (!info || !info.openai_configured) return { label: "No LLM", on: false };
    const p = info.llm_provider || "openai";
    const names = { openai: "OpenAI", gemini: "Gemini", groq: "Groq" };
    return { label: names[p] || p, on: true };
  };

  const scrollDown = useCallback(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  useEffect(() => {
    getConfig()
      .then(setServerInfo)
      .catch(() => setServerInfo({ openai_configured: false }));
  }, []);

  useEffect(() => { scrollDown(); }, [messages, scrollDown]);

  /* Auto-resize textarea */
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [input]);

  async function submit(text) {
    text = text.trim();
    if (!text || loading) return;
    setError("");
    setInput("");
    setSuggestions([]);
    setMessages((m) => [...m, { role: "user", content: text }]);
    setLoading(true);

    // Add a typing placeholder
    setMessages((m) => [...m, { role: "assistant", content: "__typing__", _typing: true }]);

    try {
      let res;
      if (docSession) {
        // ── Document query path ──────────────────────────────────
        res = await sendDocQuery(docSession.session_token, text, threadId);
        if (res.thread_id) setThreadId(res.thread_id);
        setMessages((m) => [
          ...m.filter((msg) => !msg._typing),
          {
            role: "assistant",
            content: res.answer,
            sources: res.sources,
            action: res.action || "doc_retrieve",
            agent_confidence: res.agent_confidence,
            trace: res.trace,
            userQuery: text,
            isDocResponse: true,
            docFilename: docSession.filename,
          },
        ]);
        setSuggestions([]);
      } else {
        // ── General IR corpus path ───────────────────────────────
        res = await sendChat(threadId, text);
        setThreadId(res.thread_id);
        setSuggestions(res.suggestions || []);
        setMessages((m) => [
          ...m.filter((msg) => !msg._typing),
          {
            role: "assistant",
            content: res.answer,
            sources: res.sources,
            action: res.action,
            agent_confidence: res.agent_confidence,
            trace: res.trace,
            userQuery: text,
          },
        ]);
      }
    } catch (err) {
      setError(err.message || String(err));
      setMessages((m) => [
        ...m.filter((msg) => !msg._typing),
        {
          role: "assistant",
          content: `Something went wrong: ${err.message || err}`,
          sources: [],
          action: "error",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    submit(input);
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(input);
    }
  }

  async function restoreThread() {
    const id = prompt("Paste thread_id to restore from MongoDB:");
    if (!id) return;
    setError("");
    try {
      const data = await loadThread(id);
      setThreadId(data.thread_id);
      const restored = (data.messages || []).map((msg) => ({
        role: msg.role,
        content: msg.content,
        sources: msg.meta?.sources,
        action: msg.meta?.stage,
        trace: msg.meta?.trace,
      }));
      setMessages(restored);
    } catch (e) {
      setError(e.message);
    }
  }

  function handleSessionReady(uploadResult) {
    setDocSession(uploadResult);
    // Announce in chat
    setMessages((m) => [
      ...m,
      {
        role: "assistant",
        content:
          `✅ **Document ready:** "${uploadResult.filename}"\n\n` +
          `📊 Indexed **${uploadResult.chunk_count} chunks** across **${uploadResult.page_count} page(s)**.\n\n` +
          `💬 Ask me anything about this document — I'll answer *only* from its content and show you the exact source excerpts used.\n\n` +
          `🔍 IR Pipeline: text extraction → chunking (${uploadResult.chunk_count} chunks) → embedding → vector indexing → semantic search + RAG generation`,
        sources: [],
        action: "doc_ready",
        isDocResponse: true,
        docFilename: uploadResult.filename,
      },
    ]);
  }

  async function handleDocClear() {
    if (docSession) {
      try { await clearDocumentSession(docSession.session_token); } catch (_) {}
      setDocSession(null);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "📄 Document cleared. Returning to the general IR knowledge base.",
          sources: [],
          action: "direct",
        },
      ]);
    }
  }

  const openai_on = serverInfo?.openai_configured;
  const samples = docSession ? DOC_SAMPLE_QUESTIONS : SAMPLE_QUESTIONS;

  return (
    <div className="app-shell">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-logo">
          <div className="logo-icon">🧠</div>
          <div className="logo-text">
            <span className="logo-title">NeuralSearch</span>
            <span className="logo-subtitle">IR Research Agent</span>
          </div>
        </div>

        <div className="header-actions">
          {user && (
            <span className="user-greeting">Hi, {user.name}</span>
          )}
          {serverInfo && (() => { const { label, on } = providerLabel(serverInfo); return (
            <span className={`status-badge ${on ? "" : "off"}`}>
              <span className="status-dot" />
              {on ? `${label} Active` : "No LLM"}
            </span>
          );})()}

          {/* Document mode indicator */}
          {docSession ? (
            <span className="doc-mode-badge">
              <span className="doc-mode-dot" />
              📄 {docSession.filename.length > 20 ? docSession.filename.slice(0, 18) + "…" : docSession.filename}
            </span>
          ) : null}

          <button
            type="button"
            className={`btn-ghost doc-upload-toggle ${showDocPanel ? "active" : ""} ${docSession ? "has-doc" : ""}`}
            onClick={() => setShowDocPanel((s) => !s)}
            title={docSession ? "Manage uploaded document" : "Upload a document"}
          >
            📄 {docSession ? "Doc Active" : "Upload Doc"}
          </button>

          <button type="button" className="btn-ghost" onClick={restoreThread}>
            📂 Restore thread
          </button>
          <button type="button" className="btn-ghost logout" onClick={onLogout}>
            🚪 Logout
          </button>
        </div>
      </header>

      {/* ── Document Upload Panel (collapsible) ── */}
      {showDocPanel && (
        <DocumentUpload
          activeSession={docSession}
          onSessionReady={(result) => {
            handleSessionReady(result);
            setShowDocPanel(false);
          }}
          onClear={handleDocClear}
        />
      )}

      {/* ── Chat window ── */}
      <div className="chat-window" ref={listRef}>
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">{docSession ? "📄" : "🔍"}</div>
            <div className="empty-title">
              {docSession ? `Chat with "${docSession.filename}"` : "Ask me anything about IR"}
            </div>
            <p className="empty-desc">
              {docSession
                ? `Document indexed with ${docSession.chunk_count} searchable chunks. Ask questions and get answers grounded in its content with source citations.`
                : "Hybrid BM25 + semantic retrieval, explainable ranking, and RAG-powered answers about information retrieval systems."}
            </p>
            <div className="sample-chips">
              {samples.map((q) => (
                <button
                  key={q}
                  className="sample-chip"
                  type="button"
                  onClick={() => submit(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) =>
          msg._typing ? (
            <div className="bubble-row" key={`typing-${i}`}>
              <div className="assistant-wrapper">
                <div className="avatar">🤖</div>
                <div className="bubble assistant" style={{ padding: "0.5rem 0.8rem" }}>
                  <div className="typing-dots">
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <MessageBubble
              key={i}
              role={msg.role}
              content={msg.content}
              threadId={threadId}
              userQuery={msg.userQuery}
              sources={msg.sources}
              action={msg.action}
              agent_confidence={msg.agent_confidence}
              trace={msg.trace}
              isDocResponse={msg.isDocResponse}
              docFilename={msg.docFilename}
            />
          )
        )}
      </div>

      {/* ── Suggestions ── */}
      {suggestions.length > 0 && (
        <div className="suggestions-bar">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              className="suggestion-chip"
              onClick={() => submit(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* ── Error banner ── */}
      {error && (
        <div className="error-banner">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* ── Composer ── */}
      <div className="composer-area">
        {docSession && (
          <div className="doc-composer-hint">
            <span className="doc-composer-icon">📄</span>
            Querying: <strong>{docSession.filename}</strong>
            <span className="doc-composer-hint-sep">·</span>
            <button
              type="button"
              className="doc-composer-switch"
              onClick={() => setShowDocPanel(true)}
            >
              Change
            </button>
            <button
              type="button"
              className="doc-composer-switch"
              onClick={handleDocClear}
            >
              ✕ Remove
            </button>
          </div>
        )}
        <form onSubmit={onSubmit}>
          <div className="composer-box">
            <textarea
              ref={inputRef}
              className="composer-textarea"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={
                docSession
                  ? `Ask a question about "${docSession.filename}"…`
                  : "Ask about retrieval, RAG, BM25, embeddings… (Enter to send)"
              }
              rows={1}
              disabled={loading}
            />
            <button
              type="submit"
              className="send-btn"
              disabled={loading || !input.trim()}
              aria-label="Send message"
            >
              {loading ? "⏳" : "➤"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
