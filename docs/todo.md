# 执行清单

本文件只保留仍需推进的事项。已完成内容归档到 [todo-done.md](todo-done.md)。

当前阶段重点:

1. 将 `/api/v1 + PostgreSQL + pgvector` 明确为多租户产品主链路
2. 保持权限隔离优先，避免跨用户检索泄露
3. 收口旧 Chroma/Agent 链路与新 pgvector 链路的边界
4. 在真实 PostgreSQL 数据上沉淀 retrieval / answer eval baseline

架构结论:

- 项目没有致命总体设计缺陷，核心风险是旧 `/api + Chroma + Agent` 与新 `/api/v1 + pgvector` 两条 RAG 链路继续平级增长。
- 参考 DeerFlow 时只借鉴 run/thread 生命周期、分层边界、渐进上下文和 SSE/run 聚合，不引入 subagent、sandbox、skill marketplace 等通用 Agent 平台复杂度。
- 架构收口主任务已经完成，接下来的实现顺序应围绕真实数据质量基线: pgvector retrieval eval -> pgvector answer eval -> bad case 回流 -> 默认检索策略决策。

总体规划见 [multitenant-rag.md](multitenant-rag.md)，架构收口计划见 [target-architecture.md](target-architecture.md)。

## Batch 1: 数据库与工程地基

- [x] 引入 SQLAlchemy / Alembic / PostgreSQL / pgvector / Redis / Celery 依赖
- [x] 增加数据库、Redis、Celery、JWT、上传目录配置
- [x] 增加 SQLAlchemy Base 和 session provider
- [x] 增加核心模型: users / knowledge_bases / documents / document_chunks / chat_sessions / chat_messages
- [x] 增加 Alembic 基础配置
- [x] 增加 Docker Compose 的 PostgreSQL + Redis
- [x] 增加模型层测试

## Batch 2: 用户认证

- [x] 增加密码哈希工具
- [x] 增加用户注册 service
- [x] 增加用户登录 service
- [x] 增加 JWT access token 生成与解析
- [x] 增加 `get_current_user` 鉴权依赖
- [x] 增加 `/api/v1/auth/register`
- [x] 增加 `/api/v1/auth/login`
- [x] 增加 `/api/v1/auth/me`
- [x] 增加认证测试

## Batch 3: 知识库 CRUD

- [x] 增加知识库 schema
- [x] 增加知识库 service
- [x] 增加 `/api/v1/kbs` CRUD 路由
- [x] 所有知识库查询限制当前用户
- [x] 增加知识库权限测试

## Batch 4: 文档上传与状态

- [x] 增加文档 schema
- [x] 增加上传文件保存逻辑
- [x] 上传后创建 document 记录
- [x] 支持 document 状态流转
- [x] 增加同步解析入口
- [x] 增加文档上传与状态测试

## Batch 5: pgvector 入库与检索

- [x] 将新文档切片写入 `document_chunks`
- [x] 将 embedding 写入 pgvector 字段
- [x] 检索时按 `user_id + kb_id` 过滤
- [x] 返回结构化 references
- [x] 增加权限过滤检索测试

## Batch 6: 多租户问答和聊天记录

- [x] 增加 `/api/v1/kbs/{kb_id}/chat`
- [x] 支持 chat_session 创建和复用
- [x] 保存用户消息
- [x] 保存助手消息和 references
- [x] 问答响应返回 answer / references / session_id
- [x] 增加聊天记录查询接口
- [x] 增加问答和聊天记录测试

## Batch 7: 异步文档处理

- [x] 增加 Celery app
- [x] 增加文档处理 task
- [x] 上传文档后投递异步任务
- [x] 任务失败时写入 `failed` 和 `error_message`
- [x] 增加任务幂等策略

## 当前不做

下面这些事情当前不建议优先推进:

- [ ] 组织 / 团队 / RBAC / ACL
- [ ] 同时支持很多向量库
- [ ] 复杂长期 memory
- [ ] 在权限过滤未稳定前做大规模检索优化
- [ ] 在多租户主链路没跑通前做复杂前端后台

## 建议执行顺序

1. [x] 增加 API 端到端 smoke test 脚本
2. [x] 在真实 PostgreSQL + Redis 环境跑通端到端上传、异步处理和问答
3. [x] 进入第二阶段增强: 限流、统一异常、操作日志、缓存和 SSE
4. [x] 进入架构收口: 统一检索接口、chat run 生命周期、token 级 SSE、pgvector 多租户评测
5. [ ] 建立真实数据质量基线: pgvector retrieval / answer eval baseline

## 下一阶段增强

- [x] 统一异常处理
- [x] 操作日志
- [x] 接口限流
- [x] Redis 缓存热点问题
- [x] SSE 流式问答
- [x] Docker Compose 增加 API / worker 服务
- [x] Token 用量统计

## Batch 8: 架构收口文档

- [x] 明确 `/api/v1 + pgvector` 是产品主链路
- [x] 明确旧 `/api + Chroma + Agent` 是 legacy demo / eval 基线
- [x] 记录参考 DeerFlow 后的取舍
- [x] 更新项目状态、路线图和 AI 助手导航

## Batch 9: 统一检索接口

- [x] 定义 retrieval protocol / DTO
- [x] 让 pgvector 检索返回统一结构
- [x] 给旧 Chroma 检索加 adapter
- [x] 更新 chat service 依赖统一检索接口
- [x] 补权限过滤和 adapter 测试

## Batch 10: Chat Run 生命周期

- [x] 设计 chat run model
- [x] 增加 Alembic migration
- [x] 记录 running / completed / failed / cancelled
- [x] 记录 usage / cache_hit / error_message
- [x] API 和 SSE 围绕 run 生命周期收口

## Batch 11: Token 级 SSE

- [x] 将模型 streaming 下沉到 service
- [x] SSE 输出 answer_delta / complete / error
- [x] complete 时保存最终 answer、references、usage
- [x] 缓存命中时保持快速流式输出

## Batch 12: pgvector 多租户评测

- [x] 增加 pgvector retrieval eval 入口
- [x] 增加权限隔离评测样本
- [x] 落盘 bad case、references 和检索参数
- [x] pgvector hybrid dense + lexical RRF 召回
- [x] 问答 prompt 上下文压缩
- [x] pgvector rerank 评测和 chat service 接入

## Batch 13: pgvector 回答评测闭环

- [x] 增加 pgvector answer 采样入口
- [x] 复用 answer eval 评分 pgvector runs
- [x] 导出 pgvector answer bad cases
- [x] 更新 project status / roadmap 到最新真实状态

## Batch 14: 真实数据质量基线

- [x] 增加 pgvector baseline runner
- [x] baseline runner 支持无模型配置时只跑 retrieval
- [x] baseline runner 失败时写入 failed manifest
- [ ] 在本地 PostgreSQL + Redis 环境运行 pgvector retrieval eval
  - 当前阻塞: 本地 embedding 实际输出 1024 维，但 `EMBEDDING_DIMENSION` / pgvector 列为 1536 维，需要统一维度并重建 embeddings。
- [ ] 运行 pgvector answer sampling + answer eval
- [x] 保存 baseline manifest 和 bad cases 的标准路径
- [x] baseline manifest 汇总 artifact 数量和 retrieval summary
- [ ] 根据结果决定 hybrid / rerank 默认策略
