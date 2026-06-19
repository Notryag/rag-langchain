import { RotateCcw, Send, Square, Trash2 } from "lucide-react";
import type { FormEvent, ReactNode, RefObject } from "react";

import type { ChatMessage, FeedbackRating } from "../types";
import MessageBubble from "./MessageBubble";

type ChatPanelProps = {
  header?: ReactNode;
  input: string;
  messages: ChatMessage[];
  messagesEndRef: RefObject<HTMLDivElement | null>;
  pending: boolean;
  activeRunId: number | null;
  onClear: () => void;
  onCancelRun: () => void;
  onFeedback: (message: ChatMessage, rating: FeedbackRating) => void;
  onInputChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

function ChatPanel({
  header,
  input,
  messages,
  messagesEndRef,
  pending,
  activeRunId,
  onClear,
  onCancelRun,
  onFeedback,
  onInputChange,
  onSubmit,
}: ChatPanelProps) {
  return (
    <section className="chat-surface" aria-label="聊天">
      <header className="chat-header">
        <div>
          <p className="eyebrow">RAG Chat</p>
          <h2>扫地机器人知识助手</h2>
        </div>
        <button className="secondary-button" onClick={onClear} disabled={pending}>
          <Trash2 size={16} />
          清空
        </button>
      </header>

      {header && <div className="workspace-strip">{header}</div>}

      <div className="messages" aria-live="polite">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} onFeedback={onFeedback} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      <form className="composer" onSubmit={onSubmit}>
        <textarea
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
          rows={2}
          placeholder="输入问题，例如：扫地机器人连不上 WiFi 怎么办？"
          disabled={pending}
          required
        />
        <button
          className={`send-button ${pending && activeRunId !== null ? "cancel" : ""}`}
          disabled={pending ? activeRunId === null : !input.trim()}
          onClick={(event) => {
            if (pending && activeRunId !== null) {
              event.preventDefault();
              onCancelRun();
            }
          }}
          title={pending && activeRunId !== null ? "取消当前回答" : "发送"}
          type={pending && activeRunId !== null ? "button" : "submit"}
        >
          {pending && activeRunId === null ? (
            <RotateCcw size={20} className="spin" />
          ) : pending ? (
            <Square size={18} />
          ) : (
            <Send size={20} />
          )}
        </button>
      </form>
    </section>
  );
}

export default ChatPanel;
