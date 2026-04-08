# 项目路线图

相关文档:

- 项目现状: [project-status.md](project-status.md)
- 架构说明: [architecture.md](architecture.md)
- 执行清单: [todo.md](todo.md)

## 长期目标

长期目标不是做一个“能回答问题”的 demo，而是做成一个可持续迭代的垂直知识助手底座。

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

### 目标三: 面向垂直场景的产品雏形

结合当前知识库内容，更适合演进成下面这些方向:

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
    chat_service.py
    rag_service.py
    ingest_service.py
  api/
    schemas.py
    routes_chat.py
    routes_ingest.py
    routes_health.py
  eval/
    dataset.py
    retrieval_eval.py
    answer_eval.py
    traces.py
```

架构原则:

- `agent/` 只负责模型、工具、prompt、state
- `retrieval/` 只负责入库、召回、重排、格式化
- `tools/` 负责暴露 agent 可调用能力
- `services/` 负责业务编排
- `eval/` 负责质量验证

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

当 P0 和 P1 完成后，再进入中期建设。

建议方向:

- 增加 API 服务层
- 会话状态持久化，替换 `InMemorySaver`
- 文档管理能力: 增量入库、删除、重建索引
- 反馈闭环: 用户标记有帮助 / 无帮助
- 后台监控: 请求量、命中率、失败率、token 使用

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
