export type Citation = {
  rank?: number;
  source?: string;
  document_id?: number;
  filename?: string;
  chunk_id?: number;
  page?: string | null;
  chunk_index?: number | null;
  content?: string;
  score?: number;
};

export type PublicConfig = {
  chat_model: string;
  embedding_model: string;
  top_k: number;
  retrieval_search_type: string;
  retrieval_fetch_k: number;
  reranker_enabled: boolean;
  reranker_strategy: string;
  retrieval_max_context_chars: number;
};

export type User = {
  id: number;
  username: string;
  email: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type KnowledgeBase = {
  id: number;
  user_id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentStatus = "pending" | "processing" | "completed" | "failed";

export type KnowledgeDocument = {
  id: number;
  kb_id: number;
  user_id: number;
  filename: string;
  content_type: string | null;
  file_path: string;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type SearchType = "similarity" | "mmr" | "hybrid";

export type RetrievalProfile = {
  search_type: SearchType;
  top_k: number;
  fetch_k: number;
  reranker_enabled: boolean;
  max_context_chars: number;
};

export type FeedbackRating = "up" | "down";

export type ToolTrace = {
  toolName?: string;
  statusLine?: string;
  content: string;
  citations?: Citation[];
};

export type ChatResponse = {
  answer: string;
  references: Citation[];
  session_id: number;
  run_id: number;
  cache_hit?: boolean;
  usage: Record<string, unknown> | null;
  token_cost?: Record<string, unknown> | null;
};

export type ChatSession = {
  id: number;
  user_id: number;
  kb_id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type StoredChatMessage = {
  id: number;
  session_id: number;
  role: "assistant" | "user" | "system";
  content: string;
  references: Citation[];
  created_at: string;
  updated_at: string;
};

export type ChatRun = {
  id: number;
  session_id: number;
  user_id: number;
  kb_id: number;
  prompt_version_id: number | null;
  status: "running" | "completed" | "failed" | "cancelled";
  question: string;
  answer: string | null;
  references: Citation[];
  usage: Record<string, unknown>;
  token_cost: Record<string, unknown>;
  trace_id: string | null;
  trace_url: string | null;
  cache_hit: boolean;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type RetrievalPreviewChunk = {
  rank: number | null;
  document_id: number | string | null;
  filename: string;
  chunk_id: number | string | null;
  chunk_index: number | null;
  page?: string | null;
  score?: number | null;
  content: string;
  metadata: Record<string, unknown>;
};

export type RetrievalPreviewResponse = {
  question: string;
  kb_id: number;
  chunks: RetrievalPreviewChunk[];
};

export type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
  question?: string;
  statusLines?: string[];
  citations?: Citation[];
  retrievalProfile?: RetrievalProfile;
  toolTraces?: ToolTrace[];
  usage?: Record<string, unknown> | null;
  tokenCost?: Record<string, unknown> | null;
  runId?: number | null;
  traceUrl?: string | null;
  elapsedMs?: number | null;
  feedbackRating?: FeedbackRating;
  feedbackPending?: boolean;
  error?: boolean;
};

export type StreamEvent =
  | {
      eventName: "metadata";
      data: {
        run_id: number;
        session_id: number;
        kb_id?: number;
      };
    }
  | {
      eventName: "answer";
      data: { content?: string; answer?: string };
    }
  | {
      eventName: "answer_delta";
      data: { content?: string; answer?: string };
    }
  | {
      eventName: "tool_call" | "tool_result";
      data: {
        status_line?: string;
        tool_name?: string;
        content?: string;
        citations?: Citation[];
      };
    }
  | {
      eventName: "complete";
      data: ChatResponse;
    }
  | {
      eventName: "end";
      data: Record<string, never>;
    }
  | {
      eventName: "error";
      data: { message?: string };
    };
