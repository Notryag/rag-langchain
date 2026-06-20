import { MessageSquare, Plus } from "lucide-react";

import type { ChatSession } from "../types";

type SessionListProps = {
  activeSessionId?: number;
  disabled?: boolean;
  sessions: ChatSession[];
  onNewSession: () => void;
  onSelectSession: (session: ChatSession) => void;
};

function SessionList({ activeSessionId, disabled, sessions, onNewSession, onSelectSession }: SessionListProps) {
  return (
    <div className="session-list">
      <button className="session-new-button" disabled={disabled} onClick={onNewSession} type="button">
        <Plus size={16} />
        新会话
      </button>
      {sessions.length ? (
        <div className="session-items">
          {sessions.map((session) => (
            <button
              className={`session-item ${session.id === activeSessionId ? "active" : ""}`}
              disabled={disabled}
              key={session.id}
              onClick={() => onSelectSession(session)}
              title={session.title || `会话 ${session.id}`}
              type="button"
            >
              <MessageSquare size={15} />
              <span>{session.title || `会话 ${session.id}`}</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="panel-note">当前知识库还没有历史会话。</p>
      )}
    </div>
  );
}

export default SessionList;
