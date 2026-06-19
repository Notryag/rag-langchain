import type {
  KnowledgeBase,
  KnowledgeDocument,
  PublicConfig,
  RetrievalProfile,
  StreamEvent,
  TokenResponse,
  User,
} from "./types";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(path: string) {
  return `${apiBaseUrl}${path}`;
}

async function request(path: string, options: RequestInit = {}, token?: string) {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail || payload.error?.message || `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return response;
}

async function postJson(path: string, body: unknown = {}, token?: string) {
  return request(
    path,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    token,
  );
}

export async function checkHealth() {
  const response = await fetch(apiUrl("/api/v1/health"));
  return response.ok;
}

export async function loadConfig(): Promise<PublicConfig> {
  const response = await fetch(apiUrl("/api/v1/config"));
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export async function registerUser(payload: {
  username: string;
  email: string;
  password: string;
}): Promise<User> {
  const response = await postJson("/api/v1/auth/register", payload);
  return response.json();
}

export async function loginUser(payload: {
  username_or_email: string;
  password: string;
}): Promise<TokenResponse> {
  const response = await postJson("/api/v1/auth/login", payload);
  return response.json();
}

export async function loadMe(token: string): Promise<User> {
  const response = await request("/api/v1/auth/me", {}, token);
  return response.json();
}

export async function listKnowledgeBases(token: string): Promise<KnowledgeBase[]> {
  const response = await request("/api/v1/kbs", {}, token);
  return response.json();
}

export async function createKnowledgeBase(
  token: string,
  payload: { name: string; description?: string },
): Promise<KnowledgeBase> {
  const response = await postJson("/api/v1/kbs", payload, token);
  return response.json();
}

export async function listDocuments(token: string, kbId: number): Promise<KnowledgeDocument[]> {
  const response = await request(`/api/v1/kbs/${kbId}/documents`, {}, token);
  return response.json();
}

export async function streamChat({
  kbId,
  message,
  sessionId,
  token,
  onEvent,
}: {
  kbId: number;
  message: string;
  retrievalProfile?: RetrievalProfile;
  sessionId?: number;
  token: string;
  onEvent: (event: StreamEvent) => void;
}) {
  const response = await postJson(
    `/api/v1/kbs/${kbId}/chat/stream`,
    {
      question: message,
      session_id: sessionId,
    },
    token,
  );

  const reader = response.body?.getReader();
  if (!reader) throw new Error("当前浏览器不支持流式响应");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = parseSse(buffer, onEvent);
  }
}

function parseSse(buffer: string, onEvent: (event: StreamEvent) => void) {
  const chunks = buffer.split("\n\n");
  const rest = chunks.pop() || "";

  for (const chunk of chunks) {
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of chunk.split("\n")) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) continue;
    onEvent({
      eventName: eventName as StreamEvent["eventName"],
      data: JSON.parse(dataLines.join("\n")),
    } as StreamEvent);
  }

  return rest;
}
