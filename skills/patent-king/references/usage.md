# pk CLI 子命令速查

```
pk search -i <交底文件> [--sources cnipa,googlepatents,epo,uspto] [--max-results 20] -o search.json
pk draft  -i <交底文件> [-s search.json] -o draft.md
pk check  -i <draft.md> [--original <原申请文本>] -o check_report.md
pk mine   (v0.2)
pk oa     (v0.2)
```

## 环境变量
- `ANTHROPIC_API_KEY`（必填）
- `PK_MODEL`（默认 claude-opus-4-7）
- `PK_LIGHT_MODEL`（默认 claude-sonnet-4-6，lint/抽取用）

## 输出文件结构
- `search.json`：`{elements, keywords, queries, hits, comparison}`
- `draft.md`：权要+说明书五段
- `check_report.md`：法条 lint 报告（按 severity 分级）
