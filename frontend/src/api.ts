import type { PublicConfig, StreamEvent } from "./types";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(path: string) {
  return `${apiBaseUrl}${path}`;
}

async function postJson(url: string, body: unknown = {}) {
  const response = await fetch(apiUrl(url), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return response;
}

export async function checkHealth() {
  const response = await fetch(apiUrl("/api/health"));
  return response.ok;
}

export async function loadConfig(): Promise<PublicConfig> {
  const response = await fetch(apiUrl("/api/config"));
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export async function createThread(): Promise<string> {
  const response = await postJson("/api/threads");
  const payload = await response.json();
  return payload.thread_id;
}

export async function streamChat({
  message,
  threadId,
  onEvent,
}: {
  message: string;
  threadId: string;
  onEvent: (event: StreamEvent) => void;
}) {
  const response = await postJson("/api/chat/stream", {
    message,
    thread_id: threadId,
  });

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
