"""FastAPI app 入口"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db, session_scope
from .fixtures import seed_users
from .routes import auth as r_auth
from .routes import projects as r_projects
from .routes import files as r_files
from .routes import chat as r_chat
from .routes import search as r_search
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
    log.info("startup ok | use_real_llm=%s | use_real_zhihuiya=%s",
             settings.use_real_llm, settings.use_real_zhihuiya)
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
app.include_router(r_projects.router, prefix=settings.api_prefix)
app.include_router(r_files.router, prefix=settings.api_prefix)
app.include_router(r_chat.router, prefix=settings.api_prefix)
app.include_router(r_search.router, prefix=settings.api_prefix)
app.include_router(r_disclosure.router, prefix=settings.api_prefix)
app.include_router(r_agent.router, prefix=settings.api_prefix)
app.include_router(r_admin.router, prefix=settings.api_prefix)


@app.get("/api/ping")
def ping():
    return {
        "ok": True,
        "service": "patentlypatent-backend",
        "version": "0.5.0",
        "use_real_llm": settings.use_real_llm,
        "use_real_zhihuiya": settings.use_real_zhihuiya,
    }
