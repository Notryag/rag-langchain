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
  elapsedMs?: number | null;
  feedbackRating?: FeedbackRating;
  feedbackPending?: boolean;
  error?: boolean;
};

export type StreamEvent =
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
