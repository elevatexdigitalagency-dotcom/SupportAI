import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.db.database import current_time


def make_workspace_slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
    return f"{base[:40]}-{secrets.token_hex(3)}"


def provision_workspace(
    conn: sqlite3.Connection,
    owner_user_id: int,
    workspace_name: str,
) -> Dict[str, Any]:
    now = current_time()
    slug = make_workspace_slug(workspace_name)
    cursor = conn.execute(
        """
        INSERT INTO workspaces (name, slug, owner_user_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (workspace_name.strip(), slug, owner_user_id, now, now),
    )
    workspace_id = cursor.lastrowid

    conn.execute(
        """
        INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
        VALUES (?, ?, 'owner', ?)
        """,
        (workspace_id, owner_user_id, now),
    )

    collection_name = f"ws_{workspace_id}_kb"
    conn.execute(
        """
        INSERT INTO knowledge_bases (workspace_id, name, description, collection_name, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            workspace_id,
            "Default Knowledge Base",
            "Primary workspace knowledge base",
            collection_name,
            now,
            now,
        ),
    )

    free_plan = conn.execute(
        "SELECT id FROM plans WHERE code = 'free' LIMIT 1"
    ).fetchone()
    if free_plan:
        period_start = datetime.now(timezone.utc)
        period_end = period_start + timedelta(days=30)
        conn.execute(
            """
            INSERT INTO subscriptions
            (workspace_id, plan_id, status, current_period_start, current_period_end, created_at, updated_at)
            VALUES (?, ?, 'active', ?, ?, ?, ?)
            """,
            (
                workspace_id,
                free_plan["id"],
                period_start.isoformat(),
                period_end.isoformat(),
                now,
                now,
            ),
        )

    return {
        "id": workspace_id,
        "name": workspace_name.strip(),
        "slug": slug,
        "role": "owner",
        "created_at": now,
    }


def list_user_workspaces(conn: sqlite3.Connection, user_id: int) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT w.id, w.name, w.slug, w.owner_user_id, wm.role, w.created_at
        FROM workspace_members wm
        JOIN workspaces w ON w.id = wm.workspace_id
        WHERE wm.user_id = ?
        ORDER BY w.id ASC
        """,
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]
