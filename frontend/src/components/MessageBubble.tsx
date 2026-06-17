import { ThumbsDown, ThumbsUp } from "lucide-react";

import type { ChatMessage, FeedbackRating } from "../types";

function MessageBubble({
  message,
  onFeedback,
}: {
  message: ChatMessage;
  onFeedback: (message: ChatMessage, rating: FeedbackRating) => void;
}) {
  const totalTokens = message.usage?.total_tokens;
  const profile = message.retrievalProfile;
  const canSendFeedback =
    message.role === "assistant" && message.id !== "welcome" && !message.error && message.elapsedMs !== undefined;
  return (
    <article className={`message ${message.role}`}>
      <div className="avatar" aria-hidden="true">
        {message.role === "user" ? "你" : "AI"}
      </div>
      <div className={`bubble ${message.error ? "error" : ""}`}>
        <p>{message.content}</p>
        {!!message.statusLines?.length && <div className="status-lines">{message.statusLines.join(" | ")}</div>}
        {profile && (
          <div className="profile-snapshot">
            <span>{profile.search_type}</span>
            <span>top={profile.top_k}</span>
            <span>fetch={profile.fetch_k}</span>
            <span>rerank={profile.reranker_enabled ? "on" : "off"}</span>
            <span>ctx={profile.max_context_chars}</span>
          </div>
        )}
        {!!message.citations?.length && (
          <div className="citations">
            {message.citations.map((citation, index) => (
              <span className="citation" key={`${citation.label || citation.source}-${index}`}>
                {citation.label || citation.source || "引用"}
              </span>
            ))}
          </div>
        )}
        {!!message.toolTraces?.length && (
          <div className="tool-traces">
            {message.toolTraces.map((trace, index) => (
              <details className="tool-trace" key={`${trace.toolName || "tool"}-${index}`}>
                <summary>{trace.toolName || trace.statusLine || "tool_result"}</summary>
                <pre>{trace.content}</pre>
              </details>
            ))}
          </div>
        )}
        {(message.elapsedMs !== undefined || totalTokens !== undefined) && (
          <div className="usage">
            {message.elapsedMs !== undefined && message.elapsedMs !== null ? `${message.elapsedMs} ms` : ""}
            {message.elapsedMs !== undefined && totalTokens !== undefined ? " | " : ""}
            {totalTokens !== undefined ? `tokens=${String(totalTokens)}` : ""}
          </div>
        )}
        {canSendFeedback && (
          <div className="feedback-actions" aria-label="回答反馈">
            <button
              className={message.feedbackRating === "up" ? "selected" : ""}
              disabled={message.feedbackPending}
              onClick={() => onFeedback(message, "up")}
              title="有帮助"
              type="button"
            >
              <ThumbsUp size={15} />
            </button>
            <button
              className={message.feedbackRating === "down" ? "selected" : ""}
              disabled={message.feedbackPending}
              onClick={() => onFeedback(message, "down")}
              title="没帮助"
              type="button"
            >
              <ThumbsDown size={15} />
            </button>
          </div>
        )}
      </div>
    </article>
  );
}

export default MessageBubble;
