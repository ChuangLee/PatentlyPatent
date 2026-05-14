"""SQLAlchemy engine + session"""
from __future__ import annotations
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    pass


_is_sqlite = settings.db_url.startswith("sqlite")

engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    echo=False,
)

# v0.13-C: SQLite WAL + 关键 PRAGMA（每个新连接执行一次）
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")          # 并发读 + 单写
        cur.execute("PRAGMA synchronous=NORMAL")        # WAL 下安全
        cur.execute("PRAGMA temp_store=MEMORY")
        cur.execute("PRAGMA cache_size=-64000")         # 64 MB
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """开发期：直接 metadata.create_all。生产用 alembic。
    v0.13-C：补关键 index（CREATE INDEX IF NOT EXISTS 幂等）。
    """
    from . import models  # noqa: F401 — 触发 ORM 注册
    Base.metadata.create_all(bind=engine)

    # 关键索引（幂等）
    indices = [
        "CREATE INDEX IF NOT EXISTS ix_projects_owner_status ON projects(owner_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_projects_status        ON projects(status)",
        "CREATE INDEX IF NOT EXISTS ix_file_nodes_proj_parent ON file_nodes(project_id, parent_id)",
        "CREATE INDEX IF NOT EXISTS ix_file_nodes_proj_source ON file_nodes(project_id, source)",
        # v0.34: detached agent runs / events
        "CREATE INDEX IF NOT EXISTS ix_agent_runs_proj_status  ON agent_runs(project_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_agent_events_run_seq    ON agent_events(run_id, seq)",
    ]
    with engine.begin() as conn:
        for ddl in indices:
            try:
                conn.execute(text(ddl))
            except Exception:
                pass
        # v0.13-B: 幂等迁移 — 给已存在的老库补 archived 列
        try:
            conn.execute(text("ALTER TABLE projects ADD COLUMN archived INTEGER DEFAULT 0"))
        except Exception:
            pass  # column already exists
        # v0.28: 幂等迁移 — 给老 users 表补 username / password_hash
        for ddl in (
            "ALTER TABLE users ADD COLUMN username VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN password_hash VARCHAR(256)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username ON users(username)",
            # v0.37: file_nodes 补 readonly 列（默认 0，老数据不变）
            "ALTER TABLE file_nodes ADD COLUMN readonly INTEGER DEFAULT 0",
            # 断点续作：projects 加 plan_snapshot_json（JSON）
            "ALTER TABLE projects ADD COLUMN plan_snapshot_json JSON",
        ):
            try:
                conn.execute(text(ddl))
            except Exception:
                pass
