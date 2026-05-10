import React, { useCallback, useRef, useState } from "react";
import { uploadDocument } from "../api.js";

const ACCEPTED = ".pdf,.txt,.docx,.doc";

export default function DocumentUpload({ onSessionReady, onClear, activeSession }) {
  const [dragging, setDragging]   = useState(false);
  const [status, setStatus]       = useState("idle"); // idle | uploading | ready | error
  const [message, setMessage]     = useState("");
  const [progress, setProgress]   = useState(0);
  const fileRef = useRef(null);

  const processFile = useCallback(async (file) => {
    if (!file) return;

    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!["pdf", "txt", "docx", "doc"].includes(ext)) {
      setStatus("error");
      setMessage(`Unsupported file type: .${ext}. Please upload PDF, TXT, or DOCX.`);
      return;
    }

    setStatus("uploading");
    setMessage(`Processing "${file.name}"…`);
    setProgress(20);

    // Simulate progress steps while waiting
    const progressTimer = setInterval(() => {
      setProgress((p) => (p < 85 ? p + Math.random() * 15 : p));
    }, 600);

    try {
      const result = await uploadDocument(file, activeSession?.session_token);
      clearInterval(progressTimer);
      setProgress(100);
      setStatus("ready");
      setMessage(result.message || `Ready — ${result.chunk_count} chunks indexed`);
      onSessionReady(result);
    } catch (err) {
      clearInterval(progressTimer);
      setStatus("error");
      setMessage(`Upload failed: ${err.message || err}`);
      setProgress(0);
    }
  }, [activeSession, onSessionReady]);

  const onFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
    e.target.value = "";
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  }, [processFile]);

  const onDragOver = (e) => { e.preventDefault(); setDragging(true); };
  const onDragLeave = () => setDragging(false);

  const handleClear = () => {
    setStatus("idle");
    setMessage("");
    setProgress(0);
    onClear();
  };

  return (
    <div className={`doc-upload-panel ${status}`}>
      {/* Header */}
      <div className="doc-upload-header">
        <span className="doc-upload-icon">📄</span>
        <div>
          <div className="doc-upload-title">Document Analysis</div>
          <div className="doc-upload-subtitle">Upload PDF, DOCX, or TXT to chat with it</div>
        </div>
        {activeSession && (
          <button className="doc-clear-btn" onClick={handleClear} title="Remove document">
            ✕ Clear
          </button>
        )}
      </div>

      {/* Active document badge */}
      {activeSession && status === "ready" && (
        <div className="doc-active-badge">
          <span className="doc-active-dot" />
          <div className="doc-active-info">
            <span className="doc-active-name">📎 {activeSession.filename}</span>
            <span className="doc-active-meta">
              {activeSession.chunk_count} chunks · {activeSession.page_count} page{activeSession.page_count !== 1 ? "s" : ""}
            </span>
          </div>
          <span className="doc-active-status">Active</span>
        </div>
      )}

      {/* Drop zone (only show when idle or error) */}
      {(status === "idle" || status === "error") && (
        <div
          className={`doc-drop-zone ${dragging ? "dragging" : ""}`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={() => fileRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && fileRef.current?.click()}
          aria-label="Upload document"
        >
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPTED}
            style={{ display: "none" }}
            onChange={onFileChange}
            id="doc-file-input"
          />
          <div className="doc-drop-icon">{dragging ? "📂" : "⬆️"}</div>
          <div className="doc-drop-text">
            {dragging ? "Drop to upload" : "Drag & drop or click to browse"}
          </div>
          <div className="doc-drop-formats">PDF · DOCX · TXT · up to 50 MB</div>
        </div>
      )}

      {/* Upload progress */}
      {status === "uploading" && (
        <div className="doc-progress-area">
          <div className="doc-progress-label">
            <span className="doc-spinner" />
            {message}
          </div>
          <div className="doc-progress-track">
            <div className="doc-progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="doc-progress-steps">
            <span className={progress > 20 ? "step done" : "step"}>Extract</span>
            <span className={progress > 40 ? "step done" : "step"}>Chunk</span>
            <span className={progress > 60 ? "step done" : "step"}>Embed</span>
            <span className={progress > 80 ? "step done" : "step"}>Index</span>
          </div>
        </div>
      )}

      {/* Error message */}
      {status === "error" && (
        <div className="doc-error-msg">⚠️ {message}</div>
      )}

      {/* Ready success line */}
      {status === "ready" && (
        <div className="doc-ready-msg">
          ✅ {message}
          <div className="doc-ready-hint">
            💬 Ask questions below — answers will come from this document only
          </div>
        </div>
      )}
    </div>
  );
}
