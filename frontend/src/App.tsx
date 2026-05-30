import { Bot, PanelLeft, Plus, RotateCcw, Send, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { checkHealth, createThread, loadConfig, streamChat } from "./api";
import type { ChatMessage, Citation, PublicConfig, StreamEvent } from "./types";

const welcomeMessage: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content: "你好，我可以基于当前知识库回答选购、维护和故障排除问题。",
};

function App() {
  const [threadId, setThreadId] = useState("");
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [apiStatus, setApiStatus] = useState("连接中");
  const [messages, setMessages] = useState<ChatMessage[]>([welcomeMessage]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void boot();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  const configRows = useMemo(() => {
    if (!config) return [["模型", "-"]];
    return [
      ["模型", config.chat_model],
      ["Embedding", config.embedding_model],
      ["集合", config.collection_name],
      ["检索", config.retrieval_search_type],
      ["Top K", String(config.top_k)],
      ["Fetch K", String(config.retrieval_fetch_k)],
      ["Reranker", config.reranker_enabled ? "on" : "off"],
      ["Context", `${config.retrieval_max_context_chars} chars`],
    ];
  }, [config]);

  async function boot() {
    try {
      const [newThreadId, newConfig, healthy] = await Promise.all([
        createThread(),
        loadConfig(),
        checkHealth(),
      ]);
      setThreadId(newThreadId);
      setConfig(newConfig);
      setApiStatus(healthy ? "可用" : "异常");
    } catch {
      setApiStatus("异常");
    }
  }

  async function resetThread() {
    setPending(true);
    try {
      setThreadId(await createThread());
      setMessages([welcomeMessage]);
    } finally {
      setPending(false);
    }
  }

  function clearMessages() {
    setMessages([welcomeMessage]);
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || pending) return;

    const assistantId = crypto.randomUUID();
    setInput("");
    setPending(true);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: text },
      { id: assistantId, role: "assistant", content: "正在生成..." },
    ]);

    const statusLines: string[] = [];
    const citations: Citation[] = [];
    let answer = "";
    let failed = false;

    try {
      await streamChat({
        message: text,
        threadId,
        onEvent: (eventData) => {
          handleStreamEvent(eventData, assistantId, statusLines, citations, (nextAnswer) => {
            answer = nextAnswer;
          });
        },
      });
    } catch (error) {
      failed = true;
      updateAssistant(assistantId, {
        content: `请求失败：${error instanceof Error ? error.message : "未知错误"}`,
        error: true,
      });
    } finally {
      if (!answer && !failed) {
        updateAssistant(assistantId, { content: "没有收到回答。" });
      }
      setPending(false);
    }
  }

  function handleStreamEvent(
    eventData: StreamEvent,
    assistantId: string,
    statusLines: string[],
    citations: Citation[],
    setAnswer: (answer: string) => void,
  ) {
    if (eventData.eventName === "answer") {
      const answer = eventData.data.answer || eventData.data.content || "";
      setAnswer(answer);
      updateAssistant(assistantId, { content: answer || "正在生成..." });
      return;
    }

    if (eventData.eventName === "tool_call" || eventData.eventName === "tool_result") {
      if (eventData.data.status_line) statusLines.push(eventData.data.status_line);
      if (eventData.data.citations?.length) citations.push(...eventData.data.citations);
      updateAssistant(assistantId, { statusLines: [...statusLines], citations: [...citations] });
      return;
    }

    if (eventData.eventName === "complete") {
      setThreadId(eventData.data.thread_id || threadId);
      setAnswer(eventData.data.answer);
      updateAssistant(assistantId, {
        content: eventData.data.answer,
        statusLines: eventData.data.status_lines,
        citations: eventData.data.citations,
        usage: eventData.data.usage,
        elapsedMs: eventData.data.elapsed_ms,
      });
      return;
    }

    if (eventData.eventName === "error") {
      throw new Error(eventData.data.message || "请求失败");
    }
  }

  function updateAssistant(id: string, patch: Partial<ChatMessage>) {
    setMessages((current) =>
      current.map((message) => (message.id === id ? { ...message, ...patch } : message)),
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="控制台信息">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <Bot size={24} />
          </span>
          <div>
            <h1>LangChain RAG</h1>
            <p>本地知识库问答</p>
          </div>
        </div>

        <section className="panel">
          <div className="panel-head">
            <h2>会话</h2>
            <button className="icon-button" onClick={resetThread} disabled={pending} title="新建会话">
              <Plus size={18} />
            </button>
          </div>
          <dl className="meta-list">
            <MetaRow label="线程" value={threadId || "-"} />
            <MetaRow label="状态" value={apiStatus} tone={apiStatus === "可用" ? "ok" : "bad"} />
          </dl>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>检索配置</h2>
            <PanelLeft size={16} aria-hidden="true" />
          </div>
          <dl className="meta-list">
            {configRows.map(([label, value]) => (
              <MetaRow key={label} label={label} value={value} />
            ))}
          </dl>
        </section>
      </aside>

      <section className="chat-surface" aria-label="聊天">
        <header className="chat-header">
          <div>
            <p className="eyebrow">RAG Chat</p>
            <h2>扫地机器人知识助手</h2>
          </div>
          <button className="secondary-button" onClick={clearMessages} disabled={pending}>
            <Trash2 size={16} />
            清空
          </button>
        </header>

        <div className="messages" aria-live="polite">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          <div ref={messagesEndRef} />
        </div>

        <form className="composer" onSubmit={submitMessage}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
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
    </main>
  );
}

function MetaRow({ label, value, tone }: { label: string; value: string; tone?: "ok" | "bad" }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={tone ? `tone-${tone}` : undefined}>{value}</dd>
    </div>
  );
}

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

export default App;
