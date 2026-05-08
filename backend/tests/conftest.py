"""pytest 全局：在 import app 之前把 PP_DB_URL 改成 tmp，避免污染 prod db。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

# 必须在 import app.* 之前设置
_TMP_DIR = Path(tempfile.mkdtemp(prefix="pp_test_"))
os.environ.setdefault("PP_DB_URL", f"sqlite:///{_TMP_DIR / 'test.db'}")
os.environ.setdefault("PP_MOCK_LLM", "1")
os.environ.setdefault("PP_SSE_MAX_CONCURRENCY", "5")
