# 质量评测闭环

这份文档说明如何为当前多租户知识库建立可重复的 retrieval / answer baseline。改检索、rerank、Agent prompt 或引用逻辑前，优先用这里的流程验证。

## 核心原则

- eval dataset 必须和当前 `user_id + kb_id` 已入库文档一致。
- retrieval eval 先判断“有没有召回正确 chunks”，answer eval 再判断“回答有没有覆盖关键事实”。
- bad cases 是后续优化入口，不要在没有 bad cases 的情况下反复调 prompt。
- 对比策略时固定同一批样本，再比较 `similarity`、`hybrid`、`reranker`。

## Retrieval 样本格式

路径可以自定义，例如:

```text
data/eval/current_kb_retrieval.jsonl
```

每行一个 JSON:

```json
{"id":"kb_001","query":"文档上传后什么时候可以问答？","category":"ingestion","expected_sources":["产品说明.md"],"expected_keywords":["pending","processing","completed"],"expected_min_keyword_hits":2,"answerable":true,"score_retrieval":true}
```

字段含义:

- `id`: 稳定样本 ID。
- `query`: 用户会问的问题。
- `expected_sources`: 期望命中的文件名，必须和 chunk metadata 里的 source / filename 对得上。
- `expected_keywords`: 期望召回 chunks 中出现的关键词。
- `expected_min_keyword_hits`: 至少命中的关键词数量。
- `answerable`: 是否应当能基于知识库回答。
- `score_retrieval`: 是否纳入 retrieval pass rate。不可回答样本可设为 `false`。

## Answer 样本格式

路径可以自定义，例如:

```text
data/eval/current_kb_answer.jsonl
```

每行一个 JSON:

```json
{"id":"kb_001","query":"文档上传后什么时候可以问答？","category":"ingestion","expected_facts":["pending","processing","completed","向量化入库"],"expected_min_fact_hits":2,"answerable":true}
```

字段含义:

- `id`: 应尽量和 retrieval 样本 ID 对齐，便于追踪。
- `query`: 问答问题。
- `expected_facts`: 回答中应出现的事实点。
- `expected_min_fact_hits`: 至少覆盖的事实点数量。
- `answerable`: 不可回答问题设为 `false`，评测会接受明确拒答。

## 推荐流程

先检查 embedding 维度和 pgvector 列维度:

```powershell
uv run python -m evaluation.check_pgvector_embedding_config
```

只跑 retrieval baseline:

```powershell
uv run python -m evaluation.run_pgvector_baseline --user-id 1 --kb-id 1 --retrieval-dataset data/eval/current_kb_retrieval.jsonl --retrieval-limit 10 --skip-answer
```

跑完整 baseline:

```powershell
uv run python -m evaluation.run_pgvector_baseline --user-id 1 --kb-id 1 --retrieval-dataset data/eval/current_kb_retrieval.jsonl --answer-dataset data/eval/current_kb_answer.jsonl --retrieval-limit 10 --answer-limit 5
```

产物会写入:

```text
storage/exports/pgvector_baselines/{run_id}/
```

重点查看:

- `baseline_manifest.json`: 本次命令、状态、汇总。
- `pgvector_retrieval_manifest_*.json`: 各检索策略通过率。
- `pgvector_retrieval_bad_cases.jsonl`: 召回失败样本。
- `pgvector_answer_runs.jsonl`: 实际回答、引用、usage。
- `pgvector_answer_bad_cases.jsonl`: 回答失败样本。

## 决策标准

- 如果 `similarity` 失败但 `hybrid` 通过，优先考虑默认启用 `hybrid`。
- 如果 retrieval 通过但 answer 失败，优先检查 Agent prompt、上下文长度和引用格式。
- 如果 retrieval 失败集中在文件名、型号、专有名词，优先加强 lexical / hybrid。
- 如果 retrieval 权限检查失败，先停下修 SQL 层 `user_id + kb_id` 过滤。
