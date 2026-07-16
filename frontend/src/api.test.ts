import { afterEach, describe, expect, it, vi } from "vitest";

import { createKnowledgeBase, loadMe, loginUser, parseSse } from "./api";
import type { StreamEvent } from "./types";


afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API client", () => {
  it("adds bearer authentication and parses the response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({ id: 7, username: "owner", email: "owner@example.com", role: "user" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const user = await loadMe("secret-token");

    expect(user.id).toBe(7);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/me",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer secret-token" }),
      }),
    );
  });

  it("surfaces structured API errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ error: { message: "账号已停用" } }, { status: 403 })),
    );

    await expect(loginUser({ username_or_email: "owner", password: "invalid" })).rejects.toThrow("账号已停用");
  });

  it("serializes JSON mutations with authentication", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({ id: 3, user_id: 7, name: "Manuals", description: null }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createKnowledgeBase("secret-token", { name: "Manuals" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/kbs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: "Manuals" }),
        headers: expect.objectContaining({
          Authorization: "Bearer secret-token",
          "Content-Type": "application/json",
        }),
      }),
    );
  });
});

describe("SSE parser", () => {
  it("handles CRLF frames and preserves an incomplete event", () => {
    const events: StreamEvent[] = [];
    const firstChunk = [
      "event: metadata",
      'data: {"run_id":12,"session_id":4}',
      "",
      "event: answer_delta",
      'data: {"content":"你"}',
    ].join("\r\n");

    const rest = parseSse(firstChunk, (event) => events.push(event));

    expect(events).toEqual([{ eventName: "metadata", data: { run_id: 12, session_id: 4 } }]);
    expect(rest).toContain("event: answer_delta");

    const finalRest = parseSse(`${rest}\n\n`, (event) => events.push(event));
    expect(finalRest).toBe("");
    expect(events[1]).toEqual({ eventName: "answer_delta", data: { content: "你" } });
  });

  it("joins multiline data fields before decoding JSON", () => {
    const events: StreamEvent[] = [];

    parseSse('event: error\ndata: {"message":\ndata: "failed"}\n\n', (event) => events.push(event));

    expect(events).toEqual([{ eventName: "error", data: { message: "failed" } }]);
  });
});
