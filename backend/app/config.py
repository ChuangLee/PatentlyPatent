"""集中配置：从环境变量 + .secrets/*.env 加载"""
from __future__ import annotations
import os
import shutil
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

    # 项目存储根（PP_STORAGE_ROOT env 可覆盖；测试时 conftest 指 tmp）
    storage_root: Path = Path(os.environ.get(
        "PP_STORAGE_ROOT",
        str(PROJECT_ROOT / "backend" / "storage"),
    ))

    # LLM 模型（claude-agent-sdk 的 model alias，传给 CLI）
    anthropic_model: str = os.environ.get("PP_MODEL", "claude-opus-4-7")
    anthropic_light_model: str = os.environ.get("PP_LIGHT_MODEL", "claude-sonnet-4-6")

    # 章节级 agent 智能版开关（保留 —— 这些不是 mock 开关，而是模板 vs agent 的灰度）
    agent_prior_art: bool = os.environ.get("PP_AGENT_PRIOR_ART", "").lower() in (
        "1", "true", "yes",
    )
    agent_embodiments: bool = os.environ.get("PP_AGENT_EMBODIMENTS", "").lower() in (
        "1", "true", "yes",
    )
    agent_claims: bool = os.environ.get("PP_AGENT_CLAIMS", "").lower() in (
        "1", "true", "yes",
    )
    agent_drawings: bool = os.environ.get("PP_AGENT_DRAWINGS", "").lower() in (
        "1", "true", "yes",
    )
    agent_summary: bool = os.environ.get("PP_AGENT_SUMMARY", "").lower() in (
        "1", "true", "yes",
    )

    # JWT auth
    jwt_secret: str = os.environ.get("PP_JWT_SECRET", "dev-secret-change-in-prod")
    jwt_expire_hours: int = int(os.environ.get("PP_JWT_EXPIRE_HOURS", "24"))

    # CAS protocol 2.0/3.0 SSO（与 JWT 共存）
    cas_enabled: bool = os.environ.get("PP_CAS_ENABLED", "").lower() in ("1", "true", "yes")
    cas_server_url: str = os.environ.get("PP_CAS_SERVER", "https://casdoor.org/cas/example/app-cas")
    cas_service_url: str = os.environ.get(
        "PP_CAS_SERVICE", "https://blind.pub/patent/api/auth/cas/callback",
    )
    cas_frontend_redirect: str = os.environ.get(
        "PP_CAS_FRONT_REDIRECT", "https://blind.pub/patent/login",
    )

    # 智慧芽（数据源仍可缺失，缺则 zhihuiya.py 会抛 ZhihuiyaError）
    zhihuiya_token: str = os.environ.get("ZHIHUIYA_TOKEN", "")
    zhihuiya_api_base: str = os.environ.get(
        "ZHIHUIYA_API_BASE", "https://connect.zhihuiya.com",
    )
    # v0.38: 智慧芽托管 MCP 服务（HTTP streamable）；apikey 在 URL query 里，整 URL 视为 secret
    zhihuiya_mcp_logic: str = os.environ.get("ZHIHUIYA_MCP_LOGIC", "")
    zhihuiya_mcp_main: str = os.environ.get("ZHIHUIYA_MCP_MAIN", "")

    # 测试桩开关：仅 conftest 用来跳过启动期 CLI 校验。生产代码不读它。
    skip_cli_check: bool = os.environ.get("PP_SKIP_CLI_CHECK", "").lower() in (
        "1", "true", "yes",
    )

    @property
    def use_real_zhihuiya(self) -> bool:
        return bool(self.zhihuiya_token)


settings = Settings()
settings.storage_root.mkdir(parents=True, exist_ok=True)


def assert_claude_cli_available() -> str:
    """启动期硬校验：claude CLI 必须可用。返回 CLI 路径。

    优先用 claude-agent-sdk 自带的 bundled CLI（不依赖系统 PATH），
    其次 fallback 到 PATH 上的 `claude`。两者都没就直接 RuntimeError。
    测试通过 PP_SKIP_CLI_CHECK=1 跳过。
    """
    if settings.skip_cli_check:
        return "(skipped by PP_SKIP_CLI_CHECK)"

    # 1) bundled SDK CLI
    try:
        import claude_agent_sdk  # noqa: F401
        sdk_dir = Path(claude_agent_sdk.__file__).resolve().parent
        bundled = sdk_dir / "_bundled" / "claude"
        if bundled.exists():
            return str(bundled)
    except Exception:
        pass

    # 2) system PATH
    p = shutil.which("claude")
    if p:
        return p

    raise RuntimeError(
        "claude CLI 不可用：既未找到 claude-agent-sdk bundled CLI，"
        "PATH 上也没有 `claude`。请安装 claude-agent-sdk 或把 claude 加入 PATH。"
    )
