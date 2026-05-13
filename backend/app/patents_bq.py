"""v0.38 Option B: Google BigQuery `patents-public-data` adapter.

BigQuery 数据集由 IFI Claims 每周更新，含 CN 全量 + 英译版 + embedding_v1 向量。
零鉴权 = 不可能；需要 GCP 凭证（service account JSON）。

启用方式（用户侧 1 次设置）：
  1. https://console.cloud.google.com 创建/选择项目
  2. 启用 BigQuery API
  3. 创建 Service Account + 下载 JSON key（角色：BigQuery Data Viewer + BigQuery Job User）
  4. JSON 放到 .secrets/gcp-bq.json
  5. backend env 加 GOOGLE_APPLICATION_CREDENTIALS=.secrets/gcp-bq.json + BQ_BILLING_PROJECT=<你的项目 ID>
  6. 重启 backend

缺凭证时：is_available() 返 False，build_bq_tools() 返空 → agent 看不见 BigQuery 工具，行为不变。

成本：BigQuery 按扫描字节计费，免费层 1TB/月（足够小项目）。本 adapter 默认 LIMIT 50 + 字段裁剪。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """检测 GCP 凭证 + billing project 是否齐。"""
    cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    proj = os.environ.get("BQ_BILLING_PROJECT", "")
    if not cred or not proj:
        return False
    if not Path(cred).exists():
        return False
    return True


def _client():
    """懒加载 BigQuery 客户端。"""
    from google.cloud import bigquery
    return bigquery.Client(project=os.environ["BQ_BILLING_PROJECT"])


# ─── 工具实现 ─────────────────────────────────────────────────────────────


_PUB_TABLE = "patents-public-data.patents.publications"
_EMB_TABLE = "patents-public-data.patents.publications_202210"  # embedding_v1


async def bq_search_patents(keyword: str, country: str = "CN", year_from: int = 2020, limit: int = 20) -> dict:
    """关键词 + 国别 + 年份 检索专利标题摘要列表。

    返回 [{publication_number, title, abstract, assignee, filing_date, country_code}]
    """
    import asyncio
    if not is_available():
        return {"content": [{"type": "text", "text": "BigQuery adapter 未启用（缺 GOOGLE_APPLICATION_CREDENTIALS / BQ_BILLING_PROJECT）"}], "isError": True}

    keyword = (keyword or "").strip().replace("'", " ")
    if not keyword:
        return {"content": [{"type": "text", "text": "keyword 为空"}], "isError": True}

    # CN 数据走 title_localized / abstract_localized 简体中文；非 CN 用英文标题摘要
    field_t = "title_localized" if country == "CN" else "title_localized"
    field_a = "abstract_localized" if country == "CN" else "abstract_localized"

    sql = f"""
SELECT
  publication_number,
  ARRAY_TO_STRING(ARRAY(SELECT text FROM UNNEST({field_t}) WHERE language='zh' LIMIT 1), '') AS title_zh,
  ARRAY_TO_STRING(ARRAY(SELECT text FROM UNNEST({field_a}) WHERE language='zh' LIMIT 1), '') AS abstract_zh,
  ARRAY_TO_STRING(ARRAY(SELECT name FROM UNNEST(assignee_harmonized) LIMIT 3), ' / ') AS assignee,
  filing_date,
  country_code
FROM `{_PUB_TABLE}`
WHERE country_code = @country
  AND filing_date >= {year_from}0101
  AND (
    EXISTS (SELECT 1 FROM UNNEST({field_t}) AS t WHERE STRPOS(t.text, @kw) > 0)
    OR EXISTS (SELECT 1 FROM UNNEST({field_a}) AS a WHERE STRPOS(a.text, @kw) > 0)
  )
ORDER BY filing_date DESC
LIMIT {min(int(limit), 50)}
"""
    from google.cloud import bigquery

    def _run():
        cli = _client()
        job_cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("country", "STRING", country),
                bigquery.ScalarQueryParameter("kw", "STRING", keyword),
            ],
            use_query_cache=True,
        )
        rows = list(cli.query(sql, job_config=job_cfg).result(timeout=30))
        return [dict(r.items()) for r in rows]

    try:
        rows = await asyncio.to_thread(_run)
    except Exception as exc:  # noqa: BLE001
        logger.warning("bq_search_patents failed: %s", exc)
        return {"content": [{"type": "text", "text": f"BigQuery 查询失败：{type(exc).__name__}: {exc}"}], "isError": True}

    import json as _json
    text = f"BigQuery 命中 {len(rows)} 条（country={country}, year≥{year_from}, kw={keyword!r}）：\n"
    text += _json.dumps(rows, ensure_ascii=False, default=str, indent=2)[:8000]
    return {"content": [{"type": "text", "text": text}], "data": rows}


async def bq_patent_detail(publication_number: str) -> dict:
    """按 publication_number 拉单件详情（含权要全文）。"""
    import asyncio
    if not is_available():
        return {"content": [{"type": "text", "text": "BigQuery adapter 未启用"}], "isError": True}
    pn = (publication_number or "").strip()
    if not pn:
        return {"content": [{"type": "text", "text": "publication_number 为空"}], "isError": True}

    sql = f"""
SELECT
  publication_number,
  ARRAY_TO_STRING(ARRAY(SELECT text FROM UNNEST(title_localized) WHERE language='zh'), '') AS title_zh,
  ARRAY_TO_STRING(ARRAY(SELECT text FROM UNNEST(abstract_localized) WHERE language='zh'), '') AS abstract_zh,
  ARRAY_TO_STRING(ARRAY(SELECT text FROM UNNEST(claims_localized) WHERE language='zh'), '\\n') AS claims_zh,
  ARRAY_TO_STRING(ARRAY(SELECT text FROM UNNEST(description_localized) WHERE language='zh'), '\\n') AS description_zh,
  ARRAY_TO_STRING(ARRAY(SELECT name FROM UNNEST(assignee_harmonized)), ' / ') AS assignee,
  filing_date,
  publication_date,
  family_id,
  ARRAY_TO_STRING(ARRAY(SELECT code FROM UNNEST(ipc) LIMIT 5), ', ') AS ipc,
  ARRAY_TO_STRING(ARRAY(SELECT publication_number FROM UNNEST(citation) LIMIT 10), ', ') AS citations
FROM `{_PUB_TABLE}`
WHERE publication_number = @pn
LIMIT 1
"""
    from google.cloud import bigquery

    def _run():
        cli = _client()
        job_cfg = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("pn", "STRING", pn)],
        )
        rows = list(cli.query(sql, job_config=job_cfg).result(timeout=30))
        return [dict(r.items()) for r in rows]

    try:
        rows = await asyncio.to_thread(_run)
    except Exception as exc:  # noqa: BLE001
        return {"content": [{"type": "text", "text": f"BigQuery 失败：{exc}"}], "isError": True}

    if not rows:
        return {"content": [{"type": "text", "text": f"未找到 {pn}"}], "isError": True}

    r = rows[0]
    # 截断权要/说明书避免单次 token 爆掉
    if r.get("description_zh") and len(r["description_zh"]) > 8000:
        r["description_zh"] = r["description_zh"][:8000] + "\n…（已截断）"
    if r.get("claims_zh") and len(r["claims_zh"]) > 4000:
        r["claims_zh"] = r["claims_zh"][:4000] + "\n…（已截断）"
    import json as _json
    return {
        "content": [{"type": "text", "text": _json.dumps(r, ensure_ascii=False, default=str, indent=2)}],
        "data": r,
    }


# ─── 注册到 in-process MCP server ────────────────────────────────────────


def build_bq_tools_for_server():
    """返回 (tool_funcs, allowed_names) 二元组用于 create_sdk_mcp_server 合并。

    若 is_available()=False 返回 ([], [])，agent 完全看不到这些工具。
    """
    if not is_available():
        return [], []

    from claude_agent_sdk import tool

    @tool(
        "bq_search_patents",
        (
            "Google Patents BigQuery 关键词检索（免费，CN 全量）。"
            "输入：keyword（关键词，中英文）；country（默认 CN，可填 US/EP）；year_from（默认 2020）；limit（默认 20，最大 50）。"
            "返回 [{publication_number, title_zh, abstract_zh, assignee, filing_date, country_code}]。"
            "适合：宽泛探索期；不耗智慧芽 quota。"
        ),
        {"keyword": str, "country": str, "year_from": int, "limit": int},
    )
    async def _t_search(args):
        return await bq_search_patents(
            keyword=(args or {}).get("keyword", ""),
            country=(args or {}).get("country") or "CN",
            year_from=int((args or {}).get("year_from") or 2020),
            limit=int((args or {}).get("limit") or 20),
        )

    @tool(
        "bq_patent_detail",
        (
            "Google Patents BigQuery 按公开号拉详情（含中文权要+说明书全文）。"
            "输入 publication_number，如 CN114239036A。"
            "返回：title/abstract/claims/description/assignee/ipc/citations 全字段。"
        ),
        {"publication_number": str},
    )
    async def _t_detail(args):
        return await bq_patent_detail((args or {}).get("publication_number", ""))

    return [_t_search, _t_detail], [
        "mcp__patent-tools__bq_search_patents",
        "mcp__patent-tools__bq_patent_detail",
    ]
