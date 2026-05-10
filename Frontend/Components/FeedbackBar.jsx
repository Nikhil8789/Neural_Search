import React, { useState } from "react";
import { sendFeedback } from "../api.js";

export default function FeedbackBar({ threadId, query, answerPreview, docId }) {
  const [status, setStatus] = useState("");

  async function rate(rating) {
    setStatus("");
    try {
      await sendFeedback({
        thread_id: threadId,
        query,
        answer_excerpt: answerPreview?.slice(0, 500),
        rating,
        doc_id: docId,
      });
      setStatus(rating === 1 ? "✓ Thanks!" : "✓ Noted");
    } catch (e) {
      setStatus("Failed");
    }
  }

  return (
    <div className="feedback-bar">
      <span className="feedback-label">Was this helpful?</span>
      <button type="button" className="feedback-btn like" onClick={() => rate(1)}>
        👍 Yes
      </button>
      <button type="button" className="feedback-btn dislike" onClick={() => rate(-1)}>
        👎 No
      </button>
      {status ? <span className="feedback-status">{status}</span> : null}
    </div>
  );
}
