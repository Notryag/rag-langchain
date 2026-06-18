# 执行清单

本文件只保留仍需推进的事项。已完成内容归档到 [todo-done.md](todo-done.md)。

当前阶段重点:

1. 从单用户本地 RAG 演进为多租户企业知识库 RAG
2. 保持权限隔离优先，避免跨用户检索泄露
3. 分批迁移，先建立数据库和认证地基，再迁移入库与问答链路

总体规划见 [multitenant-rag.md](multitenant-rag.md)。

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

- [ ] 增加 Celery app
- [ ] 增加文档处理 task
- [ ] 上传文档后投递异步任务
- [ ] 任务失败时写入 `failed` 和 `error_message`
- [ ] 增加任务幂等策略

## 当前不做

下面这些事情当前不建议优先推进:

- [ ] 组织 / 团队 / RBAC / ACL
- [ ] 同时支持很多向量库
- [ ] 复杂长期 memory
- [ ] 在权限过滤未稳定前做大规模检索优化
- [ ] 在多租户主链路没跑通前做复杂前端后台

## 建议执行顺序

1. Batch 7 异步文档处理
