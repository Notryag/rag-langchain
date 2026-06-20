import { FormEvent, useEffect, useRef, useState } from "react";

import {
  cancelChatRun,
  checkHealth,
  createKnowledgeBase,
  deleteDocument,
  deleteKnowledgeBase,
  getChatRun,
  listDocuments,
  listChatMessages,
  listChatSessions,
  listKnowledgeBases,
  loadConfig,
  loadMe,
  processDocument,
  previewRetrieval,
  streamChat,
  updateKnowledgeBase,
  uploadDocument,
} from "./api";
import AuthPanel from "./components/AuthPanel";
import ChatPanel from "./components/ChatPanel";
import DocumentPanel from "./components/DocumentPanel";
import KbManager from "./components/KbManager";
import Sidebar from "./components/Sidebar";
import type {
  ChatMessage,
  ChatSession,
  Citation,
  FeedbackRating,
  KnowledgeDocument,
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
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
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
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void boot();
  }, []);

  useEffect(() => {
    if (!apiToken) return;
    void loadWorkspace(apiToken);
  }, [apiToken]);

  useEffect(() => {
    if (!apiToken || !activeKbId) {
      setDocuments([]);
      setChatSessions([]);
      return;
    }
    void refreshDocuments();
    void refreshChatSessions();
  }, [apiToken, activeKbId]);

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
      setActiveKbId((current) => (current && kbs.some((kb) => kb.id === current) ? current : kbs[0]?.id || null));
    } catch (error) {
      localStorage.removeItem(tokenStorageKey);
      setApiToken("");
      setCurrentUser(null);
      setKnowledgeBases([]);
      setDocuments([]);
      setChatSessions([]);
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
    setDocuments([]);
    setChatSessions([]);
    setActiveKbId(null);
    setSessionId(undefined);
    setMessages([welcomeMessage]);
  }

  async function resetThread() {
    setPending(true);
    setActiveRunId(null);
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
      setChatSessions([]);
      setMessages([welcomeMessage]);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "创建知识库失败");
    } finally {
      setWorkspacePending(false);
    }
  }

  async function createKb(payload: { name: string; description?: string }) {
    if (!apiToken) return;
    const kb = await createKnowledgeBase(apiToken, payload);
    setKnowledgeBases((current) => [kb, ...current]);
    setActiveKbId(kb.id);
    setSessionId(undefined);
    setChatSessions([]);
    setMessages([welcomeMessage]);
  }

  async function updateKb(kb: KnowledgeBase, payload: { name: string; description?: string }) {
    if (!apiToken) return;
    const updated = await updateKnowledgeBase(apiToken, kb.id, payload);
    setKnowledgeBases((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function deleteKb(kb: KnowledgeBase) {
    if (!apiToken) return;
    await deleteKnowledgeBase(apiToken, kb.id);
    setKnowledgeBases((current) => {
      const next = current.filter((item) => item.id !== kb.id);
      setActiveKbId(next[0]?.id || null);
      return next;
    });
    setDocuments([]);
    setChatSessions([]);
    setSessionId(undefined);
    setMessages([welcomeMessage]);
  }

  async function refreshDocuments() {
    if (!apiToken || !activeKbId) return;
    setWorkspaceError("");
    try {
      setDocuments(await listDocuments(apiToken, activeKbId));
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "加载文档失败");
    }
  }

  async function refreshChatSessions() {
    if (!apiToken || !activeKbId) return;
    try {
      const sessions = await listChatSessions(apiToken);
      setChatSessions(sessions.filter((item) => item.kb_id === activeKbId));
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "加载会话失败");
    }
  }

  async function loadSessionMessages(targetSession: ChatSession) {
    if (!apiToken || pending) return;
    setWorkspacePending(true);
    setWorkspaceError("");
    try {
      const storedMessages = await listChatMessages(apiToken, targetSession.id);
      setSessionId(targetSession.id);
      setMessages(storedMessages.length ? storedMessages.map(toChatMessage) : [welcomeMessage]);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "加载会话消息失败");
    } finally {
      setWorkspacePending(false);
    }
  }

  async function uploadActiveDocument(file: File) {
    if (!apiToken || !activeKbId) return;
    setWorkspacePending(true);
    try {
      const document = await uploadDocument(apiToken, activeKbId, file);
      setDocuments((current) => [document, ...current]);
    } finally {
      setWorkspacePending(false);
    }
  }

  async function processActiveDocument(document: KnowledgeDocument) {
    if (!apiToken) return;
    setWorkspacePending(true);
    try {
      const response = await processDocument(apiToken, document.id);
      setDocuments((current) => current.map((item) => (item.id === document.id ? response.document : item)));
    } finally {
      setWorkspacePending(false);
    }
  }

  async function deleteActiveDocument(document: KnowledgeDocument) {
    if (!apiToken) return;
    setWorkspacePending(true);
    try {
      await deleteDocument(apiToken, document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
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
    let completedRunId: number | null = null;

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
          }, (runId) => {
            completedRunId = runId;
          });
        },
      });
      if (completedRunId !== null) {
        await enrichAssistantWithRun(assistantId, completedRunId);
      }
      await refreshChatSessions();
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
      setActiveRunId(null);
    }
  }

  async function previewActiveRetrieval() {
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
      return;
    }

    setPending(true);
    setInput("");
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: text }]);
    try {
      const result = await previewRetrieval({
        kbId: activeKbId,
        question: text,
        retrievalProfile,
        token: apiToken,
      });
      const citations: Citation[] = result.chunks.map((chunk) => ({
        rank: chunk.rank || undefined,
        document_id: typeof chunk.document_id === "number" ? chunk.document_id : undefined,
        filename: chunk.filename,
        chunk_id: typeof chunk.chunk_id === "number" ? chunk.chunk_id : undefined,
        chunk_index: chunk.chunk_index,
        page: chunk.page,
        score: chunk.score || undefined,
        content: chunk.content,
      }));
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: result.chunks.length
            ? `检索命中 ${result.chunks.length} 个片段，未调用 AI。`
            : "没有检索到相关片段，未调用 AI。",
          citations,
          retrievalProfile: retrievalProfile ? { ...retrievalProfile } : undefined,
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `检索失败：${error instanceof Error ? error.message : "未知错误"}`,
          error: true,
        },
      ]);
    } finally {
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
    setCompletedRunId: (runId: number) => void,
  ) {
    if (eventData.eventName === "metadata") {
      setSessionId(eventData.data.session_id);
      setActiveRunId(eventData.data.run_id);
      updateAssistant(assistantId, { runId: eventData.data.run_id });
      return;
    }

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
          citations: eventData.data.citations || [],
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
      setCompletedRunId(eventData.data.run_id);
      updateAssistant(assistantId, {
        content: eventData.data.answer,
        runId: eventData.data.run_id,
        citations: eventData.data.references,
        toolTraces: [...toolTraces],
        usage: eventData.data.usage,
        tokenCost: eventData.data.token_cost,
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

  async function enrichAssistantWithRun(assistantId: string, runId: number) {
    if (!apiToken) return;
    try {
      const run = await getChatRun(apiToken, runId);
      updateAssistant(assistantId, {
        usage: run.usage,
        tokenCost: run.token_cost,
        traceUrl: run.trace_url,
      });
    } catch {
      // Run enrichment is helpful but not required for the chat answer itself.
    }
  }

  async function handleFeedback(message: ChatMessage, rating: FeedbackRating) {
    if (message.feedbackPending || message.role !== "assistant" || message.id === "welcome") return;

    updateAssistant(message.id, { feedbackRating: rating, feedbackPending: false });
  }

  async function cancelActiveRun() {
    if (!apiToken || activeRunId === null) return;
    const runId = activeRunId;
    setPending(false);
    setActiveRunId(null);
    setMessages((current) =>
      current.map((message) =>
        message.runId === runId
          ? {
              ...message,
              content: message.content && message.content !== "正在生成..." ? message.content : "已请求取消当前回答。",
              statusLines: [...(message.statusLines || []), "已请求取消 run"],
            }
          : message,
      ),
    );
    try {
      await cancelChatRun(apiToken, runId);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "取消 run 失败");
    }
  }

  const activeKb = knowledgeBases.find((kb) => kb.id === activeKbId) || null;

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
        chatSessions={chatSessions}
        onSessionSelect={loadSessionMessages}
      />
      <ChatPanel
        header={
          <>
            <KbManager
              activeKb={activeKb}
              pending={workspacePending}
              onCreate={createKb}
              onDelete={deleteKb}
              onUpdate={updateKb}
            />
            {activeKb && (
              <DocumentPanel
                documents={documents}
                pending={workspacePending}
                onDelete={deleteActiveDocument}
                onProcess={processActiveDocument}
                onRefresh={refreshDocuments}
                onUpload={uploadActiveDocument}
              />
            )}
          </>
        }
        input={input}
        messages={messages}
        messagesEndRef={messagesEndRef}
        pending={pending}
        activeRunId={activeRunId}
        onClear={clearMessages}
        onCancelRun={cancelActiveRun}
        onFeedback={handleFeedback}
        onInputChange={setInput}
        onPreviewRetrieval={previewActiveRetrieval}
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

function toChatMessage(message: {
  id: number;
  role: "assistant" | "user" | "system";
  content: string;
  references: Citation[];
}): ChatMessage {
  return {
    id: `stored-${message.id}`,
    role: message.role === "assistant" ? "assistant" : "user",
    content: message.content,
    citations: message.references,
  };
}

export default App;
