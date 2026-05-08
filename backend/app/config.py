"""集中配置：从环境变量 + .secrets/*.env 加载"""
from __future__ import annotations
import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# 项目根（backend 的父目录）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SECRETS_DIR = PROJECT_ROOT / ".secrets"

# 加载 .secrets/zhihuiya.env（若存在）
zhihuiya_env = SECRETS_DIR / "zhihuiya.env"
if zhihuiya_env.exists():
    load_dotenv(zhihuiya_env, override=False)


class Settings(BaseModel):
    # 服务
    host: str = os.environ.get("PP_HOST", "127.0.0.1")
    port: int = int(os.environ.get("PP_PORT", "8088"))
    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://blind.pub",
    ]
    api_prefix: str = "/api"

    # 数据库
    db_url: str = os.environ.get(
        "PP_DB_URL",
        f"sqlite:///{PROJECT_ROOT / 'backend' / 'patentlypatent.db'}",
    )

    # 项目存储根
    storage_root: Path = PROJECT_ROOT / "backend" / "storage"

    # LLM
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.environ.get("PP_MODEL", "claude-opus-4-7")
    anthropic_light_model: str = os.environ.get("PP_LIGHT_MODEL", "claude-sonnet-4-6")
    mock_llm: bool = os.environ.get("PP_MOCK_LLM", "").lower() in ("1", "true", "yes")

    # v0.18-B：prior_art 章节是否走 agent 智能版（失败 fallback 到 legacy）
    agent_prior_art: bool = os.environ.get("PP_AGENT_PRIOR_ART", "").lower() in (
        "1", "true", "yes",
    )
    # v0.19-C：embodiments / claims 章节是否走 agent 智能版（失败 fallback 到 legacy）
    agent_embodiments: bool = os.environ.get("PP_AGENT_EMBODIMENTS", "").lower() in (
        "1", "true", "yes",
    )
    agent_claims: bool = os.environ.get("PP_AGENT_CLAIMS", "").lower() in (
        "1", "true", "yes",
    )
    # v0.20 Wave1：drawings_description / summary 章节是否走 agent 智能版
    agent_drawings: bool = os.environ.get("PP_AGENT_DRAWINGS", "").lower() in (
        "1", "true", "yes",
    )
    agent_summary: bool = os.environ.get("PP_AGENT_SUMMARY", "").lower() in (
        "1", "true", "yes",
    )

    # 智慧芽
    zhihuiya_token: str = os.environ.get("ZHIHUIYA_TOKEN", "")
    zhihuiya_api_base: str = os.environ.get(
        "ZHIHUIYA_API_BASE", "https://connect.zhihuiya.com",
    )

    @property
    def use_real_llm(self) -> bool:
        return not self.mock_llm and bool(self.anthropic_api_key)

    @property
    def use_real_zhihuiya(self) -> bool:
        return bool(self.zhihuiya_token)

    @property
    def use_agent_sdk_real(self) -> bool:
        """v0.18-A: agent SDK 不走直 API，走 claude CLI 子进程；
        只要 claude 二进制可调，就能用 CLI 自身的 OAuth 认证；
        ANTHROPIC_API_KEY 不是必须的。"""
        if self.mock_llm:
            return False
        import shutil
        return shutil.which("claude") is not None or bool(self.anthropic_api_key)


settings = Settings()
settings.storage_root.mkdir(parents=True, exist_ok=True)
