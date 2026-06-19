import { RotateCcw, Send, Trash2 } from "lucide-react";
import type { FormEvent, ReactNode, RefObject } from "react";

import type { ChatMessage, FeedbackRating } from "../types";
import MessageBubble from "./MessageBubble";

type ChatPanelProps = {
  header?: ReactNode;
  input: string;
  messages: ChatMessage[];
  messagesEndRef: RefObject<HTMLDivElement | null>;
  pending: boolean;
  onClear: () => void;
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
  onClear,
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
        <button className="send-button" disabled={pending || !input.trim()} title="发送">
          {pending ? <RotateCcw size={20} className="spin" /> : <Send size={20} />}
        </button>
      </form>
    </section>
  );
}

export default ChatPanel;
