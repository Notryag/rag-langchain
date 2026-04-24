# Hybrid Search 需求评估

本评估用于判断当前阶段是否需要引入 hybrid search。结论基于离线诊断，不代表已经把 hybrid search 接入主检索链路。

## 评估方法

使用当前最佳 dense baseline:

```powershell
uv run python -m evaluation.evaluate_retrieval --search-type similarity --top-k 3 --fetch-k 8 --reranker on
```

再运行词面补救诊断:

```powershell
uv run python -m evaluation.evaluate_hybrid_need --show-failures
```

`evaluate_hybrid_need` 会先跑现有 dense retrieval，再对 dense 失败样本做全库 chunk 的词面匹配诊断。词面匹配使用评测样本中的 `expected_keywords` 和 query term，因此它是“是否值得做 hybrid”的诊断工具，不是线上 hybrid search 实现。

## 当前结果

数据集:

- retrieval eval 总样本: 34
- 计分样本: 29
- 拒答场景跳过: 5

Dense baseline:

- `similarity + reranker=on`
- passed: 25 / 29
- pass_rate: 86.21%
- dense_failed: 4

词面补救诊断:

- lexical_rescued_dense_failures: 4 / 4
- lexical_rescue_rate: 100.00%
- recommendation: `evaluate_hybrid_search`

可被词面补救的 dense 失败样本:

- `faq_015_mop_watermark`: 水痕/水渍场景，词面命中 `出水量 / 拖布 / 低速拖地`
- `faq_026_battery_drop`: 续航衰减场景，词面命中 `及时回充 / 满充满放 / 更换电池`
- `faq_031_water_tank_leak`: 水箱漏水场景，词面命中 `水箱盖 / 出水管 / 更换`
- `faq_068_wood_floor`: 木地板拖地场景，词面命中 `调小出水量 / 干拖模式 / 拖布拧干`

## 结论

当前需要继续评估 hybrid search。

原因:

- 剩余 dense 失败样本不是完全无资料，而是相关 chunk 可通过词面信号找到。
- 失败集中在明确实体或操作词上，例如 `水箱盖`、`出水管`、`干拖模式`、`更换电池`。
- 现有 reranker 已把 pass rate 提到 86.21%，继续只调 dense 参数收益有限。

建议下一步先做离线 hybrid 原型:

- 保持现有 dense retrieval 不变。
- 新增 lexical candidate 召回，只在离线评测里融合。
- 用 RRF 或加权分数融合 dense 与 lexical 候选。
- 目标是让 retrieval eval pass_rate 从 86.21% 提升到 90% 以上，再决定是否接入主链路。
