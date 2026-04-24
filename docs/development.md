# 开发与运行约定

## Python 环境

本项目统一使用 `uv` 执行命令，不直接写死 `.venv\Scripts\python.exe`，也不建议直接使用系统 `python`。

推荐方式:

```powershell
uv run python -m evaluation.evaluate_retrieval --limit 2
```

原因:

- `uv` 会自动使用项目环境与锁文件
- 不需要手动关心 `.venv` 路径
- 能减少“系统 python 缺依赖”这类问题
- 当前仓库已经验证 `uv run` 可以直接执行评测命令

## 环境准备

首次拉起项目时，先同步依赖:

```powershell
uv sync
```

后续运行脚本时，统一使用:

```powershell
uv run python -m <module>
```

## 环境变量策略

- `OPENAI_API_KEY` 是必填项，即使接本地兼容服务也需要显式提供一个非空值。
- `OPENAI_BASE_URL` 是可选项；走官方 OpenAI 可留空，走兼容网关或本地模型服务时填写。
- `CHAT_MODEL`、`EMBEDDING_MODEL`、`VECTOR_DB_DIR`、`COLLECTION_NAME`、`LOG_DIR`、`LOG_FILE_NAME` 都有默认值，但不允许为空字符串。
- `TOP_K`、`RETRIEVAL_FETCH_K`、`CHUNK_SIZE` 必须大于 `0`。
- `RETRIEVAL_MAX_CONTEXT_CHARS` 必须大于 `0`，用于限制传给模型的检索上下文字符数。
- `CHUNK_OVERLAP` 必须大于等于 `0`，且必须小于 `CHUNK_SIZE`。
- `RETRIEVAL_SEARCH_TYPE` 当前支持 `similarity`、`mmr` 和 `hybrid`。
- `RETRIEVAL_FETCH_K` 必须大于等于 `TOP_K`。
- `RERANKER_ENABLED` 是可选布尔开关，默认 `false`。
- `RERANKER_STRATEGY` 当前只支持 `embedding_lexical`。
- `LOG_LEVEL` 当前只支持 `CRITICAL`、`ERROR`、`WARNING`、`INFO`、`DEBUG`。
- 入库当前支持 `.txt`、`.md`、`.pdf`、`.docx`、`.html`、`.htm`。

## 常用评测命令

### 检索评测

```powershell
uv run python -m evaluation.evaluate_retrieval
uv run python -m evaluation.evaluate_retrieval --limit 10
uv run python -m evaluation.evaluate_retrieval --search-type similarity mmr --top-k 3 5 --fetch-k 8 12
uv run python -m evaluation.evaluate_retrieval --show-passes
uv run python -m evaluation.evaluate_retrieval --search-type similarity --top-k 3 --fetch-k 8 --reranker off on
uv run python -m evaluation.evaluate_retrieval --search-type hybrid --top-k 3 --fetch-k 8 --reranker off on
uv run python -m evaluation.evaluate_retrieval --source 扫地机器人100问2.txt
uv run python -m evaluation.evaluate_retrieval --metadata-filter-json '{"source":"维护保养.txt"}'
uv run python -m evaluation.evaluate_hybrid_need --show-failures
uv run python -m evaluation.evaluate_hybrid_search --show-changes
```

### 采样回答

```powershell
uv run python -m evaluation.generate_answers --limit 5
```

### 回答评测

```powershell
uv run python -m evaluation.evaluate_answers --limit 5
uv run python -m evaluation.evaluate_answers --show-passes
uv run python -m evaluation.evaluate_answers --bad-cases-out data/eval/bad_cases.jsonl
```

### 抓取单次 Trace

```powershell
uv run python -m evaluation.capture_trace "扫地机器人连不上WiFi怎么办"
```

## 统一入口

常用启动方式现在可以统一走 `app.main`:

```powershell
uv run python -m app.main cli
uv run python -m app.main ingest --data-dir ./data/raw
uv run python -m app.main ingest --data-dir ./data/raw --mode rebuild
uv run python -m app.main streamlit
```

如果需要自定义 Streamlit 地址或端口:

```powershell
uv run python -m app.main streamlit --server-address 0.0.0.0 --server-port 8501
```

## 注意事项

- `evaluate_retrieval` 依赖本地向量库和 embedding 检索链路。
- `generate_answers` 与 `capture_trace` 会真实调用模型，需要 `.env` 中的模型配置和 API Key 可用。
- `evaluate_answers` 默认会把未通过样本导出到 `data/eval/bad_cases.jsonl`，便于后续回看 bad case。
- 如果命令报依赖缺失，先执行 `uv sync`，再重试 `uv run ...`。
