import React, { useMemo } from "react";
import DocSourcesPanel from "./DocSourcesPanel.jsx";
import SourcesPanel from "./SourcesPanel.jsx";
import FeedbackBar from "./FeedbackBar.jsx";
import DebugPanel from "./DebugPanel.jsx";

/* ---------------------------------------------------------------
   Lightweight markdown renderer — no external deps needed.
   Handles: headings, bold, italic, inline code, code blocks,
   horizontal rules, unordered/ordered lists, links, paragraphs.
--------------------------------------------------------------- */
function renderMarkdown(text) {
  if (!text) return [];

  // Split into blocks (double newline = new block)
  const lines = text.split("\n");
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // --- Code fence ---
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      blocks.push({ type: "code", lang, content: codeLines.join("\n") });
      i++;
      continue;
    }

    // --- Headings ---
    if (line.startsWith("### ")) {
      blocks.push({ type: "h3", content: line.slice(4) });
      i++;
      continue;
    }
    if (line.startsWith("## ")) {
      blocks.push({ type: "h2", content: line.slice(3) });
      i++;
      continue;
    }
    if (line.startsWith("# ")) {
      blocks.push({ type: "h1", content: line.slice(2) });
      i++;
      continue;
    }

    // --- HR ---
    if (/^---+$/.test(line.trim())) {
      blocks.push({ type: "hr" });
      i++;
      continue;
    }

    // --- Unordered list ---
    if (/^[\-\*] /.test(line)) {
      const items = [];
      while (i < lines.length && /^[\-\*] /.test(lines[i])) {
        items.push(lines[i].slice(2));
        i++;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    // --- Ordered list ---
    if (/^\d+\. /.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s/, ""));
        i++;
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    // --- Empty line (skip) ---
    if (line.trim() === "") {
      i++;
      continue;
    }

    // --- Paragraph ---
    const paraLines = [];
    while (i < lines.length && lines[i].trim() !== "" && !lines[i].startsWith("#") && !lines[i].startsWith("```") && !/^---+$/.test(lines[i].trim())) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length) {
      blocks.push({ type: "p", content: paraLines.join(" ") });
    }
  }

  return blocks;
}

/* Inline formatting: **bold**, *italic*, `code`, [link](url) */
function InlineText({ text }) {
  if (!text) return null;

  const parts = [];
  // Pattern order matters
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[([^\]]+)\]\(([^)]+)\))/g;
  let last = 0;
  let match;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const raw = match[0];
    if (raw.startsWith("**")) parts.push(<strong key={match.index}>{raw.slice(2, -2)}</strong>);
    else if (raw.startsWith("*")) parts.push(<em key={match.index}>{raw.slice(1, -1)}</em>);
    else if (raw.startsWith("`")) parts.push(<code key={match.index}>{raw.slice(1, -1)}</code>);
    else if (raw.startsWith("[")) parts.push(<a key={match.index} href={match[3]} target="_blank" rel="noopener noreferrer">{match[2]}</a>);
    last = match.index + raw.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
}

function MarkdownBlock({ block, idx }) {
  switch (block.type) {
    case "h1": return <h1 key={idx}><InlineText text={block.content} /></h1>;
    case "h2": return <h2 key={idx}><InlineText text={block.content} /></h2>;
    case "h3": return <h3 key={idx}><InlineText text={block.content} /></h3>;
    case "hr": return <hr key={idx} />;
    case "code": return (
      <pre key={idx}>
        <code>{block.content}</code>
      </pre>
    );
    case "ul": return (
      <ul key={idx}>
        {block.items.map((item, j) => (
          <li key={j}><InlineText text={item} /></li>
        ))}
      </ul>
    );
    case "ol": return (
      <ol key={idx}>
        {block.items.map((item, j) => (
          <li key={j}><InlineText text={item} /></li>
        ))}
      </ol>
    );
    case "p":
    default: return (
      <p key={idx}><InlineText text={block.content} /></p>
    );
  }
}

/* Detect quota-warning text and render a styled banner */
function parseQuotaBanner(text) {
  if (!text) return { hasBanner: false, rest: text };
  const quotaLine = "⚠️ **OpenAI quota exhausted**";
  if (text.startsWith(quotaLine) || text.includes("OpenAI quota exhausted")) {
    // Extract the banner portion (up to the --- divider or knowledge base content)
    const divIdx = text.indexOf("---");
    if (divIdx !== -1) {
      const bannerText = text.slice(0, divIdx).trim();
      const bodyText = text.slice(divIdx + 3).trim();
      return { hasBanner: true, bannerText, bodyText };
    }
  }
  return { hasBanner: false, rest: text };
}

export default function MessageBubble({
  role,
  content,
  threadId,
  userQuery,
  sources,
  action,
  agent_confidence: agentConfidence,
  trace,
  isDocResponse,
  docFilename,
}) {
  const isUser = role === "user";
  const blocks = useMemo(() => (isUser ? [] : renderMarkdown(content)), [content, isUser]);
  const { hasBanner, bannerText, bodyText } = useMemo(() => parseQuotaBanner(content), [content]);

  const actionEmoji = {
    retrieve: "🔍",
    doc_retrieve: "📄",
    doc_ready: "✅",
    direct: "💬",
    clarify: "❓",
    error: "⚠️",
  };

  if (isUser) {
    return (
      <div className="bubble-row user">
        <div className="bubble user">{content}</div>
      </div>
    );
  }

  return (
    <div className="bubble-row">
      <div className="assistant-wrapper">
        <div className="avatar">🤖</div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="bubble assistant">
            {/* Quota banner */}
            {hasBanner && (
              <div className="quota-banner">
                <span className="quota-banner-icon">⚠️</span>
                <span>
                  {bannerText.replace("⚠️ **OpenAI quota exhausted** — RAG generation is unavailable right now.", "").trim()
                    ? bannerText.replace("⚠️", "").replace(/\*\*/g, "").trim()
                    : <>
                        <strong>OpenAI quota exhausted</strong> — RAG generation is unavailable.{" "}
                        Add billing credits at{" "}
                        <a href="https://platform.openai.com/account/billing" target="_blank" rel="noopener noreferrer">
                          platform.openai.com/account/billing
                        </a>
                        . BM25 results shown below.
                      </>
                  }
                </span>
              </div>
            )}

            {/* Answer body */}
            <div className="answer-content">
              {hasBanner
                ? renderMarkdown(bodyText).map((b, i) => <MarkdownBlock block={b} idx={i} key={i} />)
                : blocks.map((b, i) => <MarkdownBlock block={b} idx={i} key={i} />)
              }
            </div>

            {/* Action + confidence row */}
            {action && (
              <div className="action-meta">
                <span className={`action-tag ${action}`}>
                  {actionEmoji[action] || "🤖"} {action}
                </span>
                {agentConfidence != null && (
                  <span className="confidence-pill">
                    Confidence: {(agentConfidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Sources — use DocSourcesPanel for doc responses */}
          {isDocResponse
            ? <DocSourcesPanel sources={sources} filename={docFilename} />
            : <SourcesPanel sources={sources} />
          }

          {/* Feedback */}
          <FeedbackBar
            threadId={threadId}
            query={userQuery}
            answerPreview={content}
            docId={sources?.[0]?.doc_id}
          />

          {/* Debug */}
          <DebugPanel trace={trace} />
        </div>
      </div>
    </div>
  );
}
