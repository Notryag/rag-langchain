import type { ChatMessage } from "../types";

function MessageBubble({ message }: { message: ChatMessage }) {
  const totalTokens = message.usage?.total_tokens;
  return (
    <article className={`message ${message.role}`}>
      <div className="avatar" aria-hidden="true">
        {message.role === "user" ? "你" : "AI"}
      </div>
      <div className={`bubble ${message.error ? "error" : ""}`}>
        <p>{message.content}</p>
        {!!message.statusLines?.length && <div className="status-lines">{message.statusLines.join(" | ")}</div>}
        {!!message.citations?.length && (
          <div className="citations">
            {message.citations.map((citation, index) => (
              <span className="citation" key={`${citation.label || citation.source}-${index}`}>
                {citation.label || citation.source || "引用"}
              </span>
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
