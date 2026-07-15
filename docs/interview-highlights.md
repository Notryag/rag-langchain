# 面试亮点与演示路径

本文用于说明项目中值得深入讲解的工程决策。重点不是功能数量，而是问题、取舍、实现和验证形成闭环。

## 亮点一：多租户 RAG 权限边界

检索不是先查向量再在 Python 过滤，而是在 SQL 查询阶段同时约束 `user_id + kb_id`。知识库、文档、会话、run 和 run event 的读取也经过用户范围检查。

演示建议:

1. 创建两个用户和两个知识库。
2. 上传内容可区分的文档。
3. 用 retrieval preview 展示跨租户内容不会命中。
4. 运行 `tests/test_pgvector_retrieval_eval.py` 展示权限泄漏会导致评测失败。

## 亮点二：认证与授权分离

JWT 负责确认用户身份，`UserRole` 负责授权。公开注册只能创建 `user`，管理员必须通过受控 CLI 创建。全局 Prompt 属于系统级配置，因此所有 Prompt 管理接口统一依赖 `require_admin`。

数据库同时保证 Prompt 的 `(name, version)` 唯一，并通过部分唯一索引保证最多一个 active Prompt。服务层的预检查用于友好错误，数据库约束负责处理并发竞争。

演示建议:

1. 普通用户访问 `/api/v1/prompts` 得到 403。
2. 创建管理员并登录。
3. 创建和激活 Prompt，查看 operation log。
4. 展示并发安全为什么不能只靠 `SELECT` 后再 `INSERT`。

## 亮点三：可靠的文档入库状态机

上传文件通过临时文件对象按 1 MiB 分块写入，限制扩展名、MIME 和总字节数。超过限制或数据库提交失败时会删除不完整文件。

文档处理使用行锁抢占 `processing` 状态。同一文档的重复任务不会同时删除和重建 chunks。Celery 使用 late ack、worker lost 重投、有限指数退避、soft/hard time limit 和单任务预取。

状态流转:

```text
pending/failed/completed -> processing -> completed
                              |
                              +---------> failed -> retry
```

演示建议:

1. 上传不支持类型，展示 415。
2. 上传超过限制的文件，展示 413 且目录无残留。
3. 同时触发两次处理，第二次返回 409 或 worker 返回 `already_processing`。
4. 模拟 embedding 服务失败，展示失败状态和 Celery 重试。

## 亮点四：可交付性门禁

CI 拆成三个并行 job:

- backend: 锁定依赖、Ruff、真实 PostgreSQL migration 和全量测试。
- frontend: `npm ci`、TypeScript/Vite 构建、high severity audit。
- container: BuildKit 构建并复用 GitHub Actions cache。

运行镜像固定 `uv` 版本，并使用无登录权限的非 root 用户；上传、日志和 checkpointer 目录在构建阶段显式授予该用户写权限。

该设计把“本地能跑”提升为“每次提交都能重复验证”。Ruff 首期只启用正确性规则，避免一次提交混入大规模历史格式化；后续可以逐步扩大规则集。

## 尚未完成但能主动说明的取舍

- Runtime 和 SSE 仍是单进程内存实现，暂不声称支持水平扩展。
- 下一阶段将持久化 SSE event，并支持 `Last-Event-ID` 断线续传。
- hybrid lexical 当前仍在 Python 打分，质量基线完成后再迁移到 PostgreSQL full-text search。
- 当前是最小 `admin/user` RBAC，未引入组织、团队和 ACL，避免面试项目过度设计。

面试时应明确说明这些边界，以及什么业务规模或可靠性目标会触发下一次架构升级。
