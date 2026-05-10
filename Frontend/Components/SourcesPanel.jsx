import React, { useState } from "react";

function ScoreBar({ label, value, max = 1, color = "#6366f1" }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return (
    <div className="score-chip" title={`${label}: ${value}`}>
      {label} {value.toFixed(2)}
    </div>
  );
}

export default function SourcesPanel({ sources }) {
  const [open, setOpen] = useState(true);
  if (!sources || !sources.length) return null;

  return (
    <div className="sources-panel">
      <div
        className="sources-header"
        onClick={() => setOpen((o) => !o)}
        role="button"
        aria-expanded={open}
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && setOpen((o) => !o)}
      >
        <span className="sources-header-icon">🔍</span>
        <span className="sources-header-label">Retrieved Sources</span>
        <span className="sources-count">{sources.length}</span>
        <span className={`sources-chevron ${open ? "open" : ""}`}>▶</span>
      </div>

      {open && (
        <div className="sources-list">
          {sources.map((s, idx) => (
            <div className="source-card" key={s.doc_id}>
              <div className="source-card-header">
                <div className="source-rank">{idx + 1}</div>
                <span className="source-title">{s.title}</span>
                <span className="source-id">{s.doc_id}</span>
              </div>
              {s.why && (
                <div className="source-why">{s.why.replace("Document retrieved because it matches: ", "")}</div>
              )}
              {s.scores && (
                <div className="source-scores">
                  <span className="score-chip final">⭐ {s.scores.final?.toFixed(3)}</span>
                  <span className="score-chip">BM25 {s.scores.keyword?.toFixed(2)}</span>
                  <span className="score-chip">Sem {s.scores.semantic?.toFixed(3)}</span>
                  <span className="score-chip">Attr {s.scores.attribute?.toFixed(2)}</span>
                  {s.scores.feedback_boost ? (
                    <span className="score-chip">FB {s.scores.feedback_boost > 0 ? "+" : ""}{s.scores.feedback_boost}</span>
                  ) : null}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
