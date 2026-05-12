"""FastAPI app 入口"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import assert_claude_cli_available, settings
from .db import init_db, session_scope
from .fixtures import seed_users
from .routes import auth as r_auth
from .routes import auth_cas as r_auth_cas
from .routes import projects as r_projects
from .routes import files as r_files
from .routes import chat as r_chat
from .routes import search as r_search
from .routes import kb as r_kb
from .routes import disclosure as r_disclosure
from .routes import agent as r_agent
from .routes import admin as r_admin
from . import agent_sdk_spike

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("patentlypatent")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with session_scope() as db:
        seed_users(db)
    # v0.37: 给所有现存 project 回填"本系统文档"根（幂等）
    try:
        from .system_docs import backfill_all_projects
        with session_scope() as db:
            n = backfill_all_projects(db)
            log.info("system_docs backfilled for %d projects", n)
    except Exception as e:  # noqa: BLE001
        log.warning("system_docs backfill failed: %s", e)
    # v0.37: 启动时把所有 status=running 的 AgentRun 标 cancelled —— 这些 task 因
    # systemd 重启已死掉，DB 状态没刷会让前端误以为还在跑，进项目即"思考中"卡死
    try:
        from datetime import datetime, timezone
        from sqlalchemy import update
        from .models import AgentRun
        with session_scope() as db:
            stale = db.query(AgentRun).filter(AgentRun.status == "running").all()
            now = datetime.now(timezone.utc)
            for r in stale:
                r.status = "cancelled"
                r.finished_at = now
                r.error = "process restarted; marked cancelled at startup"
            if stale:
                log.warning("marked %d stale running AgentRun as cancelled (systemd restart)", len(stale))
    except Exception as e:  # noqa: BLE001
        log.warning("stale run cleanup failed: %s", e)
    cli_path = assert_claude_cli_available()
    log.info(
        "startup ok | claude_cli=%s | use_real_zhihuiya=%s | model=%s",
        cli_path, settings.use_real_zhihuiya, settings.anthropic_model,
    )
    agent_sdk_spike.log_startup_status()
    yield


app = FastAPI(
    title="PatentlyPatent Backend",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 单一 prefix 挂所有路由
app.include_router(r_auth.router, prefix=settings.api_prefix)
app.include_router(r_auth_cas.router, prefix=settings.api_prefix)
app.include_router(r_projects.router, prefix=settings.api_prefix)
app.include_router(r_files.router, prefix=settings.api_prefix)
app.include_router(r_chat.router, prefix=settings.api_prefix)
app.include_router(r_search.router, prefix=settings.api_prefix)
app.include_router(r_disclosure.router, prefix=settings.api_prefix)
app.include_router(r_agent.router, prefix=settings.api_prefix)
app.include_router(r_admin.router, prefix=settings.api_prefix)
app.include_router(r_kb.router, prefix=settings.api_prefix)


@app.get("/api/ping")
def ping():
    return {
        "ok": True,
        "service": "patentlypatent-backend",
        "version": "0.5.0",
        "use_real_zhihuiya": settings.use_real_zhihuiya,
        "cas_enabled": settings.cas_enabled,
        "model": settings.anthropic_model,
    }
