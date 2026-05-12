"""v0.37: 每个项目的"本系统文档"只读根文件夹种子。

每个项目创建时（和老项目启动期回填时）：
  - 建 root-docs-{pid} 根文件夹，name="本系统文档"，readonly=True
  - 把 docs/ 下白名单文档作为子文件塞入（content 直接读 md）
  - 让员工在文件树里随时点开看 PRD / HLD / 使用说明

幂等：再次调不会重复建文件夹/文件（按 path-and-name 检测）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import PROJECT_ROOT

logger = logging.getLogger(__name__)


# 白名单：相对 docs/ 的路径 → 在"本系统文档"下显示的文件名
# 顺序即文件树排序
_DOCS_WHITELIST: list[tuple[str, str]] = [
    ("user_guide.md",    "1-使用说明.md"),
    ("prd.md",           "2-产品需求文档 PRD.md"),
    ("hld.md",           "3-系统设计文档 HLD.md"),
    ("deploy_runbook.md", "4-部署运维手册.md"),
]


def _docs_dir() -> Path:
    return (PROJECT_ROOT / "docs").resolve()


def _read_doc(rel: str) -> str | None:
    p = _docs_dir() / rel
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        logger.warning("read system doc failed %s: %s", rel, exc)
        return None


def ensure_system_docs(db, project_id: str) -> None:
    """幂等：为指定 project 建/补 root-docs 根文件夹及其内容。"""
    from .models import FileNode

    root_id = f"root-docs-{project_id}"
    now = datetime.now(timezone.utc)

    root = db.get(FileNode, root_id)
    if root is None:
        root = FileNode(
            id=root_id,
            project_id=project_id,
            name="本系统文档",
            kind="folder",
            parent_id=None,
            source="system",
            hidden=False,
            readonly=True,
            created_at=now,
            updated_at=now,
        )
        db.add(root)
        db.flush()

    # 上面 add 完，文件直接挂 root.id 下
    for rel, display_name in _DOCS_WHITELIST:
        content = _read_doc(rel)
        if content is None:
            continue
        # 按 (parent=root, name) 找是否已存在
        existing = (
            db.query(FileNode)
            .filter(
                FileNode.project_id == project_id,
                FileNode.parent_id == root_id,
                FileNode.name == display_name,
            )
            .first()
        )
        if existing is not None:
            # 内容如有更新则刷新
            if existing.content != content:
                existing.content = content
                existing.size = len(content.encode("utf-8"))
                existing.updated_at = now
                existing.readonly = True
            continue
        # 新建
        db.add(FileNode(
            id=f"f-docs-{project_id}-{rel.replace('.md','').replace('/','_')[:24]}",
            project_id=project_id,
            name=display_name,
            kind="file",
            parent_id=root_id,
            source="system",
            hidden=False,
            readonly=True,
            mime="text/markdown",
            content=content,
            size=len(content.encode("utf-8")),
            created_at=now,
            updated_at=now,
        ))


def backfill_all_projects(db) -> int:
    """启动期/手动调用：给所有现有 project 都补一遍 root-docs。返回处理数。"""
    from .models import Project

    n = 0
    for p in db.query(Project).all():
        ensure_system_docs(db, p.id)
        ensure_intake_md(db, p)
        n += 1
    db.commit()
    logger.info("system_docs: backfilled %d projects", n)
    return n


def ensure_intake_md(db, project) -> None:
    """v0.37: 把项目 description / intake 落到「我的资料/0-报门.md」（幂等）。

    老项目用户已经看不到自己当初填了啥，这个回填让他们能在文件树里看到。
    """
    from .models import FileNode
    from datetime import datetime, timezone

    pid = project.id
    user_root_id = f"root-user-{pid}"
    # 已经有 0-报门.md 就跳过（不覆盖用户可能的手改）
    existing = (
        db.query(FileNode)
        .filter(
            FileNode.project_id == pid,
            FileNode.parent_id == user_root_id,
            FileNode.name == "0-报门.md",
        )
        .first()
    )
    if existing is not None:
        return

    intake = project.intake_json or {}
    stage_label = {"idea": "创意阶段", "prototype": "已有原型", "deployed": "已落地"}.get(intake.get("stage", ""), "—")
    goal_label = {
        "search_only": "仅检索",
        "full_disclosure": "完整交底书",
        "specific_section": "特定章节",
    }.get(intake.get("goal", ""), "—")
    intake_notes = intake.get("notes", "") or "—"
    domain = project.custom_domain or project.domain or "—"
    md = (
        f"# 报门：{project.title}\n\n"
        f"> 由系统自动回填（老项目）。\n\n"
        f"## 基本信息\n\n"
        f"- **项目标题**：{project.title}\n"
        f"- **技术领域**：{domain}\n"
        f"- **当前阶段**：{stage_label}\n"
        f"- **本次目标**:{goal_label}\n"
        f"- **报门时间**：{project.created_at.isoformat(timespec='seconds') if project.created_at else '—'}\n\n"
        f"## 创意描述\n\n{project.description or '（无描述）'}\n\n"
        + (f"## 补充说明\n\n{intake_notes}\n" if intake_notes != "—" else "")
    )
    now = datetime.now(timezone.utc)
    db.add(FileNode(
        id=f"f-intake-{pid}",
        project_id=pid,
        name="0-报门.md",
        kind="file",
        parent_id=user_root_id,
        source="user",
        mime="text/markdown",
        content=md,
        size=len(md.encode("utf-8")),
        readonly=False,
        created_at=now,
        updated_at=now,
    ))
