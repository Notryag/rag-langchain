import { FormEvent, useEffect, useRef, useState } from "react";

import { checkHealth, createKnowledgeBase, listKnowledgeBases, loadConfig, loadMe, streamChat } from "./api";
import AuthPanel from "./components/AuthPanel";
import ChatPanel from "./components/ChatPanel";
import Sidebar from "./components/Sidebar";
import type {
  ChatMessage,
  Citation,
  FeedbackRating,
  KnowledgeBase,
  PublicConfig,
  RetrievalProfile,
  StreamEvent,
  TokenResponse,
  ToolTrace,
  User,
} from "./types";

const welcomeMessage: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content: "你好，我可以基于当前知识库回答选购、维护和故障排除问题。",
};

const tokenStorageKey = "rag_access_token";

function App() {
  const [apiToken, setApiToken] = useState(() => localStorage.getItem(tokenStorageKey) || "");
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [activeKbId, setActiveKbId] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<number | undefined>(undefined);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [defaultRetrievalProfile, setDefaultRetrievalProfile] = useState<RetrievalProfile | null>(null);
  const [retrievalProfile, setRetrievalProfile] = useState<RetrievalProfile | null>(null);
  const [apiStatus, setApiStatus] = useState("连接中");
  const [workspaceError, setWorkspaceError] = useState("");
  const [workspacePending, setWorkspacePending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([welcomeMessage]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void boot();
  }, []);

  useEffect(() => {
    if (!apiToken) return;
    void loadWorkspace(apiToken);
  }, [apiToken]);

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

  async function loadWorkspace(token: string) {
    setWorkspacePending(true);
    setWorkspaceError("");
    try {
      const [user, kbs] = await Promise.all([loadMe(token), listKnowledgeBases(token)]);
      setCurrentUser(user);
      setKnowledgeBases(kbs);
      setActiveKbId((current) => current || kbs[0]?.id || null);
    } catch (error) {
      localStorage.removeItem(tokenStorageKey);
      setApiToken("");
      setCurrentUser(null);
      setKnowledgeBases([]);
      setActiveKbId(null);
      setWorkspaceError(error instanceof Error ? error.message : "加载用户信息失败");
    } finally {
      setWorkspacePending(false);
    }
  }

  function handleAuthenticated(tokenResponse: TokenResponse) {
    localStorage.setItem(tokenStorageKey, tokenResponse.access_token);
    setApiToken(tokenResponse.access_token);
    setCurrentUser(tokenResponse.user);
  }

  function logout() {
    localStorage.removeItem(tokenStorageKey);
    setApiToken("");
    setCurrentUser(null);
    setKnowledgeBases([]);
    setActiveKbId(null);
    setSessionId(undefined);
    setMessages([welcomeMessage]);
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

  async function createDefaultKb() {
    if (!apiToken || workspacePending) return;
    setWorkspacePending(true);
    setWorkspaceError("");
    try {
      const kb = await createKnowledgeBase(apiToken, {
        name: "默认知识库",
        description: "用于上传文档并开始问答",
      });
      setKnowledgeBases((current) => [kb, ...current]);
      setActiveKbId(kb.id);
      setSessionId(undefined);
      setMessages([welcomeMessage]);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "创建知识库失败");
    } finally {
      setWorkspacePending(false);
    }
  }

  function clearMessages() {
    setMessages([welcomeMessage]);
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || pending) return;
    if (!apiToken || !activeKbId) {
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "user", content: text },
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "请先登录并创建或选择一个知识库。",
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
        kbId: activeKbId,
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

  if (!apiToken || !currentUser) {
    return <AuthPanel apiStatus={apiStatus} onAuthenticated={handleAuthenticated} />;
  }

  return (
    <main className="app-shell">
      <Sidebar
        apiStatus={apiStatus}
        activeKbId={activeKbId}
        config={config}
        defaultRetrievalProfile={defaultRetrievalProfile}
        knowledgeBases={knowledgeBases}
        pending={pending}
        retrievalProfile={retrievalProfile}
        threadId={sessionId ? String(sessionId) : "-"}
        user={currentUser}
        workspaceError={workspaceError}
        workspacePending={workspacePending}
        onCreateKb={createDefaultKb}
        onLogout={logout}
        onKbChange={(kbId) => {
          setActiveKbId(kbId);
          setSessionId(undefined);
          setMessages([welcomeMessage]);
        }}
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
