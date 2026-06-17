# 项目路线图

相关文档:

- 项目现状: [project-status.md](project-status.md)
- 架构说明: [architecture.md](architecture.md)
- 多租户企业知识库 RAG 规划: [multitenant-rag.md](multitenant-rag.md)
- 入库策略: [ingestion.md](ingestion.md)
- Hybrid Search 需求评估: [hybrid-search-evaluation.md](hybrid-search-evaluation.md)
- 执行清单: [todo.md](todo.md)
- 已完成清单归档: [todo-done.md](todo-done.md)

## 长期目标

长期目标不是做一个“能回答问题”的 demo，而是演进为一个多租户企业知识库 RAG 系统。

新的产品化目标详见 [multitenant-rag.md](multitenant-rag.md)。当前路线图保留质量闭环和检索迭代要求，但后续工程建设会优先围绕用户、知识库、文档、pgvector、聊天记录和权限隔离展开。

### 目标一: 可验证的 RAG 系统

需要满足:

- 检索优化可以量化评估
- 回答质量可以独立评估
- bad case 可以被追踪和回流
- 引用与拒答策略可以被验证

为了达到这一点，需要逐步补齐:

- 评测集
- retrieval eval
- answer eval
- tracing 与可观测能力

### 目标二: 可扩展的工程底座

需要满足:

- CLI、Web、未来 API 共用同一业务编排层
- retrieval、tool、agent、memory 边界清晰
- 模型、向量库、重排器可以逐步替换
- 配置、日志、运行入口更规范

### 目标三: 面向企业知识库的产品雏形

结合当前知识库内容和后端能力，更适合演进成下面这些方向:

- 多用户企业知识库
- 产品说明书问答
- 售后支持问答
- 故障排查助手
- FAQ 与知识运营后台

长期看，系统应具备这些特征:

- 回答基于事实
- 引用来源清晰
- 无法回答时稳定拒答
- 支持持续导入和维护知识库

## 架构演进方向

建议逐步演进到下面这类结构，但不要求一次性全部实现:

```text
app/
  agent/
    create_agent.py
    prompts.py
    middleware.py
    state.py
  retrieval/
    ingest.py
    loaders.py
    splitter.py
    embeddings.py
    vectorstore.py
    retriever.py
    reranker.py
    formatter.py
    citations.py
  tools/
    retrieve_context.py
    health.py
  memory/
    checkpointer.py
    thread_store.py
  services/
    rag_service.py
    ingest_service.py
  api/
    schemas.py
    routes_chat.py
    routes_ingest.py
    routes_health.py
evaluation/
    dataset.py
    evaluate_retrieval.py
    generate_answers.py
    evaluate_answers.py
    capture_trace.py
```

架构原则:

- `agent/` 只负责模型、工具、prompt、state
- `retrieval/` 只负责入库、召回、重排、格式化
- `tools/` 负责暴露 agent 可调用能力
- `services/` 负责业务编排
- `evaluation/` 负责质量验证

## 短期计划

### P0: 建立质量闭环

这是当前最高优先级。

计划内容:

- 建立一份小型评测集，覆盖事实问答、步骤问答、拒答场景
- 区分 retrieval eval 与 answer eval
- 沉淀 bad case 样本
- 给每轮优化建立可对比基线

预期结果:

- 知道当前系统哪些问题答得好
- 知道哪些问题召回不准
- 后续引入 reranker 或 hybrid search 时有客观依据

### P1: 收紧工程边界

计划内容:

- 抽出 `rag_service`，统一 CLI、Streamlit、后续 API 调用入口
- 让 middleware 真正接入主流程
- 整理 `settings` 与配置校验
- 缓存 embeddings / vector store 实例，减少重复初始化
- 统一项目入口，避免旁路调用和重复逻辑

预期结果:

- 主流程更稳定
- 模块职责更清晰
- 后续改动成本下降

### P2: 升级检索能力

计划内容:

- 加入 reranker
- 支持 metadata 过滤
- 优化 chunk 策略与上下文压缩
- 增强 citation 与 artifact 输出

预期结果:

- 召回质量更高
- 上下文更干净
- 回答更稳定，引用更可信

## 中期计划

当前 P0/P1/P2 的本地 RAG 能力已经基本具备，下一阶段进入多租户产品化建设。

建议方向:

- 数据库地基: SQLAlchemy / Alembic / PostgreSQL / pgvector
- 用户认证: 注册、登录、JWT、当前用户依赖
- 知识库 CRUD: 所有数据按当前用户隔离
- 文档管理: 上传、状态追踪、解析、切片、向量化
- 问答: 基于 `user_id + kb_id` 的权限过滤检索、引用返回、聊天记录保存
- 异步处理: Celery + Redis 处理文档任务

## 当前不建议优先做的事

以下事情短期内不建议排在前面:

- 一次性把理想目录全部实现
- 同时支持过多向量库
- 过早接入复杂 memory 体系
- 一口气增加很多 tool
- 在没有评测前反复调 prompt

这些不是不做，而是不应该排在质量闭环之前。

## 里程碑建议

### 里程碑 1: 最小可评估

完成标准:

- 有基础评测集
- 能跑 retrieval eval
- 能跑 answer eval
- 至少有一组 bad case 样本

### 里程碑 2: 最小可维护

完成标准:

- 有 service 层编排
- 有更清晰的模块边界
- 会话状态不再只依赖内存
- 配置和日志更规范

### 里程碑 3: 最小可产品化

完成标准:

- 有 API
- 有知识库维护能力
- 有稳定的引用展示和拒答策略
- 有基础运营与质量反馈闭环

## 总结

推进顺序建议保持为:

1. 先做质量闭环
2. 再做工程边界
3. 再升级检索能力
4. 最后进入产品化建设

这个顺序最稳，也最符合当前项目阶段。
