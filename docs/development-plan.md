# 项目发展计划

## 定位

项目不再以通用 RAG demo 为目标。下一阶段定位为面向售后支持、产品说明书和故障排查场景的多租户 RAG 质量运营系统。

核心差异化不是增加更多 Agent 或向量数据库，而是让知识入库、检索、回答、反馈和评测形成可追踪、可复现的闭环。

## 当前基础

已经具备的工程优势:

- `/api/v1 + Runtime + Agent + PostgreSQL/pgvector` 单一主线
- SQL 层 `user_id + kb_id` 多租户隔离
- JWT、最小 RBAC、知识库和文档管理
- Celery 异步入库、SSE、取消和结构化引用
- retrieval eval、answer eval、baseline 和 bad case 基础设施
- 后端单元测试、前端和容器 CI

## 发展优先级

### P0: 正确性与可复现性

- [x] 统一 `RetrievalProfile` 与 pgvector 执行层的 MMR 能力
- [x] 让本地测试命令不依赖手工准备生产环境变量
- [ ] 保存真实数据 baseline manifest、answer runs 和 bad cases
- [ ] 修正文档状态，避免路线图与实际能力不一致
- [x] 增加前端 API 与 SSE 核心流程测试

完成标准:

- 所有公开检索配置都有测试覆盖，并且不会运行时报“不支持”
- baseline 结果能够按代码提交和检索配置比较
- 后端测试与前端测试可以由一条明确命令重复执行

### P1: 可扩展检索

- [ ] 使用 PostgreSQL Full Text Search 和 GIN 索引替代 Python 全量 lexical 扫描
- [ ] 保留向量召回和全文召回的 SQL 租户过滤，并使用 RRF 融合
- [ ] 引入可插拔 cross-encoder reranker，支持批处理、超时和降级
- [ ] 建立 1 万和 10 万 chunks 的 p50/p95 延迟基准

完成标准:

- hybrid 查询不随知识库 chunks 数量做 Python O(N) 扫描
- benchmark 同时记录召回质量、延迟、模型调用次数和估算成本

### P2: 可靠入库与运行态

- [ ] 为入库任务增加 attempt、heartbeat、locked_until 和失效任务回收
- [ ] 增加内容 hash、重复检测、文档版本和增量重建
- [ ] 将 active run、取消信号和运行指标迁移到 Redis、数据库或标准监控系统
- [ ] 增加任务列表、失败原因、重试和查询 trace 管理界面

完成标准:

- worker 在任意处理阶段退出后，文档不会永久停留在 processing
- 多 API 实例下可以查询和取消任意实例创建的 run

### P3: 售后知识质量运营

- [ ] 支持扫描 PDF OCR、表格和图片内容提取
- [ ] 将用户反馈关联到 run、answer 和引用 chunks
- [ ] 支持从负反馈审核并生成固定评测样本
- [ ] 提供检索解释: dense/lexical 排名、RRF 分数和 rerank 前后变化
- [ ] 增加知识过期检测、文档版本差异和引用审计

完成标准:

- 一条负反馈可以经过审核进入评测集，并在后续 baseline 中持续回归
- 运营人员能够判断错误来自解析、召回、重排还是回答生成

### P4: 开源项目成熟度

- [ ] 确认开源许可证并增加 LICENSE
- [ ] 增加 CONTRIBUTING、Issue/PR 模板和 changelog
- [ ] 提供带种子数据的一键演示、界面截图和公开 benchmark
- [ ] 按可验证里程碑发布版本，而不是只累积 master 提交

## 当前里程碑

当前执行 **RAG Quality Operations v1**:

1. 修复检索配置正确性并建立可复现 baseline。
2. 将 hybrid lexical 召回迁移到 PostgreSQL FTS。
3. 接入真实 reranker，并保留超时降级。
4. 把反馈、bad case 和评测集串成可操作闭环。

暂不优先投入多向量库、复杂长期 memory、subagent 或 tool marketplace，直到质量闭环和任务可靠性达到上述完成标准。
