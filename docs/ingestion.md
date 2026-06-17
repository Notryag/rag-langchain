# 入库策略

本文说明当前知识库入库、增量更新和重建索引的约定。

## 支持格式

当前支持:

- `.txt`
- `.md`
- `.pdf`
- `.docx`
- `.html`
- `.htm`

不同文档类型会在 `app/retrieval/splitter.py` 中选择对应 chunk 切分策略，并写入 `document_type` metadata。

## 增量入库

默认模式是 `skip_existing`:

```powershell
uv run python -m app.main ingest --data-dir ./data/raw
uv run python -m app.main ingest --data-dir ./data/raw --mode skip_existing
```

策略:

- 入库前根据 `source/page/chunk_index/content_hash` 生成稳定 chunk id。
- 已存在的 chunk id 会被跳过。
- 只新增当前索引中不存在的 chunk。
- 不会删除索引中已经存在、但原始目录里已经移除的旧 chunk。

适用场景:

- 新增文档
- 文档追加内容
- 快速补充知识库，不希望影响已有索引

## 重建索引

重建模式是 `rebuild`:

```powershell
uv run python -m app.main ingest --data-dir ./data/raw --mode rebuild
```

策略:

- 先清空当前 Chroma collection。
- 再按当前 `data_dir` 中的文档重新切分并写入。
- 会移除旧索引中已经不存在于原始目录的内容。

适用场景:

- 修改 chunk 策略后需要重新生成索引
- 删除或重命名了原始文档
- metadata 结构变化后需要统一刷新
- 需要确保评测基于当前原始数据的完整快照

## 删除单个文档索引

如果只想移除某个原始文档已经写入 Chroma 的 chunks，可以按 `source` 删除:

```powershell
uv run python -m app.main delete-source 维护保养.txt
uv run python -m app.main delete-source subdir/example.md --data-dir ./data/raw
```

策略:

- `source` 会按 `--data-dir` 规范化，和入库时写入的 metadata `source` 保持一致。
- 命令只删除向量库中该 `source` 对应的 chunks，不会删除本地原始文件。
- 如果删除后要重新写入该文档，可以再次运行默认增量入库。
- 如果已经删除或重命名了大量原始文档，仍建议使用 `--mode rebuild` 生成完整快照。

适用场景:

- 单个文档下线
- 单个文档内容需要先移除再重新入库
- 调试某个 source 的检索效果

## 当前边界

- 当前没有文档级 manifest 或版本记录。
- 当前日志会记录 `run_id`、入库模式、raw/split/unique/new chunk 数量、按 source 的统计和耗时。
- 如果需要严格追踪每次入库差异，下一步应补充入库摘要文件或 manifest。
