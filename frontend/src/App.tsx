import { FormEvent, useEffect, useRef, useState } from "react";

import { checkHealth, loadConfig, streamChat } from "./api";
import ChatPanel from "./components/ChatPanel";
import Sidebar from "./components/Sidebar";
import type { ChatMessage, Citation, FeedbackRating, PublicConfig, RetrievalProfile, StreamEvent, ToolTrace } from "./types";

const welcomeMessage: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content: "你好，我可以基于当前知识库回答选购、维护和故障排除问题。",
};

function App() {
  const apiToken = import.meta.env.VITE_API_TOKEN || "";
  const kbId = Number(import.meta.env.VITE_KB_ID || "0");
  const [sessionId, setSessionId] = useState<number | undefined>(undefined);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [defaultRetrievalProfile, setDefaultRetrievalProfile] = useState<RetrievalProfile | null>(null);
  const [retrievalProfile, setRetrievalProfile] = useState<RetrievalProfile | null>(null);
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
      const [newConfig, healthy] = await Promise.all([loadConfig(), checkHealth()]);
      const defaultProfile = configToProfile(newConfig);
      setConfig(newConfig);
      setDefaultRetrievalProfile(defaultProfile);
      setRetrievalProfile(defaultProfile);
      setApiStatus(healthy ? "可用" : "异常");
    } catch {
      setApiStatus("异常");
    }
  }

  async function resetThread() {
    setPending(true);
    try {
      setSessionId(undefined);
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
    if (!apiToken || !kbId) {
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "user", content: text },
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "请先通过 VITE_API_TOKEN 和 VITE_KB_ID 配置当前用户 token 与知识库 ID。",
          error: true,
        },
      ]);
      setInput("");
      return;
    }

    const assistantId = crypto.randomUUID();
    const activeProfile = retrievalProfile ? { ...retrievalProfile } : undefined;
    setInput("");
    setPending(true);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: text },
      { id: assistantId, role: "assistant", content: "正在生成...", question: text, retrievalProfile: activeProfile },
    ]);

    const statusLines: string[] = [];
    const citations: Citation[] = [];
    const toolTraces: ToolTrace[] = [];
    let answer = "";
    let failed = false;

    try {
      await streamChat({
        kbId,
        message: text,
        retrievalProfile: activeProfile,
        sessionId,
        token: apiToken,
        onEvent: (eventData) => {
          handleStreamEvent(eventData, assistantId, statusLines, citations, toolTraces, (nextAnswer) => {
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
    toolTraces: ToolTrace[],
    setAnswer: (answer: string) => void,
  ) {
    if (eventData.eventName === "answer" || eventData.eventName === "answer_delta") {
      const answer = eventData.data.answer || eventData.data.content || "";
      setAnswer(answer);
      updateAssistant(assistantId, { content: answer || "正在生成..." });
      return;
    }

    if (eventData.eventName === "tool_call" || eventData.eventName === "tool_result") {
      if (eventData.data.status_line) statusLines.push(eventData.data.status_line);
      if (eventData.data.citations?.length) citations.push(...eventData.data.citations);
      if (eventData.eventName === "tool_result" && eventData.data.content) {
        toolTraces.push({
          toolName: eventData.data.tool_name,
          statusLine: eventData.data.status_line,
          content: eventData.data.content,
        });
      }
      updateAssistant(assistantId, {
        statusLines: [...statusLines],
        citations: [...citations],
        toolTraces: [...toolTraces],
      });
      return;
    }

    if (eventData.eventName === "complete") {
      setSessionId(eventData.data.session_id);
      setAnswer(eventData.data.answer);
      updateAssistant(assistantId, {
        content: eventData.data.answer,
        citations: eventData.data.references,
        toolTraces: [...toolTraces],
        usage: eventData.data.usage,
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

  async function handleFeedback(message: ChatMessage, rating: FeedbackRating) {
    if (message.feedbackPending || message.role !== "assistant" || message.id === "welcome") return;

    updateAssistant(message.id, { feedbackRating: rating, feedbackPending: false });
  }

  return (
    <main className="app-shell">
      <Sidebar
        apiStatus={apiStatus}
        config={config}
        defaultRetrievalProfile={defaultRetrievalProfile}
        pending={pending}
        retrievalProfile={retrievalProfile}
        threadId={sessionId ? String(sessionId) : "-"}
        onRetrievalProfileChange={setRetrievalProfile}
        onResetThread={resetThread}
      />
      <ChatPanel
        input={input}
        messages={messages}
        messagesEndRef={messagesEndRef}
        pending={pending}
        onClear={clearMessages}
        onFeedback={handleFeedback}
        onInputChange={setInput}
        onSubmit={submitMessage}
      />
    </main>
  );
}

function configToProfile(config: PublicConfig): RetrievalProfile {
  return {
    search_type: config.retrieval_search_type as RetrievalProfile["search_type"],
    top_k: config.top_k,
    fetch_k: config.retrieval_fetch_k,
    reranker_enabled: config.reranker_enabled,
    max_context_chars: config.retrieval_max_context_chars,
  };
}

export default App;
