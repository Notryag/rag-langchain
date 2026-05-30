import { Bot, PanelLeft, Plus } from "lucide-react";
import { useMemo } from "react";

import type { PublicConfig } from "../types";

type SidebarProps = {
  apiStatus: string;
  config: PublicConfig | null;
  pending: boolean;
  threadId: string;
  onResetThread: () => void;
};

function Sidebar({ apiStatus, config, pending, threadId, onResetThread }: SidebarProps) {
  const configRows = useMemo(() => {
    if (!config) return [["模型", "-"]];
    return [
      ["模型", config.chat_model],
      ["Embedding", config.embedding_model],
      ["集合", config.collection_name],
      ["检索", config.retrieval_search_type],
      ["Top K", String(config.top_k)],
      ["Fetch K", String(config.retrieval_fetch_k)],
      ["Reranker", config.reranker_enabled ? "on" : "off"],
      ["Context", `${config.retrieval_max_context_chars} chars`],
    ];
  }, [config]);

  return (
    <aside className="sidebar" aria-label="控制台信息">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          <Bot size={24} />
        </span>
        <div>
          <h1>LangChain RAG</h1>
          <p>本地知识库问答</p>
        </div>
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>会话</h2>
          <button className="icon-button" onClick={onResetThread} disabled={pending} title="新建会话">
            <Plus size={18} />
          </button>
        </div>
        <dl className="meta-list">
          <MetaRow label="线程" value={threadId || "-"} />
          <MetaRow label="状态" value={apiStatus} tone={apiStatus === "可用" ? "ok" : "bad"} />
        </dl>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>检索配置</h2>
          <PanelLeft size={16} aria-hidden="true" />
        </div>
        <dl className="meta-list">
          {configRows.map(([label, value]) => (
            <MetaRow key={label} label={label} value={value} />
          ))}
        </dl>
      </section>
    </aside>
  );
}

function MetaRow({ label, value, tone }: { label: string; value: string; tone?: "ok" | "bad" }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={tone ? `tone-${tone}` : undefined}>{value}</dd>
    </div>
  );
}

export default Sidebar;
