import type { ChatMessage } from "../types";

function MessageBubble({ message }: { message: ChatMessage }) {
  const totalTokens = message.usage?.total_tokens;
  const profile = message.retrievalProfile;
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
      </div>
    </article>
  );
}

export default MessageBubble;
