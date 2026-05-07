"""CNIPA 公布公告（epub.cnipa.gov.cn）关键字检索。

注意：CNIPA epub 端有反爬（验证码/限流），生产需要会话维持+滑块。
本 MVP 给一个安全占位：只做 query → URL，不强行抓取；返回空+提示信息，
让上层降级到 Google Patents 的 CN 译文兜底。

后续 v0.2 可接入真实 selenium/playwright + 验证码处理。
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pk.search.sources.base import SourceBase


class CnipaSource(SourceBase):
    name = "cnipa"
    base = "http://epub.cnipa.gov.cn"

    def search(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        # MVP placeholder: 直接返回检索 URL，提示用户人工跑或后续接 playwright。
        return [{
            "doc_id": "",
            "title": "[CNIPA epub 检索占位] 请在浏览器中打开下方 URL 或等待 v0.2 自动化",
            "abstract": f"query={query}",
            "url": f"{self.base}/?keyword={quote(query)}",
            "warning": "CNIPA 反爬需会话+滑块，MVP 阶段未实现自动抓取；建议同时启用 googlepatents 兜底。",
        }]
