import { FormEvent, useEffect, useRef, useState } from "react";

import { checkHealth, createThread, loadConfig, streamChat } from "./api";
import ChatPanel from "./components/ChatPanel";
import Sidebar from "./components/Sidebar";
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
      <Sidebar
        apiStatus={apiStatus}
        config={config}
        pending={pending}
        threadId={threadId}
        onResetThread={resetThread}
      />
      <ChatPanel
        input={input}
        messages={messages}
        messagesEndRef={messagesEndRef}
        pending={pending}
        onClear={clearMessages}
        onInputChange={setInput}
        onSubmit={submitMessage}
      />
    </main>
  );
}

export default App;
