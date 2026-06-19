import { ChangeEvent, useRef, useState } from "react";
import { FileUp, Play, RefreshCw, Trash2 } from "lucide-react";

import type { KnowledgeDocument } from "../types";

type DocumentPanelProps = {
  documents: KnowledgeDocument[];
  pending: boolean;
  onDelete: (document: KnowledgeDocument) => Promise<void>;
  onProcess: (document: KnowledgeDocument) => Promise<void>;
  onRefresh: () => Promise<void>;
  onUpload: (file: File) => Promise<void>;
};

const statusLabels: Record<KnowledgeDocument["status"], string> = {
  pending: "pending",
  processing: "processing",
  completed: "completed",
  failed: "failed",
};

function DocumentPanel({ documents, pending, onDelete, onProcess, onRefresh, onUpload }: DocumentPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [error, setError] = useState("");

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError("");
    try {
      await onUpload(file);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    }
  }

  async function deleteDoc(document: KnowledgeDocument) {
    const confirmed = window.confirm(`确认删除文档“${document.filename}”？`);
    if (!confirmed) return;
    setError("");
    try {
      await onDelete(document);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
  }

  async function processDoc(document: KnowledgeDocument) {
    setError("");
    try {
      await onProcess(document);
    } catch (err) {
      setError(err instanceof Error ? err.message : "处理失败");
    }
  }

  return (
    <section className="workspace-panel documents-panel">
      <div className="workspace-head">
        <div>
          <p className="eyebrow">Documents</p>
          <h2>文档</h2>
        </div>
        <div className="toolbar-actions">
          <button className="icon-light-button" onClick={onRefresh} disabled={pending} title="刷新">
            <RefreshCw size={16} />
          </button>
          <button className="secondary-button" onClick={() => fileInputRef.current?.click()} disabled={pending}>
            <FileUp size={16} />
            上传
          </button>
          <input ref={fileInputRef} type="file" hidden onChange={upload} />
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}

      {documents.length ? (
        <div className="document-list">
          {documents.map((document) => (
            <article className="document-row" key={document.id}>
              <div className="document-main">
                <strong>{document.filename}</strong>
                <span>{document.content_type || "unknown"} · {formatDate(document.updated_at)}</span>
                {document.error_message && <span className="document-error">{document.error_message}</span>}
              </div>
              <span className={`status-badge status-${document.status}`}>{statusLabels[document.status]}</span>
              <div className="row-actions">
                <button
                  className="icon-light-button"
                  onClick={() => processDoc(document)}
                  disabled={pending || document.status === "processing"}
                  title="处理"
                >
                  <Play size={15} />
                </button>
                <button
                  className="icon-light-button danger"
                  onClick={() => deleteDoc(document)}
                  disabled={pending}
                  title="删除"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="workspace-description">当前知识库还没有文档。</p>
      )}
    </section>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default DocumentPanel;
