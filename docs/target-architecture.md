# 目标架构与收口计划

本文记录当前架构判断和下一阶段收口计划。核心结论: 项目没有致命总体设计缺陷，但已经出现两条 RAG 主链路并存的分叉风险，需要先收束主架构，再继续堆功能。

## 当前架构判断

项目现在有两条可工作的链路:

```text
旧本地 RAG 链路:
/api/chat, /api/chat/stream
  -> app/services/rag_service.py
  -> app/services/chat_client.py
  -> app/agent/ + app/tools/
  -> Chroma / app/retrieval/vectorstore.py

多租户产品链路:
/api/v1/*
  -> app/services/auth_service.py / kb_service.py / document_service.py / chat_service.py
  -> SQLAlchemy models
  -> PostgreSQL + pgvector
  -> Redis / Celery / operation logs / rate limit / cache
```

短期并存是合理的。旧链路保留了 Agent、Tool、Chroma、本地演示和已有评测基础；新链路承载企业知识库产品化能力。长期问题是，如果两条链路继续平级增长，检索、引用、流式、缓存、usage、评测都会重复实现，行为会越来越不一致。

## 主线决策

从现在开始，项目主线定义为:

```text
/api/v1 + PostgreSQL + pgvector + JWT + 多租户权限过滤
```

旧 `/api` 链路定位调整为:

- legacy demo
- 本地 RAG / Agent 实验场
- evaluation 基线
- 迁移期间的对照链路

它不应继续承载新的企业知识库能力。新增多租户产品能力优先进入 `/api/v1`、`app/services/`、`app/retrieval/pgvector_store.py` 及相关模型。

## 参考 DeerFlow 的取舍

DeerFlow 的设计重点是通用长任务 SuperAgent: gateway、runtime、skills、subagents、sandbox、memory、SSE、checkpointing。这个项目不是通用 Agent 平台，而是多租户企业知识库 RAG 后端，所以不应照搬完整 DeerFlow。

适合借鉴的思想:

- 明确 run / thread 生命周期，而不是只有一次 HTTP handler。
- 按能力分层，避免工具、运行时、业务状态混在一起。
- 渐进加载上下文和能力，避免所有模块互相知道。
- SSE、状态追踪、usage、日志都围绕一次 run 聚合。

暂不适合引入的东西:

- subagent 编排
- sandbox 文件系统
- 通用 skill marketplace
- 复杂长期 memory
- 大规模多工具自动规划

## 主要风险

### 1. 主链路分叉

症状:

- `/api/chat` 和 `/api/v1/kbs/{kb_id}/chat` 都能问答。
- 两者底层检索、引用、流式和记录方式不同。
- 新功能容易在其中一条链路实现，另一条链路遗漏。

收口方向:

- 文档上明确 `/api/v1` 是产品主链路。
- 旧链路停止新增企业能力。
- 抽统一 retrieval interface，让 Chroma 和 pgvector 都成为实现，而不是两套散落调用。

### 2. 检索抽象不统一

症状:

- 旧链路围绕 LangChain Document / Chroma / retriever。
- 新链路围绕 SQLAlchemy / pgvector / document_chunks。
- hybrid、rerank、metadata filter 的复用边界还不稳定。

收口方向:

- 定义稳定的 `RetrievedChunk` / `Retriever` 协议。
- pgvector 检索必须保留 `user_id + kb_id` SQL 权限过滤。
- evaluation 逐步覆盖 pgvector 多租户链路。

### 3. SSE 还不是 token 级真流式

当前 `/api/v1/kbs/{kb_id}/chat/stream` 是先完成回答，再按片段输出 SSE。它满足前端消费形态，但不是模型 token 级流式。

收口方向:

- 将流式生成下沉到 service 层。
- 保存聊天记录、references、usage、operation log 仍由一次 chat run 收尾。
- API 层只负责 SSE 序列化，不做业务编排。

### 4. 缺少 chat run 生命周期

当前聊天记录有 `chat_sessions` 和 `chat_messages`，但缺少一次问答运行的状态实体。

后续需要的 run 信息:

- status: `running / completed / failed / cancelled`
- user_id / kb_id / session_id
- question
- answer
- references
- usage
- cache_hit
- error_message
- started_at / completed_at

这会让 SSE 重连、失败追踪、取消、耗时统计和后续后台任务化更自然。

### 5. 项目状态文档滞后

`project-status.md` 和 `roadmap.md` 仍描述“多租户建设中”，但第二阶段后端增强已经基本完成。文档必须反映当前真实架构，否则后续 AI 助手会基于过时前提改代码。

## 下一阶段计划

### Batch 8: 架构收口文档

- [x] 新增本文，明确主链路、legacy 链路和设计风险。
- [x] 更新项目状态和路线图。
- [x] 更新 AI 助手入口导航。

### Batch 9: 统一检索接口

- [x] 定义多租户安全的 retrieval protocol / DTO。
- [x] 让 pgvector 检索返回统一结构。
- [x] 给旧 Chroma 检索加 adapter，保留为 legacy/eval 实现。
- [x] 更新 chat service 只依赖统一检索接口。
- [x] 补测试，确保 `user_id + kb_id` 过滤仍在 SQL 层发生。

### Batch 10: 真正的 chat run

- [x] 设计 `chat_runs` 表或等价 run model。
- [x] 同步 Alembic migration。
- [x] 同步记录 status、usage、cache_hit、error。
- [x] chat API / SSE 统一围绕 run 生命周期。

### Batch 11: token 级 SSE

- [x] 将模型 streaming 从 API 层下沉到 service。
- [x] SSE 输出 `answer_delta / complete / error`。
- [x] complete 事件保存最终 answer、references、usage。
- [x] 缓存命中时仍允许快速流式输出。

### Batch 12: pgvector 多租户评测

- [ ] 增加 pgvector retrieval eval 入口。
- [ ] 增加多租户权限隔离评测样本。
- [ ] 将 bad case 与 references 一起落盘。
- [ ] 后续再做 hybrid、rerank、上下文压缩。

## 当前不做

- 不引入 DeerFlow 式 subagent / skill / sandbox。
- 不做组织、团队、RBAC、ACL，除非 chat run 和主链路收口完成。
- 不同时引入新的向量库。
- 不在旧 `/api` 链路继续追加多租户企业能力。

## 成功标准

完成收口后，应满足:

- 新功能默认落在 `/api/v1` 产品主链路。
- 检索调用只有一个稳定接口，pgvector 是 primary implementation。
- 旧 Chroma/Agent 链路能继续演示和评测，但不会牵引产品设计。
- SSE、usage、operation log、cache 都围绕同一个 chat run 或等价抽象聚合。
- AI 助手可以通过 [ai-context.md](ai-context.md) 渐进读取文档，不需要一次性加载全仓库说明。
