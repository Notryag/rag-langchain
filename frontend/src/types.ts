export type Citation = {
  rank?: number;
  source?: string;
  page?: string | null;
  chunk_index?: number | null;
  label?: string;
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
  collection_name: string;
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
};

export type ChatResponse = {
  thread_id: string;
  answer: string;
  status_lines: string[];
  citations: Citation[];
  usage: Record<string, unknown> | null;
  elapsed_ms: number | null;
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
      eventName: "error";
      data: { message?: string };
    };
