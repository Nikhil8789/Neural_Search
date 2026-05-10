import React, { useState } from "react";

export default function DebugPanel({ trace }) {
  const [open, setOpen] = useState(false);
  if (!trace || !Object.keys(trace).length) return null;

  return (
    <div>
      <button
        type="button"
        className="debug-toggle"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span className={`debug-chevron ${open ? "open" : ""}`}>▶</span>
        {open ? "Hide pipeline trace" : "Show pipeline trace"}
      </button>
      {open && (
        <pre className="debug-pre">{JSON.stringify(trace, null, 2)}</pre>
      )}
    </div>
  );
}
