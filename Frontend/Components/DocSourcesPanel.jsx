import React, { useState } from "react";

function ScoreBar({ score }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 75 ? "#22c55e" :
    pct >= 50 ? "#f59e0b" :
    "#ef4444";
  return (
    <div className="doc-score-row">
      <span className="doc-score-label">Similarity</span>
      <div className="doc-score-track">
        <div
          className="doc-score-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="doc-score-pct" style={{ color }}>{pct}%</span>
    </div>
  );
}

function KeywordTag({ word }) {
  return <span className="doc-keyword-tag">{word}</span>;
}

function ChunkCard({ source, index }) {
  const [expanded, setExpanded] = useState(false);
  const text = source.chunk_text || source.chunk_preview || "";
  const preview = source.chunk_preview || (text.length > 400 ? text.slice(0, 400) + "…" : text);
  const hasMeta = source.matched_attributes?.length > 0;
  const displayText = expanded ? text : preview;

  return (
    <div className="doc-chunk-card">
      {/* Card header */}
      <div className="doc-chunk-header">
        <div className="doc-chunk-badge">
          <span className="doc-chunk-num">#{index + 1}</span>
          <span className="doc-chunk-page">📄 Page {source.page || "?"}</span>
        </div>
        <div className="doc-chunk-filename">{source.filename || "document"}</div>
      </div>

      {/* Score bar */}
      <ScoreBar score={source.scores?.semantic || source.scores?.final || 0} />

      {/* Explanation why it was retrieved */}
      {source.why && (
        <div className="doc-why-line">
          <span className="doc-why-icon">🔍</span>
          <span className="doc-why-text">{source.why}</span>
        </div>
      )}

      {/* Matched keywords */}
      {hasMeta && (
        <div className="doc-keywords-row">
          <span className="doc-keywords-label">Matched:</span>
          {source.matched_attributes.map((kw) => (
            <KeywordTag key={kw} word={kw} />
          ))}
        </div>
      )}

      {/* Chunk text */}
      <div className="doc-chunk-text">{displayText}</div>

      {/* Expand toggle */}
      {text.length > 400 && (
        <button
          className="doc-expand-btn"
          onClick={() => setExpanded((e) => !e)}
          type="button"
        >
          {expanded ? "▲ Show less" : "▼ Show full excerpt"}
        </button>
      )}
    </div>
  );
}

export default function DocSourcesPanel({ sources, filename }) {
  const [open, setOpen] = useState(true);
  if (!sources || sources.length === 0) return null;

  const docSources = sources.filter((s) => s.is_doc_chunk);
  if (docSources.length === 0) return null;

  return (
    <div className="doc-sources-panel">
      <button
        className="doc-sources-toggle"
        onClick={() => setOpen((o) => !o)}
        type="button"
      >
        <span className="doc-sources-icon">📚</span>
        <span className="doc-sources-title">
          Document Sources
          {filename && <span className="doc-sources-file"> — {filename}</span>}
        </span>
        <span className="doc-sources-count">{docSources.length} chunk{docSources.length !== 1 ? "s" : ""}</span>
        <span className="doc-sources-chevron">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="doc-sources-body">
          <div className="doc-explain-intro">
            <span className="doc-explain-icon">💡</span>
            <span>
              These document excerpts were retrieved by <strong>semantic similarity search</strong>{" "}
              and used to generate the answer above. Each chunk shows its page, similarity score,
              and the keywords that matched your query.
            </span>
          </div>
          {docSources.map((src, i) => (
            <ChunkCard key={src.doc_id || i} source={src} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
